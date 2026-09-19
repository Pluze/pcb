# PCB

Reference and experimental PCB designs built with KiCad, plus reusable agent workflows for schematic capture, placement, routing, and verification.

## Contents

- [`Designs/LM555_LED_Flasher`](Designs/LM555_LED_Flasher): an all-SMT, single-sided 555 timer LED flasher adapted from a classroom reference.
- [`Designs/Ionto_Current_Source_Core`](Designs/Ionto_Current_Source_Core): a single-channel R1218 constant-current boost prototype.
- [`tools/pcbflow`](tools/pcbflow): public CLI, reusable engines and tests for humans and agents.
- [`.agents/skills`](.agents/skills): engineering methods and shared design defaults.

## Design Philosophy

Design intent is made explicit before editing. Schematic connectivity, footprints, placement, routing, silkscreen, and final renders are validated as separate gates. Classroom and prototype boards favor readable documentation, common packages, generous geometry, and reproducible evidence.

The workflows draw on KiCad's official IPC model and public agent-oriented KiCad projects, while keeping tool-specific claims tied to verified local behavior. See each design's `VALIDATION.md` for measured results and remaining warnings.

Use `./pcb finish --design NAME` to complete a saved design through clean autorouting,
review, adoption, copper pour and production build. Use `./pcb build` to refresh U4,
LightBurn and complete supplier Gerber packages together. `./pcb verify` checks the
current delivery. Add `--json` before the command for agent-readable results.

The [tool guide](tools/pcbflow/README.md) covers human/agent handoffs, staged commands,
advanced tools, output ownership and verification commands.

## Status

These projects are educational references and experiments. They are not production-certified hardware. Verify component data, electrical limits, PCB fabrication rules, assembly requirements, and safety constraints before manufacturing or use.

## Contributing

Read [`AGENTS.md`](AGENTS.md), [`Designs/AGENTS.md`](Designs/AGENTS.md), and [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing a design.

## License

MIT. See [`LICENSE`](LICENSE).
