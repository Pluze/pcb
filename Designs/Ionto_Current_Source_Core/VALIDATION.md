# Design-Specific Validation Evidence

## Current state — R1218N041A redesign

- The active schematic implements one coherent `R1218N041A-TR-FE` constant-current boost stage with a two-pin VIN-to-CE SMT jumper header and an exchangeable RSET socket.
- The pin-level contract contains six electrical networks and 26 owned endpoints.
- Closed-file connectivity validation on 2026-09-17 reported zero floating wire endpoints and zero unconnected component pins.
- KiCad ERC on 2026-09-17 reported zero errors and zero warnings.
- Exact U1 pin mapping was checked against the R1218 datasheet: CE=1, VOUT=2, VIN=3, LX=4, GND=5, VFB=6.
- CE external-control behavior was checked against the datasheet: internal pull-down 600 kΩ to 2.2 MΩ, low threshold no more than 0.5 V, and high threshold at least 1.5 V.
- The default current calculation is `0.2 V / 536 Ω = 373.13 µA`, corresponding to 0.261 mA/cm² over 143 mm².
- The 1.50 mA nominal maximum option uses 133 Ω. Including the datasheet's 0.19–0.21 V feedback range and ±1% resistor tolerance gives an estimated 1.41–1.59 mA component-tolerance span before operating effects.
- U1 is the `041A` variant: internal rectifier diode and 17–20 V over-voltage threshold. The schematic therefore intentionally omits an external diode.
- All main-board physical components have assigned footprints. C1 and C2 use enlarged 0805 hand-solder pads; U1 uses SOT-23-6; L1 uses the Bourns SRN4018 footprint; J1/J2/J3 use the same 2.54 mm SMT header family; the board-side RSET socket is the matching 2.54 mm SMT socket family.
- The rendered sheet was inspected for explicit current flow, pin-order clarity, orthogonal routing, pin escape length, crossings, wire-through-symbol errors, and text collisions. Ordinary topology is explicit; repeated symbols are used only for GND.
- The pre-redesign TPS61040 implementation is preserved at `archive/legacy_tps61040/` and was not discarded.

## Procurement evidence checked 2026-09-16

- DigiKey: `R1218N041A-TR-FE` active, SOT-23-6, cut tape available, approximately 590 in stock at the latest lookup.
- DigiKey: `SRN4018-220M` active, 22 µH, 900 mA, cut tape available, approximately 14,042 in stock at lookup.
- DigiKey: `GRM21BR71A105KA01L` active, 1 µF 10 V X7R 0805, approximately 1.24 million in stock at lookup.
- DigiKey: `C0805C224K5RACTU` active, 0.22 µF 50 V X7R 0805, approximately 351k in stock at lookup.
- DigiKey, checked 2026-09-17: `RC0805FR-07536RL` active, 536 Ω 1% 0805, cut tape `311-536CRCT-ND`, approximately 117k in stock at lookup.
- DigiKey, checked 2026-09-17: `RC0805FR-07665RL`, `RC0805FR-07402RL`, `RC0805FR-07267RL`, `RC0805FR-07200RL`, and `RC0805FR-07133RL` were active 1% 0805 cut-tape options with stock snapshots ranging from approximately 49k to 84k pieces.
- DigiKey, checked 2026-09-17: Bourns `3223W-1-102E`, 1 kΩ ±20%, 11-turn top-adjust SMD trimmer, cut tape `3223W-1-102ECT-ND`, approximately 12k in stock at lookup.
- DigiKey: Samtec `SSM-102-L-SV-K-TR` active, 2-position 2.54 mm SMT socket, approximately 1,103 in stock at lookup.
- DigiKey: Samtec `TSM-102-01-S-SV` active, 2-position 2.54 mm SMT male header with cut-tape ordering, approximately 607 in stock at the latest lookup; Mouser also lists the exact MPN.
- The same Samtec `TSM-102-01-S-SV` 2.54 mm SMT header is selected for battery input, stimulation output, CE jumper, and the removable RSET carrier where a male header is required. Recheck the exact order suffix and quantity before purchase.

## Open design-specific items

- Bench-test current accuracy at 3.0, 3.6, and 4.2 V battery input across the intended load range.
- Measure startup transient, ripple, maximum compliance voltage, and open-load behavior.
- Use a suitable dummy load for current-regulation measurements; a truly open output can validate OVP behavior but cannot carry the programmed current.
- Confirm the paper-derived sub-milliamp operating point is stable despite the datasheet's milliamp-oriented characterization.
- Design and mechanically verify the small removable RSET carrier PCB before PCB release; the bare 0805 resistor must not be treated as directly pluggable into the board socket.
- Bench-verify every populated 300 µA–1.50 mA RSET option and label fixed carriers with both resistance and nominal current.
- For adjustable validation, verify the trimmer wiper-to-end short and preset its resistance with a meter before power-up; no fixed series fallback is included in this validation configuration.
- Independently review suitability and safety before any human-connected experiment.

## PCB status

The active R1218 PCB is implemented on a 30 × 22 mm outline with eight front-side SMT footprints, front-side copper only, a front-side GND zone, 27 routed track segments, zero vias, and zero back-copper tracks. Placement scoring on 2026-09-16 was 100/100 with no courtyard overlap or outside-board failure. The GND zone definition was revised on 2026-09-17 for soldermask-free LPKF U4 milling and hand soldering: other-net clearance, minimum fill thickness, thermal gap, and thermal spoke width are all 0.50 mm. The first refill proved that C1 pad 2 could form only one thermal spoke and became electrically unconnected, so that GND pad now uses a local solid-zone override while retaining 0.50 mm clearance from every other net. After that correction, KiCad's full DRC with zone refill reported zero errors, zero unconnected items, and one warning. The remaining warning is the embedded `L_Bourns-SRN4018` library-copy mismatch: Konnect refused to refresh it because the current library footprint contains a property clause it cannot yet preserve losslessly. Pad geometry, net assignment, placement, and courtyard were independently retained and checked; this warning must be re-evaluated against the installed library before manufacturing release. The refilled zone was visually inspected at board scale with no observed narrow slivers or isolated islands, but DRC and visual review do not validate cutter access or the physical isolation channel; confirm the values with a U4 process coupon before milling the functional board. The pre-R1218 PCB remains only under `archive/legacy_tps61040/` and is not synchronized with the active schematic.

The CircuitPro RP 1.x machine-input directory contains exactly two Gerber files: front copper and the 30 × 22 mm profile. Both were regenerated with KiCad CLI 10.0.6 using `--no-x2 --no-netlist` so the older importer does not encounter KiCad X2 net-object attributes. No bottom copper, drill output, Gerber job file, archive, or documentation is present in the directory selected for import. Installed-software import confirmation and a physical U4 process coupon remain required.
