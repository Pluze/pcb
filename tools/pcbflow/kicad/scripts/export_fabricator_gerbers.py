#!/usr/bin/env python3
"""Export/audit complete native Gerber X2 + job + PTH/NPTH drill supplier packages."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import tempfile
from manufacturing_discovery import discover_packages, extract_blocks, stage_package_board
from export_circuitpro_u4_packages import find_cli, run, count_drills, normalized, stale_directories
from manufacturing_transaction import replace_directories

def layers_for(board: Path, coupon_layer=None):
    declared = extract_blocks(board.read_text(), 'layers')[0]
    copper = re.findall('\\(\\d+\\s+"((?:F|B|In\\d+)\\.Cu)"', declared)
    if not copper:
        raise ValueError('board declares no copper layers')
    return copper + ['F.Mask', 'B.Mask', 'F.Silkscreen', 'B.Silkscreen', 'F.Paste', 'B.Paste', 'Edge.Cuts'] + ([coupon_layer] if coupon_layer else [])

def plot_filename(board: Path, layer: str) -> str:
    """KiCad names plots from the display name of custom layers."""
    declared = extract_blocks(board.read_text(), 'layers')[0]
    names = {key: alias or key for (key, alias) in re.findall('\\(\\d+\\s+"([^"]+)"\\s+\\w+(?:\\s+"([^"]+)")?\\)', declared)}
    return board.stem + '-' + names.get(layer, layer).replace('.', '_') + '.gbr'

def validate(directory: Path, package: dict, layers: list[str]):
    files = {p.name for p in directory.iterdir() if p.is_file()}
    stem = package['board'].stem
    layer_files = {plot_filename(package['board'], layer) for layer in layers}
    required = layer_files | {stem + '-job.gbrjob', stem + '-PTH.drl', stem + '-NPTH.drl', 'PACKAGE.md'}
    if files != required:
        raise ValueError(f'Gerber package file set differs: missing={required - files}, extra={files - required}')
    for name in layer_files:
        data = (directory / name).read_text()
        if '%MOMM*%' not in data or not data.rstrip().endswith('M02*') or 'TF.FileFunction' not in data:
            raise ValueError(f'invalid or untyped Gerber: {name}')
    job = json.loads((directory / (stem + '-job.gbrjob')).read_text())
    declared = {item['Path'] for item in job['FilesAttributes']}
    if declared != layer_files:
        raise ValueError('Gerber job layer references do not match package')
    for (suffix, count) in [('PTH', package['plated_drills']), ('NPTH', package['unplated_drills'])]:
        path = directory / f'{stem}-{suffix}.drl'
        data = path.read_text()
        if 'M48' not in data or not data.rstrip().endswith('M30') or count_drills(path) != count:
            raise ValueError(f'invalid {suffix} drill data/count')

def build(cli, package, root):
    work = root / package['name']
    work.mkdir()
    board = work / package['board'].name
    stage_package_board(package, board)
    run([str(cli), 'pcb', 'drc', '--refill-zones', '--save-board', '--format', 'json', '--severity-error', '--exit-code-violations', '--output', str(work / 'drc.json'), str(board)])
    output = work / 'gerber'
    output.mkdir()
    layers = layers_for(board, package['coupon_layer'])
    run([str(cli), 'pcb', 'export', 'gerbers', '--layers', ','.join(layers), '--no-protel-ext', '--subtract-soldermask', '--check-zones', '--output', str(output), str(board)])
    run([str(cli), 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute', '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'route', '--excellon-separate-th', '--output', str(output), str(board)])
    notes = ['# Fabricator Gerber package', '', f'Source: `{board.name}`.', 'Native Gerber X2, absolute millimetre coordinates, with matching Gerber job and Excellon drill data.', '', '## Layer mapping', '', *[f'- `{plot_filename(board, layer)}`: {layer}.' for layer in layers], '', f"PTH drill hits: {package['plated_drills']}; NPTH drill hits: {package['unplated_drills']}.", 'Both drill files are supplied; an empty file means no holes of that type.', 'Paste layers support optional stencil manufacture. Empty backside artwork is intentional when unused.', '', 'Use the Gerber job for the source stackup/thickness. Confirm finish, copper weight,', 'material, tolerances and any assembly requirements against the approved order.', 'This package provides bare-board fabrication data; it does not include an assembly BOM or placement file.']
    if package['coupon_layer']:
        notes += ['', f"{package['coupon_layer']} contains {package['cut_count']} internal coupon cut contours.", 'Edge.Cuts is the processing boundary. Confirm internal routing and panel support/tab strategy with the fabricator.']
    (output / 'PACKAGE.md').write_text('\n'.join(notes) + '\n')
    validate(output, package, layers)
    return output

def comparable(path):
    if path.suffix == '.gbrjob':
        data = json.loads(path.read_text())
        data.get('Header', {}).pop('CreationDate', None)
        return data
    return [line for line in normalized(path) if not line.startswith('%TF.CreationDate,')]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['export', 'audit'])
    parser.add_argument('design', type=Path)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--kicad-cli', type=Path)
    args = parser.parse_args()
    try:
        packages = discover_packages(args.design, 'gerber')
        cli = find_cli(args.kicad_cli)
        with tempfile.TemporaryDirectory(prefix='fabricator-export-') as temp:
            root = Path(temp)
            generated = {p['name']: build(cli, p, root) for p in packages}
            if args.mode == 'export':
                replace_directories(packages, generated, force=args.force, stale=stale_directories(packages), kind='gerber')
            else:
                for p in packages:
                    (old, new) = (p['output'], generated[p['name']])
                    if not old.is_dir() or {f.name for f in old.iterdir()} != {f.name for f in new.iterdir()}:
                        raise ValueError(f"{p['name']}: missing or stale Gerber file set")
                    for f in new.iterdir():
                        if comparable(f) != comparable(old / f.name):
                            raise ValueError(f"{p['name']}: stale {f.name}")
                if stale_directories(packages):
                    raise ValueError('stale supplier package directories')
            for p in packages:
                print(f"PASS [{p['name']}]: complete Gerber, job and drill package ({args.mode})")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f'ERROR: {error}')
        return 1
if __name__ == '__main__':
    raise SystemExit(main())
