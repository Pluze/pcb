# Design Directory Instructions

Each immediate child of `Designs/` is one self-contained hardware design.

## Required Contents

- A meaningful, stable directory and KiCad project name; never use placeholders such as `test1`.
- Matching `.kicad_pro`, `.kicad_sch`, and `.kicad_pcb` stems.
- `README.md` describing purpose, inputs, assumptions, component strategy, and fabrication intent.
- `VALIDATION.md` recording dated ERC, DRC, connectivity, routing, and visual checks.
- `assets/` for intentional previews or reference-facing documents.
- Optional `.konnect/project.json` for design-specific preferences that should survive between sessions.

## Design Rules

- Verify symbol pin numbers, footprint pad numbers, polarity, connector orientation, and package selection against authoritative data.
- Preserve the reference's functional relationships and readable visual organization; do not preserve apparent mistakes.
- Complete the logical partitioning before drawing wires. Arrange symbols by functional block and by power/signal/feedback flow, orient related pins toward one another, align symbols and ports to the schematic grid, and reserve clear corridors for wiring and annotations.
- For a small single-sheet circuit, show the complete local topology with explicit orthogonal wires, including supply and return trunks. Do not substitute a collection of repeated net labels for visible connectivity.
- A small circuit may be divided into a few coherent functional modules when each module is internally complete and independently understandable. Use net labels only at meaningful module boundaries for shared power, return, or named inter-module signals. Do not split a simple circuit into one-component fragments, and do not place the same label on every pin inside a module.
- Choose the smallest number of modules that materially improves readability. Each module must keep its active device, bias/feedback parts, local decoupling, protection, and relevant connector path visibly wired together; an engineer must understand the module without following internal labels elsewhere.
- Every wire must leave its symbol pin in the pin's outward direction for at least one standard grid unit before turning or joining a trunk. Avoid coincident or visually overlapping nets, minimize bends, and keep wires clear of symbols and annotations.
- A wire may terminate or join only at the exact electrical endpoint of a symbol pin or at an intentional wire junction. Never route a wire through a resistor, capacitor, IC, connector, test-point, or other symbol body to imply connectivity; the path must visibly enter and leave through the correct pins.
- Keep connector pins electrically distinct unless the circuit contract explicitly requires a short. In particular, independently trace every power-input pin and every `PWR_FLAG` to its intended rail before accepting the drawing; a positive-input flag and a return flag must never share a connected wire path.
- Draw test points as short, unambiguous branches from the measured node. Keep the branch, test-point symbol, reference, value, and nearby component annotations clear of one another and of the main signal path.
- Place reference/value text only after symbol placement and planned routing are readable. Keep text horizontal where practical, unobscured, and outside symbol bodies, pins, and wires.
- Require a pre-wiring layout review and a post-wiring rendered visual review at both full-page and block-scale zoom. An electrically valid but visually ambiguous or crowded schematic does not pass.
- The post-wiring review must explicitly reject text-on-wire, text-on-symbol, wire-through-symbol, a junction at a symbol's graphical center, connector-pin shorts, power/return rail crossings, and any component whose two-terminal conduction path cannot be followed through its two actual pins.
- For a generated or script-routed schematic, keep a version-controlled pin-level topology contract beside the KiCad project. Treat that contract as the connectivity source of truth and the reviewed KiCad sheet as the presentation source of truth. Validate both directions after generation so hand edits cannot silently diverge from the declared nets.
- Prefer a maintained structured KiCad schematic API or the repository's Konnect interface over ad-hoc S-expression rewriting. Generation must preserve valid KiCad formatting, grid alignment, UUIDs and instance metadata, and must fail atomically when a route or pin mapping cannot be proven.
- Keep designators upright, unobscured, inside the board, and clear of pads and exposed copper.
- Optimize component placement and orientation before routing.
- For single-sided prototypes, begin with a zero-via budget, use wide practical traces, and prefer a documented zero-ohm jumper over a via when a crossover is unavoidable.
- Before a full reroute, close the PCB editor, remove old routing from the candidate, verify zero stale segments/vias/zones as appropriate, and export a fresh empty-wiring DSN.

## Completion Evidence

Keep `VALIDATION.md` as a compact snapshot of current reproducible results and concrete unresolved exceptions, not a chronological log. Record actual counts instead of qualitative claims: ERC/DRC results, layer use, routing and drill counts, and remaining waivers. Replace superseded evidence rather than appending process history. Inspect both schematic and board renders after the final edit.

Keep only design-specific facts and evidence inside an individual design directory. If a rule, method, checklist item, layout lesson, validation technique, or electronics principle would help another board, promote it to the repository instructions or the relevant reusable skill and leave only the measured result, design-specific rationale, or explicit exception locally.

Do not commit router exchanges, temporary reports, editor-local state, caches, or lock files.
