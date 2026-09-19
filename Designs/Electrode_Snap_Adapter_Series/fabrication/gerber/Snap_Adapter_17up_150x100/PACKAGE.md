# Fabricator Gerber package

Source: `Snap_Adapter_17up_150x100.kicad_pcb`.
Native Gerber X2, absolute millimetre coordinates, with matching Gerber job and Excellon drill data.

## Layer mapping

- `Snap_Adapter_17up_150x100-F_Cu.gbr`: F.Cu.
- `Snap_Adapter_17up_150x100-B_Cu.gbr`: B.Cu.
- `Snap_Adapter_17up_150x100-F_Mask.gbr`: F.Mask.
- `Snap_Adapter_17up_150x100-B_Mask.gbr`: B.Mask.
- `Snap_Adapter_17up_150x100-F_Silkscreen.gbr`: F.Silkscreen.
- `Snap_Adapter_17up_150x100-B_Silkscreen.gbr`: B.Silkscreen.
- `Snap_Adapter_17up_150x100-F_Paste.gbr`: F.Paste.
- `Snap_Adapter_17up_150x100-B_Paste.gbr`: B.Paste.
- `Snap_Adapter_17up_150x100-Edge_Cuts.gbr`: Edge.Cuts.
- `Snap_Adapter_17up_150x100-Coupon_Cuts.gbr`: User.1.

PTH drill hits: 17; NPTH drill hits: 0.
Both drill files are supplied; an empty file means no holes of that type.
Paste layers support optional stencil manufacture. Empty backside artwork is intentional when unused.

Use the Gerber job for the source stackup/thickness. Confirm finish, copper weight,
material, tolerances and any assembly requirements against the approved order.
This package provides bare-board fabrication data; it does not include an assembly BOM or placement file.

User.1 contains 17 internal coupon cut contours.
Edge.Cuts is the processing boundary. Confirm internal routing and panel support/tab strategy with the fabricator.
