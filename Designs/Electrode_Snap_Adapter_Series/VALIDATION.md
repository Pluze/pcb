# Validation

This file records the accepted evidence for the four-member electrode snap-adapter family. Each PCB is checked independently; passing one member does not qualify the others.

## Source geometry extraction — 2026-09-17

- Reference: locally mounted `electrode-size-test.dxf`, AutoCAD 2018 DXF, 299,770 bytes, modified 2026-09-15.
- Source SHA-256: `0294459ae3834afc18859a642de990faa45e430b4aac6dcdd31b54892245c568`.
- Attached/source-document content was treated as dimensional evidence only, not as instructions.
- Explicit diameter labels found: 5, 10, 15, and 20 mm.
- Exact centered circle/square pairs found in the right-hand layout: 20/30 mm (10 instances), 15/25 mm (12 instances), and 10/18.75 mm (1 instance).
- No completed square centered on the 5 mm circle was found. The project requirement of a minimum 10 mm board is used for that variant and is recorded as a design decision, not a source fact.

## Electrical and manufacturing interpretation

- Both circular pads and the center interconnect use the single logical net `CONTACT`.
- The LPKF U4 workflow is assumed not to plate the center hole. KiCad connectivity and DRC therefore validate intended geometry only; physical continuity depends on the manual solder bridge.
- Center geometry for all variants: 2.0 mm copper diameter, 1.0 mm drill, leaving 0.5 mm nominal annular copper per side before process tolerances.
- Required post-fabrication check: continuity/low-resistance measurement between front and back copper after solder filling.

## Generated family

| Back diameter | Board side | Front margin | Back margin | KiCad parse | DRC violations | Unconnected |
| ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 5 mm | 10 mm | 1 mm | 2.5 mm | pass | 0 | 0 |
| 10 mm | 18.75 mm | 5.375 mm | 4.375 mm | pass | 0 | 0 |
| 15 mm | 25 mm | 8.5 mm | 5 mm | pass | 0 | 0 |
| 20 mm | 30 mm | 11 mm | 5 mm | pass | 0 | 0 |

## Project checks

- KiCad CLI version: 10.0.6.
- Konnect project metadata: project, schematic, and PCB stems match; reported KiCad compatibility is 10.0.
- Empty schematic ERC: 0 errors, 0 warnings.
- Base 8/20/30 PCB through KiCad CLI: 0 DRC violations, 0 unconnected items, 0 footprint errors.
- Base 8/20/30 PCB through Konnect `run_drc`, severity `info`: 0 errors, 0 warnings, 0 unconnected items, 0 total violations.
- Front/back visual review: all eight 784 × 784 renders were inspected. Every circular contact and drilled hole is concentric with its square outline, front pads remain 8 mm, back pads increase as specified, and no silkscreen or text overlaps exposed copper.
- Determinism: the base board and all four variants produced identical SHA-256 values before and after regeneration from `series.csv`.
- Generator guard evidence retained from the reusable helper validation: invalid edge clearance and overwrite without `--force` are rejected before output is written.

## Remaining physical validation

- Confirm the actual LPKF tool diameter, isolation width, drill runout, and front/back registration before relying on the 1 mm edge margin of the 10 mm board.
- Fabricate one coupon of each size and record measured outline, pad diameter, hole diameter, front/back continuity, solder joint flatness, snap retention, and film-electrode attachment quality.

## CircuitPro RP 1.0 import compatibility — 2026-09-17

- Operator screenshots from CircuitPro RP 1.0 Advanced show the top copper, bottom copper, and profile geometry parsed with the intended 8 mm, 15 mm, and approximately 25 mm displayed extents for the 8/15/25 variant.
- The prior PTH Excellon was parsed and displayed as `1 x 1 mm`, matching the geometric extent of its single 1.0 mm drill hit. That display is not evidence of a `1:1` coordinate precision.
- The explicit drill-file error shown in the screenshots names the empty `NPTH.drl`; a separate error names the ZIP archive. Other messages show attempts to classify Gerber job metadata and duplicate import candidates. These are packaging failures, not evidence that the valid PTH coordinate failed to parse.
- CircuitPro also reported ignored KiCad X2 object/net attributes such as `TO,N,CONTACT`. The replacement Gerbers were therefore generated with KiCad CLI `--no-x2 --no-netlist` while retaining standard Protel layer extensions.
- Every replacement variant directory contains exactly four machine inputs: top copper, bottom copper, profile, and one non-empty 1.0 mm Excellon drill. Empty NPTH outputs, Gerber job files, ZIP archives, and documentation are excluded from the directories selected for import.
- The replacement Excellon contract is millimetres, absolute origin, explicit decimal coordinates, full header, no Y mirror, one 1.000 mm tool, and one drill hit at the common copper center. All copper flashes and the drill hit resolve to the same absolute coordinate.
- Final installed-software acceptance remains open until one clean four-file directory is imported in CircuitPro RP 1.0 and the operator confirms the four target mappings and a concentric overlay before toolpath generation.
