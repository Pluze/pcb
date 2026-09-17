# Contributing

## Start Here

Read the repository and scoped `AGENTS.md` files, then the relevant skill and target design documentation. Preserve unrelated work and use a short-lived branch for independent changes after initial repository setup.

## Changes

- Keep one design under `Designs/<Meaningful_Name>/`.
- Explain design intent, sources, assumptions, and fabrication constraints.
- Update `VALIDATION.md` with measured ERC/DRC and visual-review evidence.
- Keep generated scratch data in the operating-system temporary directory or ignored `.work/`.
- Do not commit KiCad locks, editor-local state, router exchanges, caches, or unexplained reports.

## Commits

Use lowercase Conventional Commit subjects, for example:

```text
feat: add lm555 led flasher reference design
fix: correct led polarity and timing network
docs: record single-sided routing constraints
chore: refine repository validation policy
```

Stage exact paths and inspect the cached diff before committing. Keep each commit focused on one accepted outcome.

The repository includes a versioned pre-commit hook and growth checker. Enable the hook once per clone:

```sh
git config core.hooksPath .githooks
```

Run the complete check before publishing:

```sh
python3 .agents/skills/pcb-repository-governance/scripts/check_repository_growth.py --all-tracked --history --report-worktree
```

Ordinary Git rejects files larger than 5 MiB, images larger than 2 MiB, reader-facing binary documents outside a design's `assets/` directory, and disposable archives, office containers, or videos. It also stops when untracked data exceeds 500 files or 25 MiB, or ignored data exceeds 2,000 files or 50 MiB. Do not bypass the check. Put reproducible source data in reviewable text, use release assets for generated publication packages, and establish Git LFS deliberately before adding a necessary large binary.

## Review Checklist

- KiCad project files parse and share a matching project stem.
- Connectivity and polarity match the intended circuit.
- ERC and DRC results are current and documented.
- Footprints, board outline, placement, routing, and silkscreen have been visually inspected.
- No unresolved connection, unintended layer, via, private path, secret, or temporary artifact is included.
- Remaining warnings and engineering risks are disclosed.
