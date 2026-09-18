# Validation

Current validation snapshot for the active R1218 design. The former TPS61040 implementation is retained only under `archive/legacy_tps61040/`.

## Electrical

- ERC: 0 errors, 0 warnings; the topology contract contains six nets and 26 owned endpoints.
- U1 pin mapping matches the R1218 `041A` variant: CE=1, VOUT=2, VIN=3, LX=4, GND=5, VFB=6.
- Default current is `0.2 V / 536 Ω = 373.13 µA`. The 133 Ω option is nominally 1.50 mA; the documented feedback and resistor tolerances give 1.41–1.59 mA before operating effects.

## PCB and outputs

- Active routing source: 27 × 20 mm, eight front-side SMT footprints, 39 front-copper track segments, zero zones, zero vias, and zero back-copper tracks. Board area is 18.2% smaller than the previous 30 × 22 mm revision.
- Default and CE-control routing is 0.25 mm (about 10 mil). BAT+, switching-node, and stimulation net classes remain wider at 0.8 mm, 1.0 mm, and 0.6 mm respectively, with only local pad escapes reduced where required.
- The routing-only primary and generated with-pour production variant each report 0 DRC errors and 0 unconnected items. The only retained warning is `lib_footprint_mismatch` for the embedded L1 footprint; pad geometry, nets, placement, and courtyard remain checked.
- The generated front GND pour uses 1.00 mm clearance to other nets and a 1.00 mm edge inset. The 1.50 mm trial was rejected as unnecessarily wide for the U4 time objective. Explicit routed GND returns keep the routing-only primary electrically complete without copper-zone connectivity.
- Validation order is route-first: the generated no-pour board passed DRC before the with-pour board was refilled and checked. A zone is not accepted as the only connection for any net.
- Repo-wide manufacturing policy is stored in `.agents/skills/kicad-pcb-layout/references/repository-defaults.json`. Production generation exports the routing-only primary package and automatically derives the one-zone `With_Pour` package unless a design explicitly opts out.
- Each PCB-driven U4 package contains exactly `TopLayer.gtl` and `BoardOutline.gm1`; neither variant has bottom copper or drill geometry.
- Each PCB-driven LightBurn package contains one front-mask DXF. Manufacturing source-freshness audit passes, and `ezdxf` reports 0 errors and 0 fixes.
