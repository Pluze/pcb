# Validation

Validated with KiCad 10.0.6. Commands run from the repository root:

```sh
./pcb check --design Ionto_Current_Source_Core
./pcb review --design Ionto_Current_Source_Core
./pcb verify --design Ionto_Current_Source_Core --no-cache
```

## Electrical and source agreement

- ERC: 0 errors and 0 warnings. The topology contract contains six nets and 26
  owned endpoints, including power symbols.
- Native exported-netlist comparison: 8 components, 20 physical endpoints, zero
  value/footprint/connectivity differences; source hashes remain unchanged.
- U1 mapping matches R1218 041A: CE=1, VOUT=2, VIN=3, LX=4, GND=5, VFB=6.
- Nominal current: 0.2 V / 536 ohm = 373.13 microampere. The 133 ohm option gives
  1.50 mA nominal and 1.41–1.59 mA with documented feedback/resistor tolerances.
- All 8 references lack structured schematic MPN fields. The procurement catalog
  is separate; stock, exact suffixes and catalog-to-schematic linkage need review.

## PCB and manufacturing

- 27 × 20 mm; 8 front-side SMT footprints; 53 F.Cu segments, 113.4515 mm total;
  zero vias, back-copper tracks, non-45-degree segments or degree-two right angles.
- Local/control routing: 0.25 mm; stimulation: 0.30 mm; BAT+, LX and outer GND:
  0.50 mm. LX is 3.00 mm long. Selectable 6 mil tracks are unused.
- Routing-only and refilled-pour boards: 0 DRC errors, 0 unconnected items, and
  1 retained embedded-L1 library mismatch warning per board.
- Explicit GND routing is complete before pour. Pour spacing, thermals and
  edge inset follow the repository profile. C1/C2 retain solid-zone connections.
- U4, LightBurn and Gerber freshness audits pass for both variants. U4 packages
  contain TopLayer.gtl and BoardOutline.gm1; there are no drills or back copper.
- LightBurn has one front-mask DXF per variant; ezdxf reports 0 errors/0 fixes.
  Gerber packages include declared layers, native job and matching drill files.
- Board/pour previews were visually reviewed. Current regulation, switching
  behavior, laser time and physical yield require measurements on actual hardware.
