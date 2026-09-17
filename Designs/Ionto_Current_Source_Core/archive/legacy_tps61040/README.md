# Single-Channel Adjustable Constant-Current Core

This is a minimum verifiable 1-cell LiPo powered constant-current stimulation core. It intentionally omits charging, timing, wireless power, channel selection, and miniaturization. The board exposes only a battery input and one two-wire stimulation output.

This is an experimental electrical prototype, not a medically certified device. Do not connect it to a person until the electrical limits, isolation, electrodes, fault behavior, and applicable safety requirements have been reviewed by a qualified engineer.

## Functional Architecture

1. **Battery input:** J1 accepts a protected 1-cell LiPo, nominally 3.0–4.2 V.
2. **Compliance supply:** U1, L1, D1, C1, C2, R1, and R2 form a TPS61040 boost converter. The nominal target is approximately 25.9 V:

   `VBOOST = 1.233 V × (1 + 2.00 MΩ / 100 kΩ) ≈ 25.9 V`

3. **Reference:** U2 is a TLV431A 1.24 V shunt reference. R3 biases it from the battery.
4. **Current servo:** U3 compares the 1.24 V reference with the voltage across R5 and drives Q1 through R4. The loop forces:

   `ISTIM ≈ 1.24 V / R5`

5. **Output:** J2 pin 1 receives the boosted positive supply through R6. J2 pin 2 returns through Q1 and R5. R6 adds passive fault-current limiting but also reduces usable compliance voltage.

## Assembly-Selected Current

R5 is intentionally a fixed assembly option rather than a potentiometer.

| R5 | Nominal current |
|---:|---:|
| 12.4 kΩ | 100 µA |
| 9.53 kΩ | 130 µA |
| 4.99 kΩ | 250 µA |
| 2.49 kΩ | 500 µA |

The default is 9.53 kΩ for approximately 130 µA. Actual current depends on the TLV431 tolerance, resistor tolerance, op-amp offset, MOSFET operating point, available battery voltage, boost regulation, and load compliance.

## Component Roles

| Ref | Selected part/value | Purpose |
|---|---|---|
| J1 | 2-pin JST-PH style SMT connector | Battery input |
| U1 | TPS61040DBVR | Generates the higher compliance voltage |
| L1 | 10 µH, at least 0.5 A | Boost energy storage |
| D1 | MBR0540T1G | 40 V Schottky boost rectifier |
| C1 | 4.7 µF, 10 V, X7R | Boost input bypass |
| C2 | 2.2 µF, 50 V, X7R | Boost output filtering |
| R1/R2 | 2.00 MΩ / 100 kΩ, 1% | Sets approximately 25.9 V boost output |
| U2 | TLV431AIDBVR | 1.24 V precision shunt reference |
| R3 | 10 kΩ, 1% | Biases the reference |
| U3 | MCP6001T-I/OT | Error amplifier for the current loop |
| R4 | 1 kΩ | Isolates the op-amp from the MOSFET gate |
| Q1 | 2N7002-7-F | High-voltage-side-compliant N-MOS current sink element |
| R5 | assembly option, 1% | Sets the stimulation current |
| R6 | 33 kΩ, 1% | Passive series fault-current limit |
| C3 | 100 nF, 10 V, X7R | Local op-amp supply bypass |
| TP1/TP2 | SMT test points | VBOOST and current-sense measurement |

Exact distributor stock and approved alternates must be recorded with a lookup date before ordering; stock is not treated as a permanent design property.

## Schematic Generation Contract

`schematic_topology.json` is the pin-level connectivity source of truth. The KiCad schematic remains the reviewed presentation source of truth for symbol placement, orientation, text, wires, and junctions. The two must be compared after every generated change.
