---
name: context-efficient-work
description: Limit context and token growth during long, tool-heavy repository tasks, repeated validation loops, or log analysis. Do not use for simple one-step work.
---

# Context-Efficient Work

Preserve correctness while minimizing material that must enter the model context. Apply this skill only to work long enough that repeated reads, schemas, diffs, renders, or logs are a meaningful cost.

## Start from the next decision

Before reading, state the next decision or fact to establish. Request only evidence that can change that decision. Do not collect background merely because it might become useful later.

Read required instruction and selected skill files completely. For everything else, use progressive inspection:

1. inventory names and state with narrow commands such as `git status`, `git diff --name-status`, `rg --files`, or a targeted directory listing;
2. locate relevant sections with headings, keys, identifiers, `rg -n`, structured queries, or metadata;
3. read only the ranges or records needed for the decision; and
4. expand scope only when the targeted evidence is insufficient.

Start searches in the owning repository directory or known configuration path. Do not recursively search a home directory, application-support tree, session archive, dependency cache, or generated-output tree until narrower locations have been exhausted. Exclude binaries, caches, backups, renders, and generated artifacts unless they are the object of the task.

## Control tool output

- Set an explicit output budget appropriate to the question; default to no more than roughly 4,000 tokens from one call and lower it for simple checks.
- Ask tools for counts, summaries, selected fields, or matching records instead of entire documents. For structured data, select keys with the native query mechanism.
- Store unavoidable verbose output in the operating-system temporary directory or ignored `.work/<task>/`. Inspect its exit status and summary first, then open only actionable sections. A report path is not evidence unless the producing command succeeded.
- Do not load complete session logs, generated KiCad files, filled-zone polygon diffs, tool catalogs, or schemas when a structured query, semantic validator, or targeted excerpt answers the question. Review generated changes through source parameters, parsers, DRC/ERC, counts, and renders; inspect raw generated text only around unexplained differences.
- For Git review, first classify files with name-status and statistics. Review ordinary source diffs directly. For large deterministic generated sections, account for the entire file through generation inputs plus semantic validation, while separately inspecting every hand-authored or unexplained change.

## Load capabilities on demand

For lazy tool systems, read the toolbox or capability summaries first. Load only the smallest plausible toolbox, then inspect only the schema of the candidate operation. Do not load every toolbox or repeat schema discovery in the same bounded session unless the server state or requirement changed.

Batch related independent reads when their combined output remains small. Prefer one bounded mutation batch followed by one verification batch. Avoid large compound commands whose output mixes unrelated questions or obscures which producer failed.

## Reuse established state

Do not reread unchanged content. Reuse a result when its source, relevant preconditions, and artifact version are unchanged; otherwise check a hash, modification time, Git diff, or tool revision before rereading. Preserve concise facts and conclusions, not raw output.

At each major phase boundary, keep a compact working checkpoint containing:

- objective and current decision;
- accepted facts and assumptions;
- changed artifacts;
- validation result and remaining warning;
- blocker, if any; and
- next action.

Do not repeat the checkpoint in every commentary update. Start a new task only when the next deliverable is genuinely independent and the checkpoint is sufficient to resume it.

## Bound retries and validation

Never retry an unchanged failure. Preserve the short failure signature, classify it, and change exactly one relevant precondition or mechanism. If the same cause survives two materially different attempts, stop and revise the assumption, design topology, environment, or tool choice.

Validate the smallest affected scope first, then run broader required gates once near completion. Do not rerun expensive whole-project checks after a documentation-only change unless that documentation alters an executable contract. Conversely, do not reduce validation merely to save context: safety, publication, and repository instructions remain authoritative.
