"""Human-facing summaries of workflow evidence; raw receipts remain available."""
from pathlib import Path

PHASES = {
    'design-check': 'Schematic, PCB parity and parts check',
    'clean-route-and-review': 'Routing and independent checks',
    'adopt': 'Apply reviewed routing',
    'build-u4-mask-gerber': 'Production files',
    'verify': 'Delivery verification',
    'design-contract': 'Project files',
    'manufacturing-export': 'Generate production files',
    'manufacturing-audit': 'Check production files',
    'repository-growth': 'Repository hygiene',
    'diff-check': 'File formatting',
}
RUNNING = {
    'review': 'Checking board connectivity and design rules…',
    'route': 'Creating and checking a new routing candidate…',
    'finish': 'Completing the saved design…',
    'build': 'Building U4, LightBurn DXF and Gerber packages…',
    'verify': 'Checking the current delivery…',
    'adopt': 'Rechecking and applying the reviewed route…',
}
NEXT = {
    'review': 'Open the board preview and inspect placement, copper and labels.',
    'route': 'Inspect the candidate preview. Apply reviewed route when satisfied, then Build production files.',
    'finish': 'Inspect the final preview and production packages. Reopen the updated board in KiCad.',
    'build': 'Open production files and choose the package for your manufacturing process.',
    'verify': 'Review the production packages and confirm the manufacturing order parameters.',
    'adopt': 'Reopen the updated board in KiCad, then Build to refresh all production files.',
}


def objects(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from objects(item)
    elif isinstance(value, list):
        for item in value:
            yield from objects(item)


def phase_label(name):
    if name.startswith('pcb-review-'):
        return 'Board checks: ' + name[len('pcb-review-'):].replace('_', ' ')
    return PHASES.get(name, name.replace('-', ' ').capitalize())


def summarize(command, result, evidence=(), code=0):
    """Only summarize measured fields; missing evidence is never a zero count."""
    passed = code == 0 and result.get('status') == 'pass'
    lines, seen, warnings = [], set(), 0
    for item in objects([result, *evidence]):
        parity = item.get('parity')
        if isinstance(parity, dict):
            label = item.get('design', 'Design').replace('_', ' ')
            lines.append(f"{label}: schematic/PCB agreement — {parity['status'].replace('_', ' ')}")
            missing = item.get('parts', {}).get('missing_mpn', [])
            if missing:
                warnings += len(missing)
                lines.append(f"  Parts without schematic MPN fields: {', '.join(missing)}")
        drc = item.get('drc')
        if isinstance(drc, dict) and 'unconnected' in drc:
            identity = item.get('artifacts', {}).get('drc') or item.get('board') or str(drc)
            if identity in seen:
                continue
            seen.add(identity)
            severities = drc.get('severities', {})
            count = severities.get('warning', 0)
            warnings += count
            lines.append(f"Board checks: {severities.get('error', 0)} errors · {drc['unconnected']} unconnected · {count} warnings")
            for category, count in drc.get('types', {}).items():
                label = 'Footprints differ from installed library' if category == 'lib_footprint_mismatch' else category.replace('_', ' ').capitalize()
                lines.append(f'  {label}: {count}')
        routing = item.get('routing')
        if isinstance(routing, dict) and 'length_mm' in routing:
            line = f"Routing: {routing['length_mm']:.2f} mm · {routing['segments']} segments · {routing['vias']} vias"
            if line not in lines:
                lines.append(line)
    for phase, state in result.get('phases', {}).items():
        label = {'pass': 'Completed', 'cached': 'Verified — unchanged', 'fail': 'Needs attention'}.get(state, state)
        lines.append(f'{phase_label(phase)}: {label}')
    title = ('Completed with warnings' if warnings else 'Completed') if passed else 'Needs attention'
    if not passed:
        if result.get('failed_phase'):
            lines.insert(0, 'Stopped at: ' + phase_label(result['failed_phase']))
        error = result.get('error')
        if error:
            lines.append('Issue: ' + str(error).splitlines()[0][:240])
        suggestion = 'Open the check report or technical details, correct the reported issue, then run this step again.'
    else:
        suggestion = NEXT[command[0]]
        if command[0] == 'finish' and '--candidate-only' in command:
            suggestion = NEXT['route']
        if warnings:
            suggestion = 'Review the warnings in the check report. ' + suggestion
    if not lines:
        lines.append('The requested operation completed.' if passed else 'The operation could not complete.')
    return title, '\n'.join(lines) + '\n\nNext step\n' + suggestion


def artifact_label(path):
    path = Path(path)
    if path.is_dir():
        return {'u4': 'U4 machine files', 'lightburn': 'LightBurn mask templates',
                'gerber': 'Fabricator Gerber package'}.get(path.name, 'Supporting files')
    kind = {'.png': 'Board preview', '.svg': 'Vector preview', '.kicad_pcb': 'PCB file',
            '.json': 'Check report'}.get(path.suffix, 'Result')
    return f'{kind} — {path.name}'
