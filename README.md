# PCB

Reference and experimental PCB designs built with KiCad, plus reusable agent workflows for schematic capture, placement, routing, and verification.

## Contents

- [`Designs/LM555_LED_Flasher`](Designs/LM555_LED_Flasher): an all-SMT, single-sided 555 timer LED flasher adapted from a classroom reference.
- [`Designs/Ionto_Current_Source_Core`](Designs/Ionto_Current_Source_Core): a single-channel R1218 constant-current boost prototype.
- [`Designs/Electrode_Snap_Adapter_Series`](Designs/Electrode_Snap_Adapter_Series): four circular-contact adapters and a 17-up U4 panel.
- [`.agents/skills`](.agents/skills): reusable KiCad, PCB-layout, component, and repository tooling.

## Design Philosophy

Design intent is made explicit before editing. Schematic connectivity, footprints, placement, routing, silkscreen, and final renders are validated as separate gates. Classroom and prototype boards favor readable documentation, common packages, generous geometry, and reproducible evidence.

The workflows draw on KiCad's official IPC model and public agent-oriented KiCad projects, while keeping tool-specific claims tied to verified local behavior. See each design's `VALIDATION.md` for measured results and remaining warnings.

All active designs use the repository manufacturing exporter. It discovers the publishable KiCad boards, derives layer, mask, drill, and panel-cut intent directly from each `.kicad_pcb`, and audits checked-in U4 and LightBurn outputs against a fresh export.

Repository-wide goals use a self-discovered workflow rather than a hand-maintained project plan. For example, `python3 .agents/skills/kicad-konnect/scripts/pcb_workflow.py release-ready` discovers active designs, runs the applicable read-only gates, keeps detailed logs under ignored `.work/`, and returns one compact JSON result. Add `--apply` only when the requested goal should refresh inferred manufacturing outputs; Git publication remains a separate authorized action.

## Status

These projects are educational references and experiments. They are not production-certified hardware. Verify component data, electrical limits, PCB fabrication rules, assembly requirements, and safety constraints before manufacturing or use.

## Contributing

Read [`AGENTS.md`](AGENTS.md), [`Designs/AGENTS.md`](Designs/AGENTS.md), and [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing a design.

## License

MIT. See [`LICENSE`](LICENSE).
