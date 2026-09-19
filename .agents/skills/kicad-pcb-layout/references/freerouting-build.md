# Routing and manufacturing entrypoints

Use the [PCB tool guide](../../../../tools/pcbflow/README.md) for human and agent commands.

`./pcb finish --design NAME` applies the common sequence: saved schematic ERC,
clear old routing/vias/pours in a snapshot, Freerouting, width/corner finishing,
independent KiCad review, adoption, pour derivation, three-format manufacturing
build, and final verification. `--candidate-only` stops at the review handoff.

`./pcb route --design NAME` runs the routing stage independently. The standalone
engine is `./pcb tool route-candidate --help`; its native KiCad DSN/SES bridge is
verified with KiCad 10.0.6, Freerouting 2.4.1 and Java 26. `./pcb doctor` resolves
installed runtimes. Each router process has a 120-second default limit and a
fresh temporary user-data directory.

Routing candidates retain placement, pad/net assignments and mechanics. Layer
constraints follow DSN layer declarations. The selected profile uses F.Cu, zero
vias, 45-degree routing and a 0.25 mm actual width floor. One finishing pass widens
sub-floor neckdowns and bevels degree-two right-angle bends by at most 0.20 mm,
limited to a third of either neighboring leg. Independent DRC validates the result.
The receipt includes input/engine hashes, geometry metrics, DRC and render paths.

`./pcb build` compiles accepted routing into no-pour/with-pour U4, LightBurn and
supplier Gerber packages. All selected output families are staged and validated
before one recoverable batch replacement. Source-variant generation remains a
separate preceding step. Caching tracks source/project/custom rules, exporters
and manufacturing outputs. Run `./pcb verify` to audit the saved delivery.

Review critical functional/return paths and final renders as part of design
acceptance. The geometry receipt and manufacturing files carry their measured
scope; bench performance remains a design-specific validation activity.
