# Validation

Current validation snapshot for the generated circular-contact family.

## Geometry and PCB

- Source labels establish back-contact diameters of 5, 10, 15, and 20 mm. The 5 mm source geometry has no complete matching square, so its 10 mm board size is a project choice.
- Generated board sides are 10, 18.75, 25, and 30 mm; every front contact is 8 mm. Each board has one 1.0 mm drilled, 2.0 mm copper center interconnect.
- KiCad 10.0.6 parses every generated board. ERC reports 0 errors and 0 warnings; DRC reports 0 violations and 0 unconnected items.
- Fresh regeneration of the base board, four variants, and 17-board panel is byte-identical to the checked-in sources.

## 150 × 100 mm panel

- Contains four 30 mm, four 25 mm, five 18.75 mm, and four 10 mm coupons.
- Coupon envelope: 129 × 77.75 mm. Processing outline: 130.5 × 79.25 mm. Minimum raw-stock edge margin including the documented fiducial envelope: 5 mm.
- `Edge.Cuts` contains one processing outline; semantic layer `Coupon.Cuts` contains 17 closed finished-board contours. The 17 contacts use independent nets and 17 plated-design drill hits.

## Manufacturing outputs

- PCB-driven U4 audit passes for the active panel package: top copper, bottom copper, one processing outline, 17 `CutInside` contours and 17 plated-design drill hits. Panel-first discovery publishes this package instead of standalone coupons.
- PCB-driven LightBurn audit passes for the two active panel DXFs. `ezdxf` reports 0 errors and 0 fixes, and rendered front/back geometry matches the board sources.
- CircuitPro RP 1.0 target names are `TopLayer`, `BottomLayer`, `BoardOutline`, `CutInside`, and `DrillPlated`; Gerbers omit X2 object/net attributes.

The unified build validates U4, LightBurn and supplier Gerber outputs together,
including native Gerber-job layer references and expected PTH/NPTH drill counts.
