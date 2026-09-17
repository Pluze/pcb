# LPKF CircuitPro RP 1.x / ProtoLaser U4 Import Package

This directory is a compatibility-oriented machine-input package for the four double-sided electrode snap-adapter variants. Each variant directory contains exactly four files that should be selected together in CircuitPro. Do not select this parent directory as a mixed batch.

## Select one variant directory

| Directory | Top contact | Bottom contact | Profile centerline |
| --- | ---: | ---: | ---: |
| `Circular_Contact_F8_B5_S10` | 8 mm | 5 mm | 10 x 10 mm |
| `Circular_Contact_F8_B10_S18p75` | 8 mm | 10 mm | 18.75 x 18.75 mm |
| `Circular_Contact_F8_B15_S25` | 8 mm | 15 mm | 25 x 25 mm |
| `Circular_Contact_F8_B20_S30` | 8 mm | 20 mm | 30 x 30 mm |

Each selected directory contains only:

| File | Format | CircuitPro assignment |
| --- | --- | --- |
| `Top.gtl` | Gerber X / RS-274X without X2 net-object attributes | `TopLayer` |
| `Bottom.gbl` | Gerber X / RS-274X without X2 net-object attributes | `BottomLayer` |
| `Profile.gm1` | Gerber X profile | `BoardOutline` |
| `Drill_1mm.drl` | Excellon | `DrillPlated` |

There is intentionally no ZIP archive, Gerber job file, or empty NPTH drill file in an import directory. CircuitPro RP 1.x may try to classify every selected item and report import failures for those non-artwork or empty files.

## Excellon contract

`Drill_1mm.drl` uses the current KiCad decimal Excellon defaults required for this package:

- units: millimetres;
- values: absolute;
- zero format: explicit decimal;
- Y mirroring: off;
- full header: enabled;
- one tool: 1.000 mm;
- one coordinate: the same absolute center as both copper flashes.

In decimal mode, a CircuitPro display of `1 x 1 mm` for this file is the geometric extent of the single 1.0 mm circular drill hit. It is not an indication that CircuitPro inferred a `1:1` coordinate precision. KiCad's `3:3` precision field is disabled for decimal-format Excellon and is not needed to interpret the explicit coordinate.

The hole remains a logical PTH in the KiCad design because it is the intended electrical interconnect between the two contact surfaces. The selected `U4_DoubleSided_NoTHP` process does not plate the barrel: process the hole without a THP step, then wick solder through it and verify front-to-back continuity. It is not a mechanical-only NPTH.

## CircuitPro import sequence

1. Create the `U4_DoubleSided_NoTHP` project with the material entry matching the actual substrate and copper thickness.
2. Open one variant directory and select only its four files. Do not import a parent folder, archive, README, job file, or an earlier export.
3. Keep the format selectors on `GerberX` for the three Gerbers and `Excellon` for the drill, then set each lower `Target` selector to the value in the table above. Do not leave a target on the filename-named layer, and do not manually mirror `Bottom.gbl`; let the two-sided CircuitPro workflow handle the material turn.
4. Confirm the displayed contact sizes and profile: top 8 mm, bottom equal to the chosen variant, one 1 mm drill, and the profile listed above.
5. Add the CircuitPro/U4 template's normal registration features outside the finished profile. Complete both copper sides before cutting the profile.
6. Use the validated material-library laser process and complete rub-out or the appropriate hatch strategy so unwanted copper outside the circular contacts is removed.
7. Process the profile last, clean the copper, solder-fill the center hole, and perform a low-resistance continuity test.

Gerber profile `Size/Format` may include the 0.05 mm drawing aperture and therefore display 0.05 mm larger than the profile centerline, for example 25.05 x 25.05 mm for the 25 mm variant. The actual profile path coordinates remain exactly 25 x 25 mm; CircuitPro must use the profile path centerline for cutting.

## Verification

- Generated with KiCad CLI 10.0.6.
- Gerbers were exported with `--no-x2 --no-netlist` to avoid the `TO,N,...` object-attribute warnings observed in CircuitPro RP 1.0.
- Excellon was exported as millimetre, absolute, decimal, full-header data with PTH and NPTH separated; the empty NPTH result was excluded.
- All four source boards previously passed DRC with 0 violations and 0 unconnected items.
- File-level validation confirms one 1.000 mm drill hit at the common copper center and profile path dimensions of 10, 18.75, 25, and 30 mm respectively.
- Final acceptance still requires a clean import and visual overlay check in the installed CircuitPro RP 1.0 system, followed by a physical process coupon.
