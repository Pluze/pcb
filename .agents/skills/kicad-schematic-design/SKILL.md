---
name: kicad-schematic-design
description: Design, automate, and verify readable KiCad schematics from logical topology through functional layout, explicit wiring, circuit-as-code generation, ERC, and rendered review.
---

# KiCad Schematic Design

Use this skill for the complete schematic workflow. Logic, presentation, automation, and verification stay together because each stage constrains the next.

## 1. Establish electrical truth

- Translate the requirements into components, exact pins, named nets, supply conditions, and functional blocks before placement.
- Keep a version-controlled pin-level topology for generated work. It is the connectivity source of truth; the reviewed KiCad sheet is the presentation source of truth.
- Confirm consequential pin mappings and packages with `pcb-component-engineering` before claiming hardware correctness.

## 2. Use moderate functional decomposition

A simple one-sheet circuit should normally remain roughly two or three substantial modules. A module must perform a coherent function and contain its active device, bias/feedback parts, local decoupling, protection, and relevant connector path. Do not create modules for individual passives or split a small analog loop into labeled fragments.

Use labels only at real module interfaces, cross-sheet links, genuinely dense repeated networks, or conventional common power networks such as GND/VCC/VDD. Inside each module, show ordinary component-to-component topology with explicit wires. Place each interface label at the module edge after a visible wire stub. A reader should understand a module without chasing its internal nets elsewhere.

Do not turn a common power net into a page-spanning physical rail when that rail creates long detours, blocks feedback paths, or forces ambiguous crossings. Prefer a small number of local power symbols or compact labeled power branches. Keep each local branch visibly complete; the exception applies to the shared power plane, not to ordinary signal or feedback topology.

## 3. Place for human reading before wiring

- Use a consistent left-to-right or top-to-bottom power and signal flow. Keep power entry upstream and feedback beside the controlled stage.
- Orient connectors so pins face their circuitry. Align related pins, repeated channels, rows, columns, and text baselines to the grid.
- Reserve visible corridors for signal, feedback, supply, and return wiring. Use deliberate whitespace between modules but do not scatter a simple circuit across the page.
- Perform an unwired review: function, direction, polarity, port order, likely bends, text clearance, and whether placement alone communicates structure.

Derive the layout from the circuit rather than from a fixed template:

- Identify the dominant energy, signal, control, feedback, and return paths. Give each important path a readable visual spine, then arrange the spines in the causal order of the design.
- Put sources and inputs at the entry side of the sheet, controlled or transforming elements near the center of their function, and loads, outputs, or downstream interfaces at the exit side. Choose left-to-right or top-to-bottom per module and use it consistently.
- Keep local feedback and bias parts close to the device they govern. Place shunt parts perpendicular to the rail or node they serve when that makes their function immediately recognizable.
- Align directly interacting pins and parts before wiring. A straight functional relationship is preferable to a compact placement that requires several turns or hides causality.
- Show important current and return paths as continuous topology when they explain circuit behavior. Use local common-power symbols when a page-wide rail would add crossings or conceal the functional paths.
- Put external connectors near the boundary of their functional block, orient their pins toward the circuit, and place test points directly on the measured path or on a short perpendicular branch.
- Judge compactness by information density, not by minimum area. Preserve enough whitespace to separate functions, feedback loops, annotations, and crossing-free routing, but do not scatter a simple circuit into isolated islands.

Concept images or generated diagrams may be used as composition references for block proportion, whitespace, alignment, and information hierarchy. Never inherit their pin numbers, wires, junctions, or component topology without independently rebuilding them from the pin-level electrical model and passing schematic validation.

## 4. Draw explicit, unambiguous local topology

- Every wire leaves its pin in the natural outward direction for at least one schematic-grid unit before turning or joining.
- Connect only at exact transformed pin endpoints or intentional junctions. Never route through a symbol body or use a continuous line behind a two-terminal part.
- Keep different nets from coincident or parallel overlap. Avoid ambiguous crossings, near-touches, and stacked junctions.
- Trace connector pins independently. Source positive and return, boosted output and load return, and distinct power flags must never merge accidentally.
- Draw test points as short perpendicular branches or clear endpoint continuations.
- Keep reference/value text horizontal where practical and outside symbols and wires.

Reject text-on-wire, text-on-symbol, wire-through-symbol, junctions at graphical centers, bypassed divider/sense resistors, connector-pin shorts, supply/return crossings with a junction, and any local path that cannot be followed without labels.

## 5. Automate repeatably when useful

Separate:

- electrical model: components, exact parts, footprints, named nets, `REF.PIN` membership, hierarchy, reusable blocks;
- presentation model: position, orientation, port direction, text, module composition, lanes;
- KiCad data model: valid symbols, UUIDs, instances, wires, labels, junctions, and file structure.

Use `../kicad-konnect/scripts/schematic_topology_router.py` for placed symbols with explicit topology JSON. Dry-run before `--apply`. The router must reserve pin escapes, avoid component/text bounds, prevent different nets from sharing or crossing nodes, and fail without modifying the schematic when routing is unresolved. Change placement, module boundaries, lane constraints, or rip-up order rather than forcing a crossing or short.

Reserve every placed pin's outward escape corridor before routing any net, including pins whose nets will be routed later. Open a reserved corridor only to its owning routing unit. Never remove an already occupied node from the blocking set merely because the current pin or label wants to use it; report the conflict and change placement or routing instead. This prevents order-dependent shorts at another component's pin escape.

Treat a failed route as design feedback, not an invitation to repeat blind attempts:

1. Re-run the failed net without previously occupied routes. If it still fails, the symbol geometry, orientation, obstacle clearance, or imposed backbone is topologically infeasible; change the layout or constraint.
2. If it succeeds alone, identify the earlier route consuming the corridor. Change priority only when that matches circuit readability; otherwise move symbols or define a deliberate lane.
3. For GND/VCC/VDD and similar shared planes, consider local power symbols or compact labeled branches before creating a long physical tree.
4. Stop after the failure class is known. Make one reasoned design change, then re-run the full dry-run. Record new generic failure patterns in the router or this skill only after the remedy is validated.

Extracted reference architecture:

- From `circuit-synth`: explicit nets, circuit functions, hierarchy, reusable patterns, deterministic regeneration, source-reference synchronization, and hybrid code/KiCad refinement.
- From `kicad-sch-api`: exact format preservation, schematic-space transforms, 1.27 mm grid discipline, transformed pins, component bounds, connectivity tracing, hierarchy, and Manhattan obstacle routing. Use it as a backend only when it is an approved dependency.
- From `netlistsvg`: directed port graphs, stable component/port types, layered layout, configurable direction/spacing, crossing minimization, and separation of netlist, symbol appearance, and layout policy. Translate geometry back to real KiCad objects; SVG remains preview evidence only.

## 6. Verify before PCB synchronization

Run the repository validator for topology-driven designs:

```bash
python3 tools/pcbflow/kicad/scripts/validate_schematic_design.py \
  Designs/<name>/schematic_topology.json \
  --report /tmp/<name>-schematic-validation.json \
  --render Designs/<name>/assets/schematic.png
```

It checks endpoint ownership/existence, symbol overlap, dangling wires, unconnected pins, orphan items, named-net shorts, wire-through-symbol geometry, ERC, and creates a render.

Also compare important nets against the topology, inspect raw critical pin mappings, verify power flags, and recalculate regulator, current-set, divider, filter, and protection networks. Inspect renders at full-page and block scale for collisions, ambiguous junctions, excessive detours, vertical crowded values, inconsistent orientations, and unclear feedback or return paths.

When checking whether a wire crosses a symbol body, do not use a component bound that includes its outward pin strokes as though the whole rectangle were solid body geometry. Derive the body-side boundary from each transformed pin's exact endpoint, direction, and length first; otherwise legal routing beside IC pins and resistor leads becomes a false positive. Continue to treat a wire entering from the wrong side of an exact pin endpoint as a real geometry defect.

Keep generic rules and algorithms in this skill and its helpers. Store only dated results, circuit-specific calculations, exceptions, and unresolved risks in the design directory. Do not accept the schematic while any material connectivity, mapping, readability, or evidence gap is undisclosed.
