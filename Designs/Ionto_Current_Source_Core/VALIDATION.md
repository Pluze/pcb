# Validation

Current validation snapshot for the active R1218 design. The former TPS61040 implementation is retained only under `archive/legacy_tps61040/`.

## Electrical

- ERC: 0 errors, 0 warnings; the topology contract contains six nets and 26 owned endpoints.
- U1 pin mapping matches the R1218 `041A` variant: CE=1, VOUT=2, VIN=3, LX=4, GND=5, VFB=6.
- Default current is `0.2 V / 536 Ω = 373.13 µA`. The 133 Ω option is nominally 1.50 mA; the documented feedback and resistor tolerances give 1.41–1.59 mA before operating effects.

## PCB and outputs

- Active board: 30 × 22 mm, eight front-side SMT footprints, 27 front-copper track segments, one front GND zone, zero vias, and zero back-copper tracks.
- DRC: 0 errors, 0 unconnected items, and one `lib_footprint_mismatch` warning for the embedded L1 footprint. Pad geometry, nets, placement, and courtyard remain checked.
- PCB-driven U4 output contains exactly `TopLayer.gtl` and `BoardOutline.gm1`; the source has no bottom copper or drill geometry.
- PCB-driven LightBurn output contains one front-mask DXF. Manufacturing source-freshness audit passes, and `ezdxf` reports 0 errors and 0 fixes.
