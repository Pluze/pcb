# LM555 LED Flasher

An educational astable 555 timer that flashes one LED. The design adapts the classroom topology into a compact, readable, all-SMT KiCad project intended for simple prototype fabrication.

![PCB top view](assets/pcb-top.png)

## Circuit

- `U1`: LM555xM, SOIC-8.
- `R1`: 1 kΩ, 0603.
- `R2`: 100 kΩ, 0603.
- `R3`: 330 Ω LED current limiter, 0603.
- `C1`: 10 µF polarized SMD aluminum electrolytic, 5 × 5.3 mm.
- `C2`: 10 nF, 0603, control-voltage bypass.
- `D1`: generic indicator LED, 0805.
- `BT1`: 2-pin JST-PH SMD power connector.

The timing network follows the standard astable relationship approximately described by `f = 1.44 / ((R1 + 2R2) × C1)`. Actual flash rate depends on component tolerance, leakage, and the chosen 555 variant.

## Component Strategy

All board-mounted parts are SMT. The 0805 LED remains visible and hand-solderable; the 0603 passives keep the board compact without forcing unusually small geometry.

`C1` does not electrically have to be electrolytic. This implementation uses an SMD aluminum electrolytic because its effective 10 µF capacitance is more predictable across a typical low-voltage supply than a small high-value MLCC subject to DC-bias derating. A ceramic alternative should use an adequately rated 1206 or 1210 X7R part, verify effective capacitance at the actual bias voltage, and recalculate the timing range.

`D1` is intentionally generic because the classroom reference does not specify color or optical output. Select a real 0805 LED whose forward voltage and current are compatible with the supply, LM555 output capability, and `R3`; re-evaluate `R3` if those assumptions change.

## Layout Intent

- Board outline: approximately 40 mm × 25 mm with rounded corners.
- Components and all routing are on `F.Cu`.
- Zero vias and zero jumper resistors are used.
- Normal tracks are 0.4 mm; six short pad neck-down segments are 0.3 mm.
- The connector is placed at the left edge, the LED/output section follows it, the timer occupies the center, and timing components sit to the right.
- Designators and polarity marks are kept upright, visible, and inside the board.

## Reference Adaptation

The schematic preserves the classroom circuit's recognizable power rails, 555 pin relationships, timing divider, control bypass, and LED output path. Layout geometry was adjusted where KiCad symbol geometry, SMT packages, electrical loop length, or silkscreen readability required it.

![Schematic](assets/schematic.png)

## Limitations

This is a reference and experimental design, not a production release. Confirm the exact LM555 variant, supply range, LED, capacitor voltage rating, connector polarity, fabrication rules, and assembly process before building it.
