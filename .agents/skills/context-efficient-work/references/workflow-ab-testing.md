# Workflow A/B Testing

Use this method when changing agent orchestration, transaction helpers, caching, validation routing, or model-visible output.

## Compare outcomes before efficiency

Define the same user goal, inputs, allowed mutations, expected artifacts, and acceptance evidence for both paths. A candidate passes only when it preserves or improves engineering coverage. Report extra or missing coverage explicitly; never trade away a safety or correctness gate for lower token proxies.

Actual model-token accounting is preferred when the runtime exposes it. Otherwise label model-visible calls, output characters, output lines, elapsed time, and repeated-work avoidance as proxy metrics rather than token measurements.

## Portfolio

Exercise the smallest representative set that covers the changed behavior:

- cold full-scope work;
- one narrowly selected design or component;
- unchanged repeated work and cache invalidation;
- a complex multi-gate completion or release check;
- a realistic failure that proves fail-fast behavior and a useful error signature;
- a mutating task in an isolated temporary workspace; and
- an engineering-judgment task whose generated artifact is evaluated by independent validators rather than by the producing step.

For PCB work, representative lifecycle cases include a new schematic/topology, schematic routing and validation, a newly generated PCB plus DRC, an existing-layout verification, manufacturing output generation/audit, and repository release readiness.

## Control bias

Run cold comparisons in both A→B and B→A order when startup caches or system load could affect timing. Keep inputs and tool versions fixed, isolate mutating outputs, and retain detailed reports outside model context. Do not mix a warm cached candidate with a cold baseline except in a separately labelled repeated-work scenario.

## Improvement loop

When a benchmark exposes a real defect:

1. preserve the failing scenario and signature;
2. re-discover existing capabilities before adding code;
3. fix the narrowest workflow adapter, validator, or cache boundary;
4. add a regression test for the demonstrated gap;
5. rerun the affected scenario in both orders when relevant; and
6. promote only the stable lesson, not benchmark noise, into durable guidance.

Keep scenario definitions in ordinary code when a small fixed registry is sufficient. Do not invent a workflow DSL merely to describe the benchmark.
