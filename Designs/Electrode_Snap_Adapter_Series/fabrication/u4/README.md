# CircuitPro RP 1.x / ProtoLaser U4 Inputs

Each child directory is one independently imported package. Filenames match the verified CircuitPro targets.

| File | Format | Target |
| --- | --- | --- |
| `TopLayer.gtl` | GerberX | `TopLayer` |
| `BottomLayer.gbl` | GerberX | `BottomLayer` |
| `BoardOutline.gm1` | GerberX | `BoardOutline` |
| `CutInside.gm2` | GerberX | `CutInside` |
| `DrillPlated.drl` | Excellon | `DrillPlated` |

The four single-board packages omit `CutInside.gm2`. The 17-up panel contains one continuous `BoardOutline` and seventeen closed contours in `CutInside`; do not map those seventeen contours to `BoardOutline`.

Regenerate or audit every package from the repository root:

```sh
python3 .agents/skills/kicad-konnect/scripts/export_circuitpro_u4_packages.py \
  export Designs/Electrode_Snap_Adapter_Series --force

python3 .agents/skills/kicad-konnect/scripts/export_circuitpro_u4_packages.py \
  audit Designs/Electrode_Snap_Adapter_Series
```

The exporter derives layers, `Coupon.Cuts`, drill counts, and contour counts directly from the KiCad PCBs. It runs error-level DRC, uses `--no-x2 --no-netlist`, exports decimal millimetre Excellon with PTH/NPTH separation, omits empty drill files, applies target-aligned names, validates exact file sets and counts, and compares audit output with the current sources while ignoring timestamps.
