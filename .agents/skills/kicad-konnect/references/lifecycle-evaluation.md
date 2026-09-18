# PCB Agent Lifecycle Evaluation

Use this portfolio when evaluating changes to PCB agent governance, capability discovery, orchestration, or validation. It complements automated command benchmarks with artifact-based engineering tasks.

## Evaluation rule

The producing agent does not grade its own design. Compare the resulting source files and evidence with independent parsers, topology checks, ERC/DRC, manufacturing validators, repository gates, and rendered human review. Efficiency matters only after the acceptance contract is preserved.

## Representative tasks

### New circuit: common

Design a small, one-sheet, hand-solderable SMT circuit from a functional requirement such as a timer, indicator, sensor interface, or protected power input. Require:

- explicit supply, interface, assembly, and fabrication assumptions;
- exact consequential MPN and pin/footprint evidence;
- a pin-level topology contract;
- readable functional grouping and explicit local wiring;
- ERC, topology comparison, geometry checks, and schematic renders; and
- disclosed unknowns rather than invented requirements.

### New circuit: complex

Design a mixed power/analog or feedback-controlled circuit with protection, test points, multiple interfaces, and nontrivial component ratings. Evaluate calculations, loop and return-path reasoning, derating, connector semantics, failure behavior, topology readability, and whether missing authoritative evidence blocks rather than silently passes.

### New PCB

Create a board from a verified schematic under mechanical and fabrication constraints. Include both a simple generated geometry case and a placement/routing case. Evaluate footprint mapping, fixed mechanical items, placement feasibility, routing layers, widths, vias or jumpers, zones, DRC, connectivity, silkscreen, assembly access, and 2D/3D review. A generated file must pass KiCad parsing and DRC before final placement in the project.

### Existing-design verification

Seed or select realistic defects: stale routing, wrong connector orientation, pin/pad mismatch, shorted power/return, unfilled or over-close zones, open coupon contours, missing drill output, stale manufacturing files, or ambiguous schematic geometry. The agent must discover the applicable tool surface, classify the failure, change a relevant precondition, and extend the narrowest validator when the defect was previously invisible.

### Manufacturing and release

Generate and audit U4, Gerber, drill, panel-cut, or LightBurn outputs from board semantics. Evaluate exact layer mapping, outline/cut separation, drill and contour counts, source freshness, output atomicity, repository hygiene, and publication boundaries.

### Capability-discovery challenge

Present a needed operation that is not in the currently loaded tool list but exists in another toolbox or through a supported composition. Passing behavior re-discovers capabilities and uses or thinly adapts the existing operation. Failing behavior declares the capability absent or builds a parallel API without completing discovery.

## Comparison record

For each A/B run, record task, inputs, tool versions, order, accepted artifacts, failed gates, model-visible calls and output, elapsed time, cache state, and any extra coverage. Preserve raw logs under ignored `.work/`; promote only verified failures and durable remedies into skills or helpers.
