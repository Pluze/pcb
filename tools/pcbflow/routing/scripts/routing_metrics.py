#!/usr/bin/env python3
"""Summarize saved routing geometry for candidate comparison, independently of DRC."""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'kicad' / 'scripts'))
from manufacturing_discovery import extract_blocks, point


def metrics(board: Path) -> dict:
    text = board.read_text(encoding='utf-8')
    nets = defaultdict(lambda: {'segments': 0, 'length_mm': 0.0, 'widths_mm': set()})
    junctions = defaultdict(list)
    layers = Counter()
    non_45 = 0
    for segment in extract_blocks(text, 'segment'):
        start, end = point(segment, 'start'), point(segment, 'end')
        net_match = re.search(r'\(net\s+(?:"([^"]+)"|([^\s)]+))', segment)
        if not net_match:
            raise ValueError('segment has no readable net')
        net = net_match.group(1) or net_match.group(2)
        layer = re.search(r'\(layer\s+"([^"]+)"', segment).group(1)
        width = float(re.search(r'\(width\s+([^\s)]+)', segment).group(1))
        dx, dy = end[0] - start[0], end[1] - start[1]
        non_45 += int(min(abs(dx), abs(dy)) > 1e-5 and abs(abs(dx)-abs(dy)) > 1e-5)
        nets[net]['segments'] += 1
        nets[net]['length_mm'] += math.hypot(dx, dy)
        nets[net]['widths_mm'].add(width)
        layers[layer] += 1
        junctions[(net, layer, start)].append((dx, dy))
        junctions[(net, layer, end)].append((-dx, -dy))
    right_angles = 0
    for vectors in junctions.values():
        if len(vectors) != 2:
            continue
        a, b = vectors
        norm = math.hypot(*a) * math.hypot(*b)
        right_angles += int(norm > 0 and abs(a[0]*b[0]+a[1]*b[1]) / norm < 1e-5)
    for entry in nets.values():
        entry['length_mm'] = round(entry['length_mm'], 4)
        entry['widths_mm'] = sorted(entry['widths_mm'])
    return {
        'segments': sum(layers.values()), 'vias': len(extract_blocks(text, 'via')),
        'layers': dict(sorted(layers.items())), 'zones': len(extract_blocks(text, 'zone')),
        'length_mm': round(sum(n['length_mm'] for n in nets.values()), 4),
        'degree_two_right_angles': right_angles, 'non_45_segments': non_45,
        'nets': dict(sorted(nets.items())),
        'coverage': 'straight segment geometry; pad/T junction intent and electrical suitability require review',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    result = {'candidate': metrics(args.board)}
    if args.baseline:
        result['baseline'] = metrics(args.baseline)
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
