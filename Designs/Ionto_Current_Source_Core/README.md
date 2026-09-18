# R1218N041A Single-Channel Constant-Current Core

This project is a minimum verifiable implementation of the paper's R1218-based stimulation architecture. It accepts a protected 1-cell LiPo and provides one two-wire constant-current output. Charging, timing, wireless power, channel decoding, switches, and miniaturization are deliberately omitted.

This is an experimental electrical prototype, not a medically certified device. Do not connect it to a person until current limits, isolation, electrodes, open-load behavior, fault behavior, and applicable safety requirements have been reviewed by a qualified engineer.

## Electrical operation

`U1` is `R1218N041A-TR-FE`, a SOT-23-6 boost LED/current driver with an internal switch, internal rectifier diode, 0.2 V feedback reference, and approximately 18.5 V typical over-voltage protection. `CE` is routed to J3 instead of being permanently tied high.

J3 is a two-pin 2.54 mm SMT header:

- Pin 1: VIN / always-on source
- Pin 2: CE / external enable input

Fit a standard 2.54 mm shunt across pins 1–2 for always-on operation. Remove the shunt and drive pin 2 for external control. The external controller must share board GND through a separate ground connection.

The R1218 includes a CE pull-down specified at 600 kΩ to 2.2 MΩ, so removing the shunt leaves the converter disabled even when no external controller is attached. For an external logic source, the datasheet specifies CE low at no more than 0.5 V and CE high at at least 1.5 V; the CE pin must remain within its absolute input limits relative to the battery/GND domain.

The current path is:

`VBAT → L1 → U1 internal boost stage → VOUT → J2 pin 1 → external load → J2 pin 2 → VFB → R1 → GND`

U1 regulates the VFB node to nominally 0.2 V, so:

`ISTIM = 0.2 V / R1`

The default `R1 = 536 Ω ±1%` gives `ISTIM ≈ 373 µA`, corresponding to approximately 0.261 mA/cm² over 143 mm². For the 199 mm² electrode, use the 402 Ω carrier for approximately 498 µA or 0.250 mA/cm². The R1218 feedback specification is 0.19–0.21 V, so IC feedback tolerance alone produces approximately ±5% current variation before resistor tolerance and operating effects.

## Assembly-selected current

| R1 | Nominal current | Use |
|---:|---:|---|
| 665 Ω | 301 µA | Low end of configured range |
| 536 Ω | 373 µA | 143 mm² default |
| 402 Ω | 498 µA | 199 mm² default |
| 267 Ω | 749 µA | Intermediate setting |
| 200 Ω | 1.00 mA | Larger-area validation setting |
| 133 Ω | 1.50 mA | Nominal maximum setting |

For a fixed-current carrier, use one fixed resistor per assembly. The main board carries a two-position 2.54 mm SMT female socket. R1 is mounted on a removable two-pin RSET carrier made from a mating `TSM-102-01-S-SV` header and a tiny carrier PCB; it is not inserted into the socket as a bare 0805 part. This keeps resistor changes solder-free at the core board. Do not populate multiple fixed values in parallel.

For bench adjustment, a Bourns `3223W-1-102E` 1 kΩ, 11-turn, top-adjust SMD trimmer can replace the fixed RSET electrically. Connect it as a two-terminal rheostat by tying the wiper to one end, then connect those two effective terminals to the two existing RSET pads. Its physical three-pad footprint does not match the present two-pad RSET socket, so use short wires or a simple two-pin header connection for validation rather than soldering it directly onto the socket footprint. Approximately 667 Ω sets 300 µA, 402 Ω sets 498 µA, 267 Ω sets 749 µA, 200 Ω sets 1.00 mA, and 133 Ω sets 1.50 mA. Preset the resistance with a meter before power-up; the trimmer scale is not a calibrated current indication.

## Component roles and selected parts

| Ref | Selected part/value | Package/footprint | Purpose |
|---|---|---|---|
| J1 | Samtec `TSM-102-01-S-SV` | 1×2, 2.54 mm vertical SMT header | Protected 1S LiPo input; pin 1 BAT+, pin 2 GND; accepts a simple flying-lead harness |
| U1 | Nisshinbo `R1218N041A-TR-FE` | SOT-23-6 | Boost conversion and 0.2 V constant-current regulation |
| L1 | Bourns `SRN4018-220M`, 22 µH | 4.0 × 4.0 mm SMD | Boost energy storage; 900 mA rated, shielded |
| C1 | Murata `GRM21BR71A105KA01L`, 1 µF 10 V X7R | 0805 hand-solder pads | Battery/input bypass |
| C2 | KEMET `C0805C224K5RACTU`, 0.22 µF 50 V X7R | 0805 hand-solder pads | Boost/output filtering |
| R1 | Yageo `RC0805FR-07536RL`, 536 Ω 1% | 0805 on removable two-pin RSET carrier | Default 373 µA setting for 143 mm² electrode |
| RT1 option | Bourns `3223W-1-102E`, 1 kΩ ±20%, 11-turn | 3.9 × 3.2 mm top-adjust SMD trimmer connected to the two RSET pads | Adjustable validation replacement for the fixed RSET |
| XS1 | Samtec `SSM-102-L-SV-K-TR` | 1×2, 2.54 mm vertical SMT female socket | Board-side receptacle for the removable RSET carrier; represented by R1's footprint in the current schematic |
| XP1 | Samtec `TSM-102-01-S-SV` | 1×2, 2.54 mm vertical SMT male header | Mating connector on the removable RSET carrier |
| J2 | Samtec `TSM-102-01-S-SV` | 1×2, 2.54 mm vertical SMT header | Stimulation output; pin 1 STIM+, pin 2 STIM−/VFB; accepts a simple flying-lead harness |
| J3 | Samtec `TSM-102-01-S-SV` | 1×2, 2.54 mm vertical SMT header | VIN-to-CE always-on jumper and external CE input |

The R1218 contains the boost rectifier diode, so the design intentionally has no external Schottky diode. C1 and C2 meet the datasheet's minimum application values, and L1 is within the recommended 10–22 µH range.

Distributor evidence checked 2026-09-16: DigiKey listed the R1218N041A, SRN4018-220M, C1, C2, the Samtec SSM-102 board socket, and the TSM-102 two-pin SMT header used by the RSET carrier and CE jumper as active and available. The selected Yageo 0805 RSET values covering approximately 300 µA–1.50 mA were checked on 2026-09-17 and selected from active, cut-tape parts with substantial DigiKey stock. The optional Bourns `3223W-1-102E` SMD trimmer was also active and available in cut tape. Inventory is volatile and must be rechecked before ordering.

The English, text-only procurement table is stored in [`BOM.csv`](BOM.csv). It includes the five-board build quantities, RSET options, selected DigiKey order numbers, useful 0805 stock parts, price estimates, and the dated inventory snapshot. Recheck price, stock, lifecycle, and exact order suffix before purchasing.

J1, J2, J3, and the removable RSET carrier deliberately reuse the same 2.54 mm connector family wherever mating gender permits. This minimizes unique inventory and makes future connector changes a harness or small-adapter problem rather than a core-board redesign.

## PCB implementation

The active board is 27 × 20 mm, an 18.2% area reduction from the previous 30 × 22 mm revision. All eight footprints and all routed copper are on the front side, with zero vias; the production pour variant adds a front-side GND zone while the matching primary remains routing-only. The placement follows the power/current path from the battery header at the left, through the inductor and R1218 stage, to the stimulation header at the right. The CE jumper sits beside the controller/output area, and the removable RSET socket remains accessible along the lower edge.

The ordinary/default routing width is 0.25 mm (about 10 mil), including the CE control path. Current- and noise-sensitive nets retain wider classes: main BAT traces are 0.8 mm, the switching-node trunk is 1.0 mm with short 0.4 mm pad escapes, and stimulation routing is 0.6 mm with local pad escapes down to 0.25 mm. These widths are intended for a hand-soldered prototype and are not a substitute for a thermal/current review at a chosen copper weight.

For the soldermask-free LPKF U4 prototype, the front GND zone uses 1.00 mm clearance to other-net copper and a 1.00 mm board-edge inset, with 0.25 mm minimum fill thickness, a 0.50 mm thermal-relief gap, and 0.50 mm thermal spokes. One millimetre preserves a generous hand-soldering moat while reducing the isolation width by one third relative to the rejected 1.50 mm trial. C1 was rotated to make its BAT+ and GND escapes direct, and C1, C2, R1, U1, and J1 now have explicit routed GND continuity so the board remains electrically complete when the pour is omitted. C1 and C2 use deliberate local solid-zone connections because the small 0805 pads cannot accept two 0.50 mm thermal spokes in the available geometry.

The matching primary PCB is intentionally the routing-only design source and contains no zone. It must pass DRC with zero unconnected items before production generation derives [`variants/Ionto_Current_Source_Core_With_Pour.kicad_pcb`](variants/Ionto_Current_Source_Core_With_Pour.kicad_pcb). The production exporter refills and checks a temporary copy of that 1.00 mm GND-zone definition, leaving both design sources unchanged.

The repo-wide [`repository-defaults.json`](../../.agents/skills/kicad-pcb-layout/references/repository-defaults.json) owns the common route-first workflow, single-sided/zero-via policy, 0.25 mm default clearance and routing width, wider functional net classes, explicit GND-tree requirement, 1.00 mm pour clearance and edge inset, thermal settings, DRC gates, and automatic dual manufacturing outputs. KiCad project net classes mirror those defaults; this design has no local override.

CircuitPro-ready single-sided U4 Gerber output is under [`fabrication/u4/Ionto_Current_Source_Core/`](fabrication/u4/Ionto_Current_Source_Core/) for the routing-only primary and [`fabrication/u4/Ionto_Current_Source_Core_With_Pour/`](fabrication/u4/Ionto_Current_Source_Core_With_Pour/) for the generated pour variant. Each package contains only `TopLayer.gtl` and `BoardOutline.gm1` because the PCB has no back copper, vias, or drilled holes.

Matching LightBurn templates are under [`fabrication/lightburn/Ionto_Current_Source_Core/`](fabrication/lightburn/Ionto_Current_Source_Core/) and [`fabrication/lightburn/Ionto_Current_Source_Core_With_Pour/`](fabrication/lightburn/Ionto_Current_Source_Core_With_Pour/). Each `FrontMask_TopView.dxf` is a millimetre vector export of `F.Mask` plus `Edge.Cuts`; laser settings are intentionally not stored in the geometry file.

## Schematic contract and archive

`schematic_topology.json` is the pin-level connectivity contract. The reviewed KiCad sheet is the presentation source of truth. Ordinary topology is shown by explicit orthogonal wires; only the conventional common GND network uses repeated power symbols.

The replaced TPS61040/TLV431/MCP6001 implementation is preserved under `archive/legacy_tps61040/` with its schematic, topology, documentation, validation record, and render.

## Known engineering limitation

The fixed and adjustable RSET values provide nominal settings from approximately 300 µA to 1.50 mA. The R1218 datasheet specifies a 400 mA internal switch, a 400–1000 mA switch-current-limit range, and application examples up to 20 mA load current, so 1.50 mA is well below the converter's demonstrated load-current range. Actual regulated current still follows feedback-voltage tolerance and must be measured across battery voltage and representative load resistance. A truly open output draws no regulated load current and tests OVP behavior only; use a suitable dummy load to verify current regulation.
