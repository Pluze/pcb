# Design Directory Instructions

Each immediate child of `Designs/` is one self-contained hardware design.

## Required contract

- Use one meaningful stable name for the directory and matching `.kicad_pro`, `.kicad_sch`, and `.kicad_pcb` files.
- Keep `README.md` for purpose, inputs, assumptions, component strategy, fabrication intent, and unresolved design risks.
- Keep `VALIDATION.md` as a compact current snapshot of dated, reproducible evidence and explicit waivers—not a chronological log.
- Keep intentional previews under `assets/`; use `.konnect/project.json` only for durable project-specific tool preferences or explicit exceptions. Common PCB workflow, layout, routing, line-width, copper-pour, and manufacturing defaults live in `.agents/skills/kicad-pcb-layout/references/repository-defaults.json` and must not be copied into each design.
- For generated schematics, keep the version-controlled pin-level topology contract beside the project.

## Engineering boundary

Use the relevant component, schematic, layout, and Konnect skills for engineering method. Design files and documentation contain only requirements, calculations, selections, geometry, measured results, risks, and exceptions specific to that design. Promote reusable rules, algorithms, and validation methods to their owning skill before applying them here.

Before accepting a design, verify authoritative symbol-pin and footprint-pad mapping, polarity and connector orientation, schematic connectivity and readability, placement and mechanical constraints, routing, layer use, zones, ERC/DRC, and final schematic/PCB renders. Record actual counts and remaining exceptions. A tool pass does not prove fabrication readiness or a physical interconnect.

Do not commit locks, editor state, caches, router exchanges, temporary reports, superseded renders, or process history.
