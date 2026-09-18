# CircuitPro RP 1.x / ProtoLaser U4 Inputs

`Ionto_Current_Source_Core/` contains exactly two files for this front-copper-only board:

| File | Format | Target |
| --- | --- | --- |
| `TopLayer.gtl` | GerberX | `TopLayer` |
| `BoardOutline.gm1` | GerberX | `BoardOutline` |

Regenerate or audit the package from the repository root:

```sh
python3 .agents/skills/kicad-konnect/scripts/export_circuitpro_u4_packages.py \
  export Designs/Ionto_Current_Source_Core --force

python3 .agents/skills/kicad-konnect/scripts/export_circuitpro_u4_packages.py \
  audit Designs/Ionto_Current_Source_Core
```

The exporter derives the front-only copper and zero-drill contract directly from the PCB. It runs error-level DRC, uses `--no-x2 --no-netlist`, applies target-aligned names, validates the continuous board outline, and compares audit output with the current KiCad source while ignoring timestamps.
