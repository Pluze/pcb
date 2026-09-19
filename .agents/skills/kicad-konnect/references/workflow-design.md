# Staged PCB work with evidence

Use this reference when a task spans design decisions, file mutation, validation,
and delivery. Derive the next phase from the requested change and existing files;
do not ask the user to maintain another manifest.

## Phase contracts

| Phase | Input and decision | Executable boundary | Evidence before advancing |
| --- | --- | --- | --- |
| Intent | Required behavior, interfaces, fabrication and assembly limits | Read design contract and changed requirements | Accepted values, source references, unresolved consequential choices |
| Components | Existing BOM and exact package candidates | Search repository, then manufacturer/distributor | Dated MPN, pin/pad/orientation, ratings and sourcing evidence |
| Schematic | Pin-level topology and placed values | `pcb_workflow.py schematic-validate --design NAME` for topology-backed designs | Connectivity, ERC, geometry and rendered review; use native ERC for other schematics |
| Layout change | Verified netlist, project rules and mechanical constraints | One discovered native mutation batch or one closed-file edit batch | Changed components/nets, routing completeness and source readback |
| PCB review | Saved board plus sibling project/custom rules | `pcb_workflow.py pcb-review --design NAME` | DRC categories, unconnected count, input hashes, source integrity, SVG/PNG paths |
| Manufacturing | Accepted board and fabrication process | `pcb_workflow.py manufacturing-refresh --apply --design NAME` | Three-format batch replacement, layer mapping and freshness |
| Delivery | Intended batch and unresolved waivers | `pcb_workflow.py release-ready`, then governance Git gates | Scope-specific evidence, complete diff, coherent commit; authorized publication separately |

Commands are relative to `tools/pcbflow/kicad/scripts/`. `plan --for-goal
pcb-review` exposes the derived phase list without KiCad execution. A single-board
review may use `headless_pcb_review.py BOARD` directly; a wrapper is useful for
selection, multi-design fail-fast behavior and a common evidence receipt.

`release-ready` checks saved-design ERC and endpoint/value/footprint agreement,
the repository contract, manufacturing freshness, whitespace and repository growth.
It does **not** establish exact-MPN correctness, procurement BOM validity,
visual quality, electrical safety, or bench performance. Choose the missing gates
from the changed artifact; never interpret a goal name as broader proof.

## Change impact instead of restarting the lifecycle

| Change | Revisit | Reuse only if still valid |
| --- | --- | --- |
| Resistor value / exact MPN | Calculation, ratings, availability, placed values, BOM; pin/package checks when identity changes | Geometry when package and connectivity are unchanged |
| Net or pin mapping | Topology, ERC, PCB synchronization, routing, DRC, exports | Unaffected component qualification |
| Placement / routing / copper | Mechanical constraints, routing, refill, DRC, renders, manufacturing | Unchanged circuit calculations |
| Project rule or custom rule | All affected DRC evidence, then fabrication checks | Render style and source documentation |
| Export convention | Parser/target mapping, contours, drill counts and freshness | Accepted source-board geometry |
| Presentation only | File validity and visual inspection | Electrical/manufacturing evidence |

A requirement change invalidates downstream evidence, not every upstream fact.
Record the reason for invalidation in a temporary checkpoint. Keep engineering
search (placement choices, current paths, component tradeoffs) separate from
repeatable execution (refill, checks, exports). A failed engineering gate returns
control to the relevant decision; it does not launch another unchanged attempt.

## Snapshot and receipt contract

A PCB snapshot includes the same-basename `.kicad_pcb`, `.kicad_pro`, and optional
`.kicad_dru`. The review helper refuses a missing project and creates a fresh
workspace per invocation, preventing stale rules and old reports from passing.
For variants without a sibling project, explicitly stage the intended project
rules first; the helper does not guess which parent's rules apply.

The receipt includes status, input hashes, DRC category counts, source-integrity
result, artifact locations and coverage. Nonzero exit means failure. Warnings
remain visible and require interpretation against the design's documented waivers.
A pass is geometric evidence, not human visual approval. Inspect the returned
images when appearance or placement matters.

Current review scope is saved PCB geometry. It does not copy hierarchical
schematics, local library trees, custom model trees or external project-variable
resources. Designs depending on those need an explicitly staged dependency bundle
and parity/library review before delivery. Do not silently downgrade them to a
standalone-board check. Live unsaved changes are outside the snapshot.

Review evidence is intentionally uncached: deleting temporary renders or changing
external libraries must not leave a reusable success pointing to nonexistent or
stale artifacts. Existing manufacturing caching remains limited to its declared
inputs. Full details belong in temporary storage, not the receipt or Git.

## Small interfaces, independent acceptance

- Use native KiCad/Konnect operations for geometry and exports; retain adapters
  only for isolation, transaction boundaries, rule preservation and evidence.
- Validate negative cases: missing project, malformed report, stricter project
  rules, stale workspace, missing output, failed child process and source change.
- Measure model-visible call counts, output size and wall time separately. A
  larger honest receipt can be preferable to a smaller result that hides rules.
- Use both A/B orders and the same coverage. A manufacturing benchmark cannot
  prove interactive placement quality or reduced reasoning/token consumption.
- External libraries and skills are candidates, not authority. Prefer a pinned
  minimal trial with independent KiCad checks over installing a competing stack.

See the [tool guide](../../../../tools/pcbflow/README.md#verification-and-reference-tools)
for repeatable verification commands and external reference tools.

For routing versus build semantics, cleanup scope and transaction limits, see the
[Freerouting/build contract](../../kicad-pcb-layout/references/freerouting-build.md).

## Public composition

Use `./pcb check` to inspect saved schematic/PCB agreement and parts fields before
layout work. Use `./pcb finish --design NAME` for the common complete workflow, or
`./pcb finish --design NAME --candidate-only` for a human routing handoff.
`./pcb build` compiles all three manufacturing formats together. The
[tool guide](../../../../tools/pcbflow/README.md) owns command usage and architecture;
this reference owns phase evidence and change-impact decisions.
