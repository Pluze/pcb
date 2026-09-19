#!/usr/bin/env python3
"""Read-only saved-design checks: native ERC, endpoint parity and parts inventory."""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from headless_pcb_review import find_kicad_cli, sha256
from manufacturing_discovery import extract_blocks


def pcb_components(text):
    """Use the existing native-block reader for KiCad 10 saved footprint fields."""
    result = {}
    for block in extract_blocks(text, 'footprint'):
        properties = {m[0]: json.loads('"' + m[1] + '"') for m in re.findall(r'\(property\s+"([^"]+)"\s+"((?:\\.|[^"\\])*)"', block)}
        ref = properties['Reference']
        if ref in result:
            raise ValueError(f'duplicate PCB reference: {ref}')
        pads = {}
        for pad in extract_blocks(block, 'pad'):
            number = re.match(r'\(pad\s+"([^"]*)"', pad)[1]
            if not number:
                continue
            match = re.search(r'\(net\s+"((?:\\.|[^"\\])*)"\)', pad)
            net = json.loads('"' + match[1] + '"') if match else ''
            if '(net ' in pad and not match:
                raise ValueError('endpoint inspection requires KiCad 10 named-net format')
            if number in pads and pads[number] != net:
                raise ValueError(f'duplicate pad {ref}.{number} has conflicting nets')
            pads[number] = net
        result[ref] = {'value': properties.get('Value', ''),
                       'footprint': re.match(r'\(footprint\s+"([^"]+)"', block)[1], 'pads': pads}
    return result


def schematic_components(root):
    result = {}
    for component in root.findall('components/comp'):
        if component.find("property[@name='exclude_from_board']") is not None:
            continue
        ref = component.attrib['ref']
        if ref in result:
            raise ValueError(f'duplicate schematic reference: {ref}')
        fields = {f.attrib['name']: f.text or '' for f in component.findall('fields/field')}
        result[ref] = {'value': component.findtext('value', ''), 'footprint': component.findtext('footprint', ''),
                       'mpn': fields.get('MPN', ''), 'manufacturer': fields.get('Manufacturer', ''),
                       'dnp': component.find("property[@name='dnp']") is not None, 'pads': {}}
    for net in root.findall('nets/net'):
        for pin in net.findall('node'):
            ref = pin.attrib['ref']
            if ref in result:
                result[ref]['pads'][pin.attrib['pin']] = net.attrib['name']
    return result


def groups(components):
    nets = {}
    for ref, component in components.items():
        for pin, net in component['pads'].items():
            endpoint = ref + '.' + pin
            # An unnamed pad is independent, never joined to every other empty pad.
            nets.setdefault(net or ('unconnected:' + endpoint), set()).add(endpoint)
    return {endpoint: peers for peers in nets.values() for endpoint in peers}


def compare(schematic, board):
    """Compare endpoint partitions, independent of generated net names/aliases."""
    findings = []
    for ref in sorted(set(schematic) | set(board)):
        if ref not in schematic or ref not in board:
            findings.append({'type': 'component_mismatch', 'reference': ref, 'missing_from': 'schematic' if ref not in schematic else 'pcb'})
            continue
        for field in ('value', 'footprint'):
            if schematic[ref][field] != board[ref][field]:
                findings.append({'type': field + '_mismatch', 'reference': ref,
                                 'schematic': schematic[ref][field], 'pcb': board[ref][field]})
    expected, actual = groups(schematic), groups(board)
    for endpoint, peers in sorted(expected.items()):
        if endpoint not in actual or peers != actual[endpoint]:
            findings.append({'type': 'connectivity_mismatch', 'endpoint': endpoint,
                             'schematic': sorted(peers), 'pcb': sorted(actual.get(endpoint, set()))})
    for endpoint, peers in sorted(actual.items()):
        if endpoint not in expected and len(peers) > 1:
            findings.append({'type': 'extra_connected_pad', 'endpoint': endpoint, 'pcb': sorted(peers)})
    return findings


def check(design, workspace, cli):
    stem = design / design.name
    board, schematic = stem.with_suffix('.kicad_pcb'), stem.with_suffix('.kicad_sch')
    # Native read-only export resolves hierarchical sheets and local library context in place.
    inputs = sorted(set(design.rglob('*.kicad_sch')) | set(design.glob('*.kicad_pro')) | set(design.glob('*.kicad_dru')) | {board})
    hashes = {p: sha256(p) for p in inputs}
    output = workspace / design.name
    output.mkdir()
    erc, netlist = output / 'erc.json', output / 'netlist.xml'
    commands = [(['sch', 'erc', '--format', 'json', '--output', str(erc), str(schematic)], 'erc'),
                (['sch', 'export', 'netlist', '--format', 'kicadxml', '--output', str(netlist), str(schematic)], 'netlist')]
    for args, phase in commands:
        process = subprocess.run([str(cli), *args], capture_output=True, text=True, timeout=120)
        (output / (phase + '.log')).write_text(process.stdout + process.stderr)
        if process.returncode:
            raise RuntimeError(f'{design.name}: {phase} failed; inspect {output / (phase + ".log")}')
    erc_data = json.loads(erc.read_text())
    violations = [v for sheet in erc_data['sheets'] for v in sheet['violations']]
    counts = Counter(v['severity'] for v in violations)
    components = schematic_components(ET.parse(netlist).getroot())
    footprints = pcb_components(board.read_text())
    findings = compare(components, footprints) if components else []
    inventory = output / 'parts.csv'
    with inventory.open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Reference', 'Value', 'Footprint', 'MPN', 'Manufacturer', 'DNP'])
        for ref, part in sorted(components.items()):
            writer.writerow([ref, part['value'], part['footprint'], part['mpn'], part['manufacturer'], part['dnp']])
    missing = [ref for ref, part in components.items() if not part['dnp'] and not part['mpn']]
    unchanged = all(sha256(p) == digest for p, digest in hashes.items())
    result = {'design': design.name, 'status': 'fail' if findings or counts.get('error') or not unchanged else 'pass',
              'erc': {'errors': counts.get('error', 0), 'warnings': counts.get('warning', 0)},
              'parity': {'status': ('fail' if findings else 'pass') if components else 'not_applicable_empty_schematic',
                         'components': len(components), 'endpoints': len(groups(components)), 'findings': len(findings)},
              'parts': {'missing_mpn': missing, 'unique_mpn': len({p['mpn'] for p in components.values() if p['mpn']}),
                        'procurement_catalog_present': (design / 'BOM.csv').is_file(),
                        'scope': 'schematic fields only; catalog matching, datasheets and stock remain separate'},
              'source_unchanged': unchanged, 'artifacts': {'report': str(output / 'findings.json'), 'inventory': str(inventory)}}
    (output / 'findings.json').write_text(json.dumps({'summary': result, 'findings': findings, 'inputs': {str(p.relative_to(design)): h for p, h in hashes.items()}}, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('Designs'))
    parser.add_argument('--design', action='append', default=[])
    parser.add_argument('--kicad-cli', type=Path)
    args = parser.parse_args()
    workspace = Path(tempfile.mkdtemp(prefix='pcb-design-check-'))
    try:
        designs = [p for p in sorted(args.root.resolve().iterdir()) if (p / (p.name + '.kicad_pcb')).is_file()]
        if args.design:
            names = set(args.design)
            missing = names - {p.name for p in designs}
            if missing:
                raise ValueError('unknown designs: ' + ', '.join(sorted(missing)))
            designs = [p for p in designs if p.name in names]
        if not designs:
            raise ValueError('no saved designs found')
        results = [check(d, workspace, find_kicad_cli(args.kicad_cli)) for d in designs]
        result = {'status': 'pass' if all(r['status'] == 'pass' for r in results) else 'fail',
                  'checks': results, 'details': str(workspace)}
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        result = {'status': 'fail', 'error': str(error), 'details': str(workspace)}
    print(json.dumps(result, separators=(',', ':')))
    return 0 if result['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
