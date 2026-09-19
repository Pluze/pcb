---
name: pcb-repository-governance
description: "Govern a reusable PCB design repository: organize KiCad projects, create new designs, manage temporary and generated files, preserve clean Git history, validate publication boundaries, reuse prior evidence, and promote stable lessons into AGENTS.md or skills. Use for repository setup, cleanup, project scaffolding, contribution workflow, checkpointing, or durable process improvement around PCB work."
---

# PCB Repository Governance

Use this skill when repository structure and work discipline are part of the requested result, not merely incidental file operations.

## One Authority per Rule

Assign each rule to one primary owner:

- repository invariants and publishing policy: root `AGENTS.md`;
- design-directory contract: `Designs/AGENTS.md`;
- repeatable domain or tool procedure: a focused skill;
- executable commands and protocol mechanics: `tools/pcbflow/` with adjacent tests;
- circuit-specific facts and evidence: the design's `README.md` and `VALIDATION.md`.

Link to the primary owner instead of copying normative prose. This reduces drift and makes future improvements local.

## Directory Contract

Keep the root small and functional. Prefer:

```text
.agents/skills/
.github/
Designs/
AGENTS.md
CONTRIBUTING.md
LICENSE
README.md
```

Expose reusable execution through `./pcb`; keep engineering guidance in skills.

Store every KiCad project under `Designs/<Meaningful_Name>/`. Use the same stem for the directory and the `.kicad_pro`, `.kicad_sch`, and `.kicad_pcb` files. Place intentional previews under `assets/` and project-specific Konnect preferences under `.konnect/`.

## Temporary-File Policy

Classify an artifact before creating it:

1. Disposable process data goes to the operating-system temporary directory.
2. A recoverable cleanup backup goes to a uniquely named operating-system temporary directory and is reported to the user.
3. Tool data that must live inside the repository goes under ignored `.work/<task>/`.
4. A reader-facing artifact goes under the owning design's `assets/`.
5. A reproducibility input belongs beside the design only when it is stable, documented, and intentionally versioned.

Never commit editor locks, `.kicad_prl`, autosaves, backup directories, DSN/SES exchanges, caches, transient ERC/DRC reports, Finder metadata, or personal absolute paths. Do not manually remove an active KiCad lock; close the owning editor first.

## Create a New Design

1. Choose a meaningful functional name before creating files.
2. Create `Designs/<Name>/` with matching KiCad stems, `README.md`, `VALIDATION.md`, `assets/`, and optional `.konnect/project.json`.
3. Write the design contract: function, supply range, interfaces, known parts, fabrication assumptions, layer count, assembly method, and source references.
4. Separate verified facts from interpretations and unresolved questions.
5. Reuse a previous design only after identifying which constraints genuinely match; never copy its values or rules by proximity alone.
6. Establish the first checkpoint after the project opens and parses correctly.

## Development Workflow

Use a gated sequence:

1. Contract and source attribution.
2. Existing-state inspection.
3. Schematic capture and pin-level connectivity verification.
4. ERC and visual schematic review.
5. Footprint and package verification.
6. Placement optimization and mechanical review.
7. Guarded routing or autorouting.
8. DRC, connectivity, layer, width, via, silkscreen, and render checks.
9. Documentation of evidence and remaining risk.
10. Explicit staging, cached-diff review, coherent commit, and publication verification.

Do not advance merely because a tool exited successfully. Each gate must inspect the artifact the next phase will consume.

## Inferring Hidden Constraints

Translate user language into testable constraints, then state assumptions:

- “classroom,” “prototype,” or “easy to fabricate” often implies common parts, readable labels, generous spacing, wide traces, and simple layer use;
- “single-sided” implies one copper routing layer, zero vias by default, deliberate crossover policy, and same-side SMD placement unless explicitly changed;
- “match the reference” implies functional topology and meaningful spatial grouping, not copying visible errors;
- “all SMT” implies footprint availability, assembly access, polarity visibility, and realistic hand-assembly sizes;
- “publish” implies no private paths, secrets, proprietary source material, lock files, or unexplained generated debris;
- “finished” implies recorded verification and disclosed warnings, not just saved files.

If an inferred constraint materially changes safety, electrical behavior, cost, or manufacturability, surface it rather than silently deciding.

## Efficient Tool Use

- Inspect first and choose the narrowest capable toolset.
- Let repository state produce transient execution plans. Do not require a user-authored plan, duplicate project manifest, or scheduled task when the design files and repository contract already determine the work.
- Prefer a tested goal-level controller when it can execute several deterministic phases behind one compact result. Keep its verbose logs and cache under ignored `.work/`, key reused evidence to content and tool inputs, and preserve per-phase failure identity.
- Before creating or retaining a KiCad helper in any skill, inventory the current Konnect toolboxes and schemas for overlapping capability. Prefer native guarded operations; document and test the exact residual gap that justifies custom code.
- Batch related reads, edits, and verification in one process when state permits.
- Reuse schema discovery and project context during a bounded session.
- Change a failed call's precondition before retrying it.
- Keep GUI state and file-backed state synchronized; close editors before external file mutation.
- Preserve a checkpoint before a high-impact operation and validate the saved file afterward.
- Put deterministic, failure-prone mechanics in a tested helper rather than repeating shell fragments.
- Under a managed workspace, a Git ref update can fail with `cannot lock ref` or `unable to create directory` even when the branch name and repository are valid because `.git` is read-only to the sandboxed process. Confirm the repository state, then rerun the same narrowly scoped Git operation once with the required repository-write permission; do not rename branches, modify ref files manually, or repeat the sandboxed command.
- Treat validator runtime failures separately from content failures. If the default Python lacks a declared dependency such as PyYAML, locate an existing approved environment that provides it instead of installing packages ad hoc. If bytecode compilation fails only because the interpreter cannot write its user cache, redirect `PYTHONPYCACHEPREFIX` to an operating-system temporary directory; never create interpreter caches in the repository or weaken the validator to obtain a pass.

## Git History

Use lowercase Conventional Commit subjects. A commit should represent one accepted outcome, such as repository governance, one design addition, or one verified fix. Exclude discarded drafts and session noise.

Before committing:

1. define the intended batch and state the role of every candidate file;
2. inspect status and separate unrelated user work;
3. remove or leave unstaged superseded assets, duplicate renders, intermediate screenshots, internal discussion, rejected alternatives, chronological decision churn, transient reports, and incidental generated files;
4. retain only necessary sources, current evidence, final reader-facing artifacts, and concise documentation of accepted rationale and unresolved risk;
5. search candidates for secrets, absolute personal paths, debug residue, locks, caches, nested repositories, and router exchanges;
6. stage explicit paths and inspect `git diff --cached --name-status` so every staged file is intentional;
7. inspect `git diff --cached --check` and the complete cached diff, unstaging any file without a clear role in the batch;
8. run the validations appropriate to the changed scope.

Run `tools/pcbflow/repository/scripts/check_repository_growth.py --report-worktree` against the staged batch. Before publication, run it with `--all-tracked --history --report-worktree`; this checks both the current tree and every reachable blob so a large artifact cannot be hidden by adding and deleting it within one push. Install the checked-in `.githooks/pre-commit` through `git config core.hooksPath .githooks` for local enforcement. The helper owns the numeric limits and prohibited artifact classes; update its tests and documentation together when policy changes.

Do not use Git history as a transcript of the design session. Iteration history belongs in local recoverable checkpoints or temporary backups; the commit should present the accepted engineering state and the evidence needed to review it.

Do not amend, rebase, force-push, or rewrite shared history without explicit authorization.

## Local-to-Remote Integration

Model Git publication as a state transition, not as a single `push` command:

1. Confirm the worktree and index contain only the intended work.
2. Resolve the source branch, integration branch, remote name, remote URL, and destination branch explicitly.
3. Fetch the destination branch and compare it with the source using the fetched remote-tracking ref. A squash workflow may proceed directly only when the destination is not unexpectedly ahead or divergent.
4. Preserve the source branch as a recovery point. Switch to the integration branch and fast-forward it to the fetched destination before applying the source with `merge --squash`.
5. Review the resulting staged name-status, whitespace check, statistics, complete diff, and relevant validation evidence as one publication batch. The earlier feature-branch review is useful evidence but does not replace checking the combined squash result.
6. Create one conventional commit on the integration branch and use a normal fast-forward push. Never substitute a force push for resolving unexpected divergence.
7. Verify publication by fetching or reading the remote-tracking ref and comparing its commit ID with the intended local integration commit.
8. After verified publication to the integration branch, delete the local source branch when it has no unpublished work beyond the published batch and is not attached to a worktree. This cleanup is the default even after a squash merge; retain the branch only when the user explicitly requests it or it still contains unique unpublished work. Never delete another task's branch merely because it is already merged.
9. Report the concrete commit, remote URL, destination branch, and completed source-branch cleanup or the specific reason a branch remains.

An explicit user request to `push`, publish, or update the remote authorizes a normal push of the audited current repository state to its configured upstream remote and named or tracked branch. Inspect and report the concrete URL and destination, but do not demand separate proof of remote-account ownership or repeat the confirmation merely because the remote uses GitHub, SSH, or another external host. Ask again only when publication intent was not explicit, the configured destination is missing or genuinely ambiguous, the requested branch differs from the tracked destination, or the operation would require a force push or history rewrite. Stop before pushing if secrets, credentials, private keys, personal absolute paths, unrelated files, stale generated artifacts, unlicensed private material, or unreviewed history enter the batch.

## Reusing Prior Experience

Start with repository instructions, then inspect the closest successful design and its validation record. Reuse verified process, not unexamined geometry or component choices. A prior workaround remains conditional on the same tool version and failure signature.

## Dynamic Improvement

Promote a lesson only when at least one condition holds:

- the user explicitly states a durable policy;
- the same failure recurs;
- tool output or authoritative documentation proves a stable behavior.

Then:

1. identify the narrowest owner;
2. express the reusable requirement as a tool-neutral workflow outcome, inputs, artifacts, and evidence;
3. remove project-specific values unless they are essential examples;
4. re-discover existing capabilities before claiming a gap, then prefer a thin adapter or composition over a parallel API, protocol, or DSL;
5. update the narrowest coupled helper and extend validation only for the demonstrated failure, safety risk, or acceptance requirement;
6. when the change affects orchestration, caching, or output volume, run a coverage-first A/B comparison over the affected common, repeated, failure, and complex tasks;
7. test the revised workflow against the real failure that motivated it;
8. keep the skill in English and scan for accidental local paths or project-specific residue.

Do not promote guesses, one-off session corrections, or discarded experiments into durable policy.

## Publication Gate

Before making a repository public, require:

- intentional license and public-facing README;
- clean repository status after the intended commits;
- no nested repositories, secrets, local paths, locks, caches, temporary outputs, or unlicensed reference material;
- documented design limitations and human-review requirement;
- parseable KiCad files and current ERC/DRC evidence;
- working links and readable rendered assets.

Publication does not certify fabrication readiness.
