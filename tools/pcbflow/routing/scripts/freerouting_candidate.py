#!/usr/bin/env python3
"""Build an isolated front-copper, zero-via Freerouting candidate; never overwrite sources."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'kicad' / 'scripts'))
from manufacturing_discovery import extract_blocks
from headless_pcb_review import find_kicad_cli, review, sha256
from routing_metrics import metrics
from routing_finish import finish


def strip_routing(text: str) -> str:
    for kind in ('segment', 'arc', 'via', 'zone'):
        for block in extract_blocks(text, kind):
            if kind == 'zone' and '(keepout' in block:
                continue
            text = text.replace(block, '', 1)
    return text


def constrain_dsn(text: str, clearance_mm: float) -> str:
    structures = extract_blocks(text, 'structure')
    if len(structures) != 1:
        raise ValueError('expected one DSN structure')
    structure = structures[0]
    layers = extract_blocks(structure, 'layer')
    if len(layers) != 2 or not all(name in structure for name in ('F.Cu', 'B.Cu')):
        raise ValueError('adapter supports two-copper-layer files routed only on F.Cu')
    if extract_blocks(structure, 'autoroute_settings'):
        raise ValueError('unexpected pre-existing autoroute settings')
    # Freerouting resolves layer names immediately: settings MUST follow layers.
    settings = '''(snap_angle fortyfive_degree)
    (autoroute_settings (autoroute on) (postroute on) (vias off)
      (layer_rule F.Cu (active on) (preferred_direction horizontal)
        (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 1.0))
      (layer_rule B.Cu (active off) (preferred_direction vertical)
        (preferred_direction_trace_costs 1.0) (against_preferred_direction_trace_costs 1.0)))'''
    text = text.replace(structure, structure[:-1] + '\n' + settings + '\n)')
    # KiCad exports a 50 um SMD-specific exception; do not weaken project clearance.
    import re
    def clamp(match):
        return f'(clearance {max(float(match[1]), clearance_mm * 1000):g} (type smd_smd))'
    if '(resolution um 10)' not in text:
        raise ValueError('expected native KiCad DSN micrometre units')
    return re.sub(r'\(clearance ([\d.]+) \(type smd_smd\)\)', clamp, text)


def geometry_signature(text: str) -> dict:
    # Exact native blocks: imported routing may not modify assembly or mechanics.
    return {kind: sorted(extract_blocks(text, kind)) for kind in
            ('footprint', 'gr_line', 'gr_arc', 'gr_rect', 'gr_poly', 'gr_circle', 'gr_text')}


def geometry_hash(text: str) -> str:
    return hashlib.sha256(json.dumps(geometry_signature(text), sort_keys=True).encode()).hexdigest()


def run(command: list[str], log: Path, timeout: int) -> None:
    with log.open('w') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{log.stem} exited {result.returncode}; inspect {log}')


def worker(mode: str, board: Path, exchange: Path) -> None:
    import wx
    app = wx.App(False)
    import pcbnew
    native = pcbnew.LoadBoard(str(board))
    if mode == 'export':
        pcbnew.SaveBoard(str(board), native)
        if not pcbnew.ExportSpecctraDSN(native, str(exchange)):
            raise RuntimeError('native DSN export failed')
        # KiCad SWIG export can transfer ownership: do not reuse native afterward.
    else:
        if not pcbnew.ImportSpecctraSES(native, str(exchange)):
            raise RuntimeError('native SES import failed')
        pcbnew.SaveBoard(str(board), native)


def build(args, workspace: Path) -> dict:
    source = args.board.expanduser().resolve()
    sources = [source, source.with_suffix('.kicad_pro')]
    if source.with_suffix('.kicad_dru').exists():
        sources.append(source.with_suffix('.kicad_dru'))
    if not all(p.is_file() for p in sources):
        raise ValueError('board and sibling project are required')
    if any('(keepout' in z for z in extract_blocks(source.read_text(), 'zone')):
        raise ValueError('rule-area/keepout staging requires an explicitly reviewed adapter; refusing to discard it')
    hashes = {p: sha256(p) for p in sources}
    board = workspace / source.name
    for p in sources:
        shutil.copy2(p, workspace / p.name)
    board.write_text(strip_routing(source.read_text()))
    if any(extract_blocks(board.read_text(), k) for k in ('segment', 'arc', 'via', 'zone')):
        raise ValueError('stale routing survived snapshot preparation')
    script = str(Path(__file__).resolve())
    dsn, ses = workspace / 'route.dsn', workspace / 'route.ses'
    run([str(args.kicad_python), script, '--worker', 'export', str(board), str(dsn)],
        workspace / 'export.log', 60)
    preserved_geometry = geometry_hash(board.read_text())
    dsn.write_text(constrain_dsn(dsn.read_text(), args.clearance))
    runtime = workspace / 'runtime'
    runtime.mkdir()
    run([str(args.java), '-Djava.awt.headless=true', '-jar', str(args.jar),
         '-de', str(dsn), '-do', str(ses), '-mp', str(args.passes), '-mt', '1', '-da',
         '--gui.enabled=false', '--api_server.enabled=false', '--mcp_server.enabled=false',
         '--logging.file.enabled=false', f'--user_data_path={runtime}'],
        workspace / 'router.log', args.timeout)
    if not ses.is_file() or not ses.stat().st_size:
        raise ValueError('router produced no SES output')
    run([str(args.kicad_python), script, '--worker', 'import', str(board), str(ses)],
        workspace / 'import.log', 60)
    if geometry_hash(board.read_text()) != preserved_geometry:
        raise ValueError('routing import changed assembly or mechanical geometry')
    finished, adjustments = finish(board.read_text(), args.min_width)
    board.write_text(finished)
    candidate = metrics(board)
    geometry_ok = (candidate['segments'] > 0 and candidate['vias'] == 0
                   and set(candidate['layers']) == {'F.Cu'} and candidate['zones'] == 0
                   and all(w >= args.min_width - 1e-6 for n in candidate['nets'].values()
                           for w in n['widths_mm']))
    evidence = review(board, workspace / 'review', find_kicad_cli(args.kicad_cli))
    unchanged = all(sha256(p) == digest for p, digest in hashes.items())
    return {'status': 'pass' if geometry_ok and unchanged and evidence['status'] == 'pass' else 'fail',
            'candidate': str(board), 'source_unchanged': unchanged,
            'inputs': {p.name: digest for p, digest in hashes.items()},
            'geometry_sha256': preserved_geometry, 'finishing': adjustments, 'engine_sha256': sha256(args.jar), 'geometry_gate': geometry_ok,
            'baseline': metrics(source), 'routing': candidate, 'review': evidence,
            'coverage': 'isolated routing candidate; critical path and visual acceptance required before adoption'}


def main() -> int:
    if len(sys.argv) == 5 and sys.argv[1] == '--worker':
        worker(sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('--kicad-python', type=Path, required=True)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--jar', type=Path, required=True)
    parser.add_argument('--kicad-cli', type=Path)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--passes', type=int, default=30, choices=range(1, 101), metavar='1..100')
    parser.add_argument('--min-width', type=float, default=0.25)
    parser.add_argument('--clearance', type=float, default=0.20)
    args = parser.parse_args()
    workspace = Path(tempfile.mkdtemp(prefix='pcb-freerouting-'))
    try:
        if args.timeout <= 0 or args.min_width <= 0 or args.clearance <= 0:
            raise ValueError('timeout, minimum width and clearance must be positive')
        result = build(args, workspace)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        result = {'status': 'fail', 'error': str(error)}
    result['details'] = str(workspace)
    (workspace / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, separators=(',', ':'), sort_keys=True))
    return 0 if result['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
