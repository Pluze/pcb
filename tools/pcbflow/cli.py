#!/usr/bin/env python3
"""Public PCB workflow CLI. Dispatch existing engines; do not duplicate their algorithms."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

TOOL_ROOT = Path(__file__).resolve().parent
REPOSITORY = TOOL_ROOT.parent.parent
ENGINES = {
    'workflow': ('kicad', 'pcb_workflow.py'),
    'design-check': ('kicad', 'check_design.py'),
    'review-board': ('kicad', 'headless_pcb_review.py'),
    'route-candidate': ('routing', 'freerouting_candidate.py'),
    'routing-metrics': ('routing', 'routing_metrics.py'),
    'manufacturing': ('kicad', 'manage_manufacturing_outputs.py'),
    'pour-variants': ('kicad', 'generate_copper_pour_variants.py'),
    'export-u4': ('kicad', 'export_circuitpro_u4_packages.py'),
    'export-gerber': ('kicad', 'export_fabricator_gerbers.py'),
    'export-mask': ('kicad', 'export_kapton_lightburn_templates.py'),
    'validate-u4': ('kicad', 'validate_circuitpro_u4_package.py'),
    'schematic-route': ('kicad', 'schematic_topology_router.py'),
    'schematic-validate': ('kicad', 'validate_schematic_design.py'),
    'contact-board': ('routing', 'generate_circular_contact_board.py'),
    'contact-panel': ('routing', 'generate_circular_contact_panel.py'),
    'konnect': ('kicad', 'konnect_mcp_client.py'),
    'growth': ('repository', 'check_repository_growth.py'),
    'benchmark': ('kicad', 'benchmark_pcb_workflow.py'),
}


def engine(name: str) -> Path:
    owner, filename = ENGINES[name]
    return TOOL_ROOT / owner / 'scripts' / filename


def design_board(root: Path, name: str) -> Path:
    if Path(name).name != name or name in ('.', '..'):
        raise ValueError('design must be one directory name under Designs')
    board = root / 'Designs' / name / f'{name}.kicad_pcb'
    if not board.is_file():
        raise ValueError(f'no saved board for design {name}')
    return board


def find_runtime(explicit, environment, candidates, probe=None):
    """Explicit paths fail loudly; automatic discovery never installs dependencies."""
    requested = explicit or os.environ.get(environment)
    paths = [Path(requested).expanduser()] if requested else [Path(p) for p in candidates if p]
    for path in paths:
        if path.is_file() and (probe is None or probe(path)):
            return path.resolve()
    raise ValueError(f'{environment} unavailable; pass an explicit executable/file path')


def java_compatible(path):
    try:
        result = subprocess.run([str(path), '-version'], capture_output=True, text=True, timeout=10)
        match = re.search(r'version "(\d+)', result.stderr + result.stdout)
        return result.returncode == 0 and match is not None and int(match[1]) >= 25
    except (OSError, subprocess.TimeoutExpired):
        return False


def routing_runtime(args):
    java = find_runtime(getattr(args, 'java', None), 'PCB_JAVA', [
        *sorted(Path('/opt/homebrew/opt').glob('openjdk*/bin/java'), reverse=True), shutil.which('java')
    ], java_compatible)
    python = find_runtime(getattr(args, 'kicad_python', None), 'PCB_KICAD_PYTHON', [
        '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',
        shutil.which('python3')
    ])
    jar = find_runtime(getattr(args, 'jar', None), 'FREEROUTING_JAR', sorted(
        (Path.home() / 'Documents/KiCad').glob('*/3rdparty/plugins/app_freerouting_kicad-plugin/jar/*.jar'), reverse=True))
    return {'java': str(java), 'kicad_python': str(python), 'jar': str(jar)}


def parser():
    p = argparse.ArgumentParser(description='PCB tools for engineers and agents: saved design → clean routing candidate → review → adopt → manufacturing build.')
    p.add_argument('--root', type=Path, default=REPOSITORY, help='PCB repository (default: this checkout)')
    p.add_argument('--json', action='store_true', help='machine-readable receipts instead of human summaries')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='list saved designs and their source files')
    sub.add_parser('gui', help='open the external desktop workflow window')
    check = sub.add_parser('check', help='check saved ERC, schematic/PCB endpoint parity and parts fields')
    check.add_argument('--design', action='append', default=[])
    sub.add_parser('doctor', help='check installed routing dependencies without installing anything')
    sub.add_parser('tools', help='list advanced tools; use tool NAME --help for their contracts')
    advanced = sub.add_parser('tool', help='invoke an advanced tool by stable name', add_help=False)
    advanced.add_argument('name', choices=sorted(ENGINES))
    advanced.add_argument('arguments', nargs=argparse.REMAINDER)
    for name, description in [('review', 'check saved PCB rules/connectivity and render; does not modify sources'),
                              ('schematic', 'validate an existing topology-backed schematic'),
                              ('build', 'derive pours and refresh manufacturing outputs from accepted routing'),
                              ('audit', 'audit existing manufacturing outputs without replacing them'),
                              ('verify', 'check repository and manufacturing readiness')]:
        item = sub.add_parser(name, help=description)
        item.add_argument('--design', action='append', default=[], help='repeat to restrict scope')
        item.add_argument('--no-cache', action='store_true')
        item.add_argument('--dry-run', action='store_true', help='show the planned phases only')
        if name == 'review':
            item.add_argument('--board', type=Path, help='review any saved board with its sibling project')
    route = sub.add_parser('route', help='clear old routing/pours in a copy, autoroute, finish and independently validate')
    select = route.add_mutually_exclusive_group(required=True)
    select.add_argument('--design')
    select.add_argument('--board', type=Path)
    for name in ('java', 'jar', 'kicad-python'):
        route.add_argument('--' + name, type=Path)
    route.add_argument('--timeout', type=int, default=120)
    route.add_argument('--passes', type=int, default=30)
    route.add_argument('--dry-run', action='store_true')
    finish = sub.add_parser('finish', help='compose saved-design checks → clean autoroute → adopt → three-format build → verify')
    finish.add_argument('--design', required=True)
    finish.add_argument('--candidate-only', action='store_true', help='stop after independent candidate review for human editing/inspection')
    finish.add_argument('--dry-run', action='store_true')
    for name in ('java', 'jar', 'kicad-python'):
        finish.add_argument('--' + name, type=Path)
    finish.add_argument('--timeout', type=int, default=120)
    finish.add_argument('--passes', type=int, default=30)
    adopt = sub.add_parser('adopt' , help='revalidate and adopt a reviewed routing candidate; preserve a source backup')
    adopt.add_argument('--design', required=True)
    adopt.add_argument('--receipt', type=Path, required=True, help='route workspace receipt.json (candidate may have been repaired)')
    return p


def invoke(command, root):
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    try:
        receipt = json.loads(result.stdout)
    except ValueError:
        # Advanced engines may have their own CLI text rather than a JSON receipt.
        receipt = {'status': 'pass' if result.returncode == 0 else 'fail',
                   'output': result.stdout.strip(), 'diagnostic': result.stderr.strip()}
    receipt.setdefault('status', 'pass' if result.returncode == 0 else 'fail')
    if result.returncode:
        receipt['status'] = 'fail'
    return receipt, result.returncode or (2 if receipt['status'] == 'fail' else 0)


def adopt_candidate(root, name, receipt_path):
    """Adoption is explicit and rechecks current files, never trusting a stale pass."""
    sys.path.insert(0, str(engine('review-board').parent))
    sys.path.insert(0, str(engine('route-candidate').parent))
    from headless_pcb_review import review, find_kicad_cli, sha256
    from freerouting_candidate import geometry_hash
    from routing_metrics import metrics
    source = design_board(root, name)
    prior = json.loads(receipt_path.read_text())
    candidate = Path(prior['candidate']).resolve()
    if candidate == source.resolve():
        raise ValueError('candidate must be isolated from the source')
    for filename, digest in prior['inputs'].items():
        if Path(filename).name != filename or sha256(source.parent / filename) != digest:
            raise ValueError('source changed since routing; regenerate or reconcile before adoption')
    for suffix in ('.kicad_pro', '.kicad_dru'):
        original, staged = source.with_suffix(suffix), candidate.with_suffix(suffix)
        if original.exists() != staged.exists() or (original.exists() and sha256(original) != sha256(staged)):
            raise ValueError('candidate project rules differ from source rules')
    if geometry_hash(candidate.read_text()) != prior['geometry_sha256']:
        raise ValueError('candidate changed assembly/mechanics; reconcile those separately')
    routing = metrics(candidate)
    if routing['vias'] or routing['zones'] or set(routing['layers']) != {'F.Cu'}:
        raise ValueError('adoption requires routed front-only, zero-via, no-pour geometry')
    if any(w < 0.25 for n in routing['nets'].values() for w in n['widths_mm']):
        raise ValueError('candidate violates the default 0.25 mm routing floor')
    workspace = Path(tempfile.mkdtemp(prefix='pcb-adopt-'))
    evidence = review(candidate, workspace / 'review', find_kicad_cli(None))
    if evidence['status'] != 'pass':
        return {'status': 'fail', 'review': evidence, 'source_unchanged': True}, 2
    backup = workspace / source.name
    shutil.copy2(source, backup)
    # Same-filesystem replace avoids a partially written source board.
    fd, temporary = tempfile.mkstemp(prefix='.' + source.stem, suffix='.tmp', dir=source.parent)
    os.close(fd)
    try:
        shutil.copyfile(candidate, temporary)
        os.replace(temporary, source)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return {'status': 'pass', 'adopted': str(source), 'backup': str(backup),
            'routing': routing, 'review': evidence, 'next': 'pcb build --design ' + name}, 0


def finish_design(args, root):
    """A fixed conservative recipe covers common mixed human/agent handoffs.

    This is not a workflow language: existing validators retain their decisions.
    Failures stop the recipe and retain the current phase/evidence for local repair.
    """
    board = design_board(root, args.design)
    phases = ['design-check', 'clean-route-and-review']
    if not args.candidate_only:
        phases += ['adopt', 'build-u4-mask-gerber', 'verify']
    if args.dry_run:
        return {'status': 'plan', 'designs': [args.design], 'phases': phases,
                'scope': 'clear tracks/vias/pours in snapshot; retain pads, placement and outline'}, 0
    workspace = Path(tempfile.mkdtemp(prefix='pcb-finish-'))
    outcomes = {}
    def save(name, receipt, code):
        outcomes[name] = receipt
        (workspace / (name + '.json')).write_text(json.dumps(receipt, indent=2) + '\n')
        return code == 0 and receipt.get('status') == 'pass'
    def summary(status, failed=None):
        result = {'status': status, 'designs': [args.design], 'details': str(workspace),
                  'phases': {key: value.get('status', 'unknown') for key, value in outcomes.items()},
                  'coverage': 'saved-file electrical/geometric/manufacturing checks; visual and bench acceptance remain explicit'}
        if failed:
            result['failed_phase'] = failed
            result['error'] = outcomes[failed].get('error', 'inspect phase receipt; no unchanged automatic retry')
        route = outcomes.get('clean-route-and-review', {})
        if 'candidate' in route:
            result['candidate'] = route['candidate']
        return result, 0 if status == 'pass' else 2
    print('Checking saved schematic, PCB parity and parts fields…', file=sys.stderr, flush=True)
    evidence, code = dispatch(argparse.Namespace(root=root, command='check', design=[args.design]))
    if not save('design-check', evidence, code):
        return summary('fail', 'design-check')
    print('Clearing old copper and routing a candidate…', file=sys.stderr, flush=True)
    route_args = argparse.Namespace(**{**vars(args), 'command': 'route', 'board': None})
    receipt, code = dispatch(route_args)
    if not save('clean-route-and-review', receipt, code):
        return summary('fail', 'clean-route-and-review')
    if args.candidate_only:
        return summary('pass')
    print('Revalidating and adopting the route…', file=sys.stderr, flush=True)
    receipt, code = adopt_candidate(root, args.design, Path(receipt['details']) / 'receipt.json')
    if not save('adopt', receipt, code):
        return summary('fail', 'adopt')
    for command, label in [('build', 'build-u4-mask-gerber'), ('verify', 'verify')]:
        print('Running ' + label + '…', file=sys.stderr, flush=True)
        step = argparse.Namespace(root=root, command=command, design=[args.design], no_cache=False, dry_run=False)
        receipt, code = dispatch(step)
        if not save(label, receipt, code):
            return summary('fail', label)
    return summary('pass')


def dispatch(args):
    root = args.root.expanduser().resolve()
    if args.command == 'gui':
        python = find_runtime(None, 'PCB_KICAD_PYTHON', [
            '/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3',
            sys.executable,
        ])
        env = {**os.environ, 'PYTHONPATH': str(TOOL_ROOT.parent), 'PYTHONDONTWRITEBYTECODE': '1'}
        code = subprocess.run([str(python), '-m', 'pcbflow.gui', '--root', str(root)], env=env).returncode
        return {'status': 'pass' if code == 0 else 'fail', 'gui': 'closed'}, code
    if args.command == 'finish':
        return finish_design(args, root)
    if args.command == 'check':
        command = [sys.executable, str(engine('design-check')), '--root', str(root / 'Designs')]
        for name in args.design:
            command += ['--design', name]
        return invoke(command, root)
    if args.command == 'tools':
        return {'status': 'pass', 'tools': sorted(ENGINES)}, 0
    if args.command == 'list':
        designs = [p.parent.name for p in sorted((root / 'Designs').glob('*/*.kicad_pcb'))
                   if p.stem == p.parent.name]
        return {'status': 'pass', 'designs': designs}, 0
    if args.command == 'doctor':
        runtime = routing_runtime(args)
        result = subprocess.run([runtime['kicad_python'], '-c', 'import pcbnew; print(pcbnew.GetBuildVersion())'],
                                capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise ValueError('selected KiCad Python cannot import pcbnew')
        return {'status': 'pass', 'routing_runtime': runtime, 'kicad_version': result.stdout.strip()}, 0
    if args.command == 'tool':
        return invoke([sys.executable, str(engine(args.name)), *args.arguments], root)
    if args.command == 'adopt':
        return adopt_candidate(root, args.design, args.receipt.expanduser().resolve())
    if args.command == 'route':
        board = design_board(root, args.design) if args.design else args.board.expanduser().resolve()
        runtime = routing_runtime(args)
        command = [sys.executable, str(engine('route-candidate')), str(board)]
        for name, value in runtime.items():
            command += ['--' + name.replace('_', '-'), value]
        command += ['--timeout', str(args.timeout), '--passes', str(args.passes)]
        if args.dry_run:
            return {'status': 'plan', 'command': command, 'source_mutation': False,
                    'phases': ['snapshot', 'clear-old-copper', 'freerouting', 'finish', 'independent-review']}, 0
        return invoke(command, root)
    if args.command == 'review' and args.board:
        if args.design:
            raise ValueError('choose --board or --design, not both')
        command = [sys.executable, str(engine('review-board')), str(args.board.expanduser().resolve())]
        return ({'status': 'plan', 'command': command}, 0) if args.dry_run else invoke(command, root)
    goal = {'review': 'pcb-review', 'schematic': 'schematic-validate',
            'build': 'manufacturing-refresh', 'audit': 'validate', 'verify': 'release-ready'}[args.command]
    command = [sys.executable, str(engine('workflow')), 'plan' if args.dry_run else goal, '--root', str(root)]
    if args.dry_run:
        command += ['--for-goal', goal]
    if args.command == 'build':
        command += ['--apply']
    if args.no_cache:
        command += ['--no-cache']
    for name in args.design:
        command += ['--design', name]
    return invoke(command, root)


def display(receipt, machine):
    if machine:
        print(json.dumps(receipt, separators=(',', ':'), sort_keys=True))
        return
    print(receipt.get('status', 'unknown').upper())
    for name in ('error', 'diagnostic', 'output'):
        if receipt.get(name):
            print(receipt[name])
    for name in ('designs', 'tools'):
        for value in receipt.get(name, []):
            print('  ' + value)
    for item in receipt.get('checks', []):
        print(item['design'] + ': ' + item['status'])
        print('  ERC: ' + json.dumps(item['erc']) + '; parity: ' + json.dumps(item['parity']))
        missing = item['parts']['missing_mpn']
        print('  Schematic MPN fields missing: ' + (', '.join(missing) if missing else 'none'))
    for name in ('phases', 'drc', 'routing', 'routing_runtime'):
        if name in receipt:
            print(name + ': ' + json.dumps(receipt[name], ensure_ascii=False))
    for name in ('candidate', 'adopted', 'backup', 'details', 'log_dir', 'next'):
        if name in receipt:
            print(name + ': ' + (receipt[name] if isinstance(receipt[name], str) else json.dumps(receipt[name])))
    for review in receipt.get('reviews', {}).values():
        print(review['board'] + ': ' + review['status'])
        for key, path in review.get('artifacts', {}).items():
            print('  ' + key + ': ' + path)
    for key, path in receipt.get('artifacts', {}).items():
        print(key + ': ' + path)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(argv or ['--help'])
    try:
        receipt, code = dispatch(args)
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        receipt, code = {'status': 'fail', 'error': str(error)}, 2
    display(receipt, args.json)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
