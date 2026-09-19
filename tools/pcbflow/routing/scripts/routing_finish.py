"""Bounded geometry finishing for disposable route candidates; requires subsequent DRC."""
import math
import re
import uuid
from collections import defaultdict
from manufacturing_discovery import extract_blocks, point

def finish(text: str, minimum_width: float = 0.25, setback: float = 0.2) -> tuple[str, dict]:
    """Apply one width-floor/bevel pass; the caller validates the resulting board.

    A degree-two endpoint is a bend. Higher-degree junctions retain their original
    topology. Limiting each trim to one third leaves room at both ends of a segment.
    """
    blocks = extract_blocks(text, 'segment')
    junctions = defaultdict(list)
    widths = []
    widened = 0
    for (index, block) in enumerate(blocks):
        width = float(re.search('\\(width ([\\d.]+)\\)', block)[1])
        if width < minimum_width:
            blocks[index] = re.sub('\\(width [\\d.]+\\)', f'(width {minimum_width:g})', block)
            widened += 1
        widths.append(max(width, minimum_width))
        net = re.search('\\(net\\s+("[^"]*"|[^)\\s]+)\\)', block)[1]
        layer = re.search('\\(layer "([^"]+)"\\)', block)[1]
        (a, b) = (point(block, 'start'), point(block, 'end'))
        for (role, here, other) in [('start', a, b), ('end', b, a)]:
            junctions[net, layer, here].append((index, role, other))
    additions = []
    for ((net, layer, vertex), neighbors) in junctions.items():
        if len(neighbors) != 2:
            continue
        vectors = [(other[0] - vertex[0], other[1] - vertex[1]) for (_, _, other) in neighbors]
        lengths = [math.hypot(*v) for v in vectors]
        if not min(lengths) or abs(sum((a * b for (a, b) in zip(*vectors)))) > 1e-07 * math.prod(lengths):
            continue
        distance = min(setback, min(lengths) / 3)
        ends = []
        for ((index, role, _), vector, length) in zip(neighbors, vectors, lengths):
            end = tuple((round(vertex[k] + vector[k] * distance / length, 6) for k in (0, 1)))
            ends.append(end)
            blocks[index] = re.sub('\\(' + role + '\\s+[-\\d.]+\\s+[-\\d.]+\\)', f'({role} {end[0]:.6f} {end[1]:.6f})', blocks[index])
        (a, b) = ends
        width = min((widths[n[0]] for n in neighbors))
        additions.append(f'(segment (start {a[0]:.6f} {a[1]:.6f}) (end {b[0]:.6f} {b[1]:.6f}) (width {width:g}) (layer "{layer}") (net {net}) (uuid "{uuid.uuid4()}"))')
    for (old, new) in zip(extract_blocks(text, 'segment'), blocks):
        text = text.replace(old, new, 1)
    index = text.rfind(')')
    text = text[:index] + '\n'.join(additions) + '\n' + text[index:]
    return (text, {'widened_segments': widened, 'beveled_degree_two_corners': len(additions)})
