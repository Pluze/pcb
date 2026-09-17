# PCB

Reference and experimental PCB designs built with KiCad, plus reusable agent workflows for schematic capture, placement, routing, and verification.

## Contents

- [`Designs/LM555_LED_Flasher`](Designs/LM555_LED_Flasher): an all-SMT, single-sided 555 timer LED flasher adapted from a classroom reference.
- [`.agents/skills/kicad-konnect`](.agents/skills/kicad-konnect): a reference-driven KiCad/Konnect design workflow.
- [`.agents/skills/pcb-repository-governance`](.agents/skills/pcb-repository-governance): repository organization, project creation, history, cleanup, and process-improvement guidance.

## Design Philosophy

Design intent is made explicit before editing. Schematic connectivity, footprints, placement, routing, silkscreen, and final renders are validated as separate gates. Classroom and prototype boards favor readable documentation, common packages, generous geometry, and reproducible evidence.

The workflows draw on KiCad's official IPC model and public agent-oriented KiCad projects, while keeping tool-specific claims tied to verified local behavior. See each design's `VALIDATION.md` for measured results and remaining warnings.

## Workflow References

- [KiCad IPC API documentation](https://dev-docs.kicad.org/en/apis-and-binding/ipc-api/)
- [Konnect](https://github.com/mixelpixx/Konnect)
- [KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server)
- [KiCad MCP Pro skills](https://github.com/oaslananka/kicad-mcp-pro/tree/main/skills)
- [mcp-server-kicad skills](https://github.com/ProductOfAmerica/mcp-server-kicad/tree/main/skills)
- [kcd KiCad skill](https://github.com/AlexSabaka/kcd/tree/main/skills/kicad)

These are references, not vendored dependencies. This repository's rules are based on its own verified tool behavior and design goals.

## Status

These projects are educational references and experiments. They are not production-certified hardware. Verify component data, electrical limits, PCB fabrication rules, assembly requirements, and safety constraints before manufacturing or use.

## Contributing

Read [`AGENTS.md`](AGENTS.md), [`Designs/AGENTS.md`](Designs/AGENTS.md), and [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing a design.

## License

MIT. See [`LICENSE`](LICENSE).
