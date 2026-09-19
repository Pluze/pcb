# Fabricator Gerber package

Source: `Ionto_Current_Source_Core_With_Pour.kicad_pcb`.
Native Gerber X2, absolute millimetre coordinates, with matching Gerber job and Excellon drill data.

## Layer mapping

- `Ionto_Current_Source_Core_With_Pour-F_Cu.gbr`: F.Cu.
- `Ionto_Current_Source_Core_With_Pour-B_Cu.gbr`: B.Cu.
- `Ionto_Current_Source_Core_With_Pour-F_Mask.gbr`: F.Mask.
- `Ionto_Current_Source_Core_With_Pour-B_Mask.gbr`: B.Mask.
- `Ionto_Current_Source_Core_With_Pour-F_Silkscreen.gbr`: F.Silkscreen.
- `Ionto_Current_Source_Core_With_Pour-B_Silkscreen.gbr`: B.Silkscreen.
- `Ionto_Current_Source_Core_With_Pour-F_Paste.gbr`: F.Paste.
- `Ionto_Current_Source_Core_With_Pour-B_Paste.gbr`: B.Paste.
- `Ionto_Current_Source_Core_With_Pour-Edge_Cuts.gbr`: Edge.Cuts.

PTH drill hits: 0; NPTH drill hits: 0.
Both drill files are supplied; an empty file means no holes of that type.
Paste layers support optional stencil manufacture. Empty backside artwork is intentional when unused.

Use the Gerber job for the source stackup/thickness. Confirm finish, copper weight,
material, tolerances and any assembly requirements against the approved order.
This package provides bare-board fabrication data; it does not include an assembly BOM or placement file.
