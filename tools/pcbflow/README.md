# PCB tools

One CLI for engineers and agents. Run `./pcb --help` from the checkout; no install
step is needed. Python 3 and the installed KiCad tools provide execution. `./pcb
doctor` locates KiCad Python, Freerouting and a compatible Java runtime. Explicit
paths use `--kicad-python`, `--java`, `--jar`, or the environment variables
`PCB_KICAD_PYTHON`, `PCB_JAVA`, and `FREEROUTING_JAR`.

## Desktop window

Double-click `PCB Tools.command` in this folder or run `./pcb gui`.
Running `./pcb` without a command displays CLI help.
The external window uses KiCad's installed Python/wx runtime. Select a design,
then use Run complete workflow, or follow the numbered Check, Route and Review,
and Production Files groups. Results show measured checks, warnings and next steps;
raw receipts are available in the collapsed Technical details panel. Results and
production folders open from the window. Save edits in KiCad first; close the
board editor before Finish or Apply and reopen the resulting board afterward.
The candidate-only checkbox pauses the complete workflow for review before adoption.

## Common tasks

| Intent | Command |
| --- | --- |
| Discover designs | `./pcb list` |
| Check schematic, PCB agreement and parts fields | `./pcb check` or `./pcb check --design NAME` |
| Complete a saved schematic + placement | `./pcb finish --design NAME` |
| Preview that workflow | `./pcb finish --design NAME --dry-run` |
| Generate a candidate for human review | `./pcb finish --design NAME --candidate-only` |
| Route an existing board | `./pcb route --design NAME` |
| Inspect a saved PCB | `./pcb review --design NAME` |
| Adopt a reviewed/repaired route candidate | `./pcb adopt --design NAME --receipt /path/to/receipt.json` |
| Refresh all production formats | `./pcb build --design NAME` |
| Build every active design | `./pcb build` |
| Verify the current delivery | `./pcb verify` |
| Discover fine-grained operations | `./pcb tools`, then `./pcb tool NAME --help` |

Put `--json` before the subcommand for structured agent output. High-level commands
select and compose the engines automatically. Advanced tools retain their original
arguments and focused help. The CLI and the engines share one implementation.

## Human and agent handoff

1. Draw the schematic and place components in KiCad. Save the project and close the
   board editor before a command that adopts a changed board.
2. Run `finish`. It checks saved schematic ERC and PCB endpoint/value/footprint
   agreement, inventories parts fields, then clears old tracks/vias/pours in an
   isolated copy, runs Freerouting, finishes widths/corners, and independently
   checks the routed result. Pads, component placement and board outline are retained.
3. A passing candidate is revalidated and adopted, then the tool derives and checks
   the pour variant, builds all production formats, and verifies the delivery.
4. Inspect the returned board previews and apply design-specific electrical/bench
   acceptance. `--candidate-only` provides an earlier handoff for manual editing.
   After editing the candidate, `adopt` revalidates the current saved candidate.

Use this clean-copper sequence whenever routing or pour requirements change.
`build` compiles an already accepted routing source; it is also useful when only
manufacturing outputs need refreshing. A failed phase leaves a receipt and the
candidate for targeted repair. The default recipe performs the common checks as a
set; callers do not need to choose individual low-level operations.

## Build outputs

Every active no-pour/pour package produces these sibling output families:

- `fabrication/u4/`: CircuitPro target-mapped copper, outline and relevant drills.
- `fabrication/lightburn/`: front/back mask DXFs in board coordinates as applicable.
- `fabrication/gerber/`: all declared copper layers, front/back mask, silkscreen and
  paste, outline, Gerber X2 job, PTH/NPTH drills and a short layer-mapping document.
  Panel coupon-cut artwork is included when present.

All selected designs and all three families build in staging first. Validated
output directories are replaced as one recoverable batch. The source-variant step
precedes that batch. A process-level install error restores the previous output
batch; the tool is not a filesystem power-loss transaction. Stale generated outputs
are replaced only inside the owned fabrication families. Source edits, candidates
and electrical decisions are separate from output replacement.

Verbose goal logs live under ignored `.work/pcb-workflow/`; routing and review
artifacts live in OS temporary directories. Final reader-facing source files,
previews and production packages remain in each design.

## Implementation map

`cli.py` owns public commands, dependency discovery and common-task composition.
The adjacent engine groups own KiCad review/manufacturing, routing geometry, and
repository checks. Each group keeps its tests beside its implementation. Shared
engineering defaults and decision guidance live in `.agents/skills/`.

The CLI runs saved-file workflows; an open editor's unsaved state is a separate
human handoff. The current router profile is front-copper, zero-via routing with
0.25 mm minimum actual tracks. Rule-area/keepout projects require an adapter that
preserves those constraints and are identified before routing starts. Supplier
order parameters and assembly deliverables are described in each Gerber package.

## Saved-design inspection

`check` runs native ERC and native XML netlist export, then compares schematic
component values, footprint assignments and pin-to-net connectivity with the saved
KiCad 10 PCB. Generated net names may differ; endpoint membership must agree.
The adapter reuses the native-block reader and does not implement circuit parsing
or geometry generation. DNP parts retain electrical connectivity; symbols excluded
from the board are omitted. Empty schematics report parity as not applicable.

The temporary `parts.csv` is a per-reference schematic inventory. Missing `MPN`
fields are visible findings; an existing procurement `BOM.csv` is identified as a
separate catalog. Inventory completeness does not certify catalog matching, exact
part suitability or current stock. Reports and source hashes stay in temporary
storage; the source design is unchanged. No transient task manifest is required.

`verify` combines this saved-design check with manufacturing freshness and repository
gates. `finish` stops before routing when ERC or schematic/PCB agreement fails.

## Verification and reference tools

Run the regression suites after changing their corresponding engines:

```sh
PYTHONDONTWRITEBYTECODE=1 PCB_REVIEW_REAL=1 python3 -m unittest discover -s tools/pcbflow/kicad/tests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/pcbflow/routing/tests -q
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/pcbflow/tests -q
```

The real tests require installed KiCad. They include stricter project-rule and
stale-schematic fault injections, so a clean exit alone cannot satisfy acceptance.
The endpoint adapter checks native XML netlist membership rather than generated
net labels. Native schematic-parity output can disagree for custom symbols;
inspect the relevant pin groups before accepting a discrepancy.

Useful upstream capabilities to evaluate when a concrete requirement arises:

- [KiCad CLI](https://docs.kicad.org/10.0/en/cli/cli.html): native ERC/DRC, netlists,
  BOMs, jobsets and manufacturing exports.
- [KiBot](https://github.com/INTI-CMNB/KiBot): richer CI documentation and variant BOMs.
- [KiKit](https://github.com/yaqwsx/KiKit): panel tabs, rails and panelization recipes.
- [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom):
  assembly placement/checklists after part fields are complete.
- [KiDiff](https://github.com/INTI-CMNB/KiDiff): graphical schematic/PCB revisions.
- [Memfault schematic review](https://interrupt.memfault.com/blog/schematic-review-checklist):
  hardware/firmware interface questions for designs containing those interfaces.

These are reference projects, not installed dependencies or locally qualified tools.
