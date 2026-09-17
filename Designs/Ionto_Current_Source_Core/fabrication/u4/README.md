# LPKF ProtoLaser U4 Single-Sided Fabrication Package

This package is prepared for the active `Ionto_Current_Source_Core` PCB. The design is a 30 x 22 mm, front-copper-only SMT board with a filled front GND zone, 27 front-layer track segments, zero vias, and no drilled holes.

## CircuitPro layer mapping

Open `machine_input/` and import its two files together:

| Filename | CircuitPro assignment | Purpose |
| --- | --- | --- |
| `Top.gtl` | Top copper | Pads, routed signals, and the filled front GND zone |
| `Profile.gm1` | Board outline / cutting | 30 x 22 mm finished outline |

Do not add a bottom-copper layer, drill operation, solder-mask layer, paste layer, or silkscreen layer. KiCad's automatically generated PTH and NPTH drill files contain no tool definitions or coordinates and are deliberately omitted. The machine-input directory contains no ZIP archive, job file, or documentation for CircuitPro to misclassify.

## CircuitPro process requirements

- Create a one-copper-layer CircuitPro project matching the actual substrate material, substrate thickness, and copper thickness.
- Keep the material fixed until both front-copper processing and outline cutting are complete. No front/back registration fiducials are required because the manufacturing package has no back-side artwork and no side change.
- Assign the Gerber as top copper; do not mirror it.
- Use the validated U4 material-library process for the actual copper-clad stock. Laser power, focus, repetition rate, hatch, and pass count are process parameters and are not encoded in the Gerber.
- Use complete laser rub-out or the appropriate laser hatch strategy for non-Gerber copper. The Gerber includes the intended GND plane; copper in clearances between that plane and other nets must be removed completely.
- Inspect every 0.50 mm isolation channel and thermal feature in the CircuitPro preview before starting the machine.
- Process the board outline last so that the workpiece remains fixed while the copper pattern is formed.
- This package contains no solder mask. Clean the copper and inspect for conductive debris and copper bridges before assembly.

## Substrate warning

This package assumes genuinely single-sided copper-clad stock. If double-sided copper-clad stock is used, the unprocessed back remains a continuous floating copper sheet. Do not leave that condition implicit on this experimental boost/current-source board. Either use single-sided stock or create and verify a separate U4 operation that removes the unwanted back copper. Removing back copper requires a side change even though the electrical PCB design remains single-sided.

## Verification status

- Generated with KiCad CLI 10.0.6 using `--no-x2 --no-netlist` for compatibility with CircuitPro RP 1.x.
- Exported source layers: `F.Cu` and `Edge.Cuts` only.
- Board extent: 30 x 22 mm.
- DRC: 0 errors and 0 unconnected items.
- Remaining DRC warning: the placed `L_Bourns-SRN4018` footprint for L1 differs from the currently installed library copy. This is a library-consistency warning; the placed pad geometry, net assignment, position, and courtyard were retained and previously checked, but the exact installed-library comparison must still be resolved or explicitly accepted before manufacturing release.
- Physical U4 qualification remains required. Make a process coupon and inspect isolation width, GND-zone clearances, thermal connections, copper debris, and edge quality before treating the functional board as qualified.
