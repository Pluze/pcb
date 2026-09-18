---
name: kicad-konnect
description: Operate the local Konnect MCP server efficiently and safely for KiCad project, schematic, PCB, library, verification, and export tasks. Use with the appropriate specialized PCB skill for engineering decisions.
---

# KiCad Konnect Operations

This skill owns Konnect tool discovery, session efficiency, editor-lock safety, and reusable helper invocation. It does not own schematic architecture, component engineering, PCB layout policy, or acceptance criteria.

## Goal-level autonomous entrypoint

For repository-wide manufacturing validation, output refresh, or release readiness, prefer one invocation of `scripts/pcb_workflow.py` over model-orchestrated calls to each design and exporter:

```bash
python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py plan
python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py schematic-validate --design <name>
python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py validate
python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py release-ready
python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py release-ready --apply
```

The controller discovers active KiCad designs, derives a transient phase plan, keeps full per-phase logs under ignored `.work/pcb-workflow/`, emits one compact JSON record, and reuses successful read-only evidence only while its inputs remain unchanged. Use repeated `--design NAME` only to narrow an explicitly scoped request. `--apply` authorizes manufacturing-output refresh inside the requested goal; it never authorizes a commit, push, history rewrite, or unrelated design edit.

Inspect a phase log only when the compact failure cannot be resolved from its error classification. Use the lower-level helpers directly for development, a narrowly selected package, or diagnosis of the failed phase.

## Route engineering work

Read only the specialized skills needed for the task:

- `pcb-component-engineering`: exact parts, pin/footprint mapping, ratings, DigiKey/Mouser evidence.
- `kicad-schematic-design`: the complete logic, module, placement, wiring, automation, ERC, and visual-verification workflow.
- `kicad-pcb-layout`: footprint placement, single-sided/hand-solder layout, routing, DRC, and visual QA.

## Discover the tool surface

Translate the requested operation into required capabilities, then call `list_toolboxes` before assuming a tool exists or does not exist. Read the toolbox descriptions and load the smallest set that covers every source and destination domain involved. For example, schematic-to-PCB synchronization is exposed by the schematic export/synchronization toolbox even though the result is a PCB operation.

Do not infer that Konnect lacks a capability from the currently loaded `tools/list`; unloaded toolsets are intentionally absent. Before proposing a new helper, direct file rewrite, or GUI fallback:

1. call `list_toolboxes`;
2. load each plausible toolset identified by its description;
3. inspect the resulting tool names and schemas;
4. use the existing guarded tool when it covers the requirement.

Only implement a fallback after this discovery sequence proves the capability is unavailable or materially insufficient. Record the missing boundary rather than describing Konnect broadly as lacking the feature.

Apply the same discovery gate to existing repository helpers, not only to new code. Before a skill directs the agent to run or extend a helper for a KiCad operation, re-check the current Konnect toolbox descriptions and schemas because the server surface can evolve. Retire redundant mechanics or narrow the helper to the verified residual value, such as a topology algorithm, cross-tool orchestration, deterministic validation, or a guarded compatibility wrapper.

Real engineering feedback must improve this capability layer. For a reproducible failure or newly required check: preserve the failure signature, re-discover the current tool surface, distinguish an unavailable operation from an indirect or unloaded one, then update the narrowest adapter, workflow, or validator and add a regression test. Expand validation only far enough to cover the demonstrated failure, safety risk, or acceptance contract.

Keep reusable workflows tool-neutral at their boundary: define the engineering goal, required inputs, expected artifacts, and evidence before choosing Konnect, KiCad CLI, IPC, file parsing, or GUI automation as the implementation. Compose and thinly adapt existing capabilities. Do not create a competing IPC/MCP client model, general-purpose KiCad API, or new workflow DSL merely because one operation is inconvenient to call.

When evaluating agent governance or a lifecycle workflow, read [references/lifecycle-evaluation.md](references/lifecycle-evaluation.md). It defines representative common and complex tasks for new circuits, new PCBs, existing-design verification, manufacturing, release, and capability discovery, with independent artifact-based acceptance.

Typical schematic toolsets: `sch_components`, `sch_wiring`, `sch_analysis`, `sch_batch`, `sch_export`.

Typical PCB toolsets: `pcb_board`, `pcb_components`, `placement`, `pcb_routing`, `verification`, `pcb_export`.

Copper-zone work crosses toolset boundaries. Discover and inspect `pcb_board`, `pcb_routing`, and `pcb_export` before adding, editing, or refilling zones. In the currently verified Konnect surface, zone creation is exposed by `pcb_board`/`pcb_routing`, while whole-board `refill_zones` is exposed by `pcb_export`; toolbox summaries alone may not name every individual operation.

Load `library`, `integration`, `design_review`, `templates`, or `manufacturing` only when their capabilities are actually needed. Load user/project configuration before making choices that depend on saved fabrication preferences.

## Local helper

When direct MCP invocation is unavailable in the active environment, use `scripts/konnect_mcp_client.py` as a transport client to the same Konnect server, not as a replacement capability. Prefer one `callseq` per bounded phase:

```bash
python3 .agents/skills/kicad-konnect/scripts/konnect_mcp_client.py \
  --board Designs/Example/Example.kicad_pcb --compact --strict \
  callseq '[
    {"name":"load_toolset","arguments":{"name":["placement","verification"]}},
    {"name":"score_placement","arguments":{}},
    {"name":"run_drc","arguments":{}}
  ]'
```

- Pass the board once and let the helper inject it only where accepted.
- Use `--compact` for concise output and `--strict` when a tool error must fail automation.
- Batch related reads or edits. Prefer one mutating batch followed by one verification batch.
- Do not retry an unchanged failed call; change its preconditions or tool choice.

## Preflight the execution environment

Separate three independent dependencies before using verification or live-editor tools:

1. **KiCad CLI location.** On a standard macOS KiCad installation, check `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` first and confirm its version. Also inspect `~/Documents/KiCad/<version>/3rdparty/plugins/com_github_mixelpixx_konnect/settings.json`; a saved `kicad_cli` absolute path is stronger evidence than the invoking shell's `PATH`.
2. **Child-process permission.** A valid CLI may still be unable to run a board operation inside a managed sandbox. Konnect can report this as `kicad-cli exited with -1: no diagnostic output`, while a direct sandboxed invocation may abort with exit 134. Do not misdiagnose that signature as a missing binary merely because the app-bundle directory is absent from `PATH`. Run the same absolute-path command once in the permitted execution context; if it succeeds there, use that context for CLI-backed Konnect calls.
3. **Live IPC.** Read `ipc_socket_path` and check the live UI separately. An empty socket setting or `No KiCad IPC socket found` affects live-editor operations such as zone refill, but it does not explain a file-backed CLI DRC failure. Configure KiCad API/socket discovery when live tools are required, or choose the documented file/GUI fallback.

Use targeted known paths before broad recursive searches. On macOS, the CLI is five levels below `/Applications` in the standard bundle, so shallow `find` limits can produce a false negative. Verify a producer's exit status before trying to read its expected report. In zsh diagnostic snippets, use a variable such as `cli_rc`; `status` is a reserved read-only parameter.

The warning `observability JSONL write failed: Operation not permitted` concerns optional logging and is not, by itself, a reason to retry a successful design operation. Judge success from the tool result and saved artifact.

## Failure ledger and retry budget

For every failed or anomalous call, keep a compact task-local ledger containing the operation, failure signature, relevant preconditions, the one changed precondition for the next attempt, and the result. Do not commit this transient ledger; promote only verified general behavior into this skill or a helper.

- The first failure triggers classification: schema/capability, project state, design topology, executable/configuration, permission/sandbox, or GUI/IPC state.
- A second occurrence with the same signature triggers root-cause isolation and a durable skill/helper improvement when the behavior is reproducible.
- A third call with unchanged preconditions is forbidden. Switch mechanism, fix the environment or design, or stop with the proven blocker.
- Never poll repeatedly after a stable configuration error. For example, once launch output states that IPC is unconfigured, configure IPC or use a file/GUI fallback instead of waiting through the same warning again.

Known routing for recurring signatures:

- `run_drc` with exit `-1` and no diagnostics: verify configured CLI path, reproduce with the absolute CLI command, then compare sandboxed and permitted execution. Do not edit `PATH` unless configuration inspection actually shows path resolution is the problem.
- `refill_zones` with no IPC: use KiCad's refill command in the PCB editor, save, and run DRC with zone refill enabled; do not repeatedly call the live tool.
- `launch_kicad_ui` with empty arguments: treat it as launching the manager, not as proof that the intended board is open or IPC is configured. Pass the inspected project path when the schema supports it, otherwise open the exact file once through the GUI fallback.
- A close action followed by a GUI `procNotFound` observation error may mean the application exited successfully. Re-inspect application state before repeating the close.

For computer-use fallback, load the current automation documentation before the first nontrivial action and use the documented accessibility methods exactly; do not guess method names or argument shapes. After the exact project is open, batch refill, DRC, save, and close rather than reopening editors for each step.

## Safe file and editor behavior

- Read existing project files and locks before editing.
- Close and save the relevant KiCad editor before file-backed mutation. Never delete a lock merely to force access.
- Treat `.kicad_pro` as editor-owned project state, not passive metadata. PCB Editor loads design rules and netclasses into memory and saves the project file during board/project save operations. If `.kicad_pro` is changed externally while that project remains open, the stale editor session can overwrite the disk change on DRC, refill, save, refresh, or exit. Close the owning editor before external mutation; afterward reopen the matching `.kicad_pro` through the project manager and verify the expected rules before continuing. A GUI refresh is not a file-to-memory synchronization mechanism.
- Prefer opening the matching `.kicad_pro` and launching PCB Editor from that project. Direct standalone board opens are valid, but require explicit confirmation that the intended sibling project was loaded before accepting or saving project settings.
- Preserve unrelated user changes and create a recoverable checkpoint before material edits.
- If live IPC has no handler, confirm the correct editor/project state or use an equivalent file-backed tool.
- Moving symbols does not stretch wires; delete/replan affected wires or use a supported connected move.
- Verify committed-file readback after mutations.

## Reusable helpers

- `scripts/schematic_topology_router.py`: dry-run and apply topology-driven orthogonal schematic routing.
- `scripts/validate_schematic_design.py`: topology, geometry, connectivity, ERC, and render validation.
- `scripts/manufacturing_discovery.py`: discovers publishable boards by repository convention and derives copper sides, mask sides, semantic coupon-cut layers, and drill/contour counts directly from each `.kicad_pcb`.
- `scripts/export_circuitpro_u4_packages.py`: PCB-driven RP 1.x export with target-aligned naming, DRC, validation, source-freshness audit, and recoverable replacement.
- `scripts/validate_circuitpro_u4_package.py`: exact package/file, attribute, connected-contour, and drill-hit validation for supported U4 profiles.
- `scripts/export_kapton_lightburn_templates.py`: PCB-driven millimetre DXF export from inferred solder-mask openings plus `Edge.Cuts`, with source-freshness audit and fitted AutoCAD extents/viewport metadata. KiCad's raw DXF can contain valid geometry but appear blank in AutoCAD because it omits extents and leaves the active view at a 1000 mm default around the origin.
- `scripts/manage_manufacturing_outputs.py`: repository-wide discovery and audit/export of U4 and LightBurn outputs for every active design.
- `scripts/pcb_workflow.py`: goal-level, self-discovered orchestration with compact JSON results, ignored phase logs, input-hash caching, and explicit mutation authority.
- `scripts/benchmark_pcb_workflow.py`: counterbalanced A/B coverage for full and scoped manufacturing checks, unchanged repeats, topology-driven schematic validation, new generated PCB plus DRC, and release readiness. Reports stay under ignored `.work/pcb-workflow/benchmarks/`.

These helpers are repository-wide capabilities only where they add behavior beyond the currently discovered Konnect surface. Revalidate that boundary before use or maintenance. Their design-specific input and measured results belong under the target design; their general algorithms and rules remain with the skill.

## CircuitPro RP 1.x compatibility exports

For any LPKF ProtoLaser U4 or CircuitPro RP 1.x manufacturing-input task, read [references/circuitpro-rp1-u4.md](references/circuitpro-rp1-u4.md) completely before exporting or interpreting files. It owns the parser-format rationale, CircuitPro target mapping, filename contract, KiCad CLI compatibility fallback, drill semantics, packaging boundary, and validation gate. Re-discover the current Konnect export schemas first; use the reference's CLI fallback only for options the loaded tool surface still cannot express.
