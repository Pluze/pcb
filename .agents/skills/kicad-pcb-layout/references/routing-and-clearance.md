# Routing width and copper clearance

Reviewed 2026-09-19. Values in `repository-defaults.json` are engineering starting
points for the selected U4 hand-assembly profile, not fabrication qualification.

| Setting | Repository recommendation | Interpretation |
| --- | --- | --- |
| Selectable trace range | 0.1524–0.508 mm, about 6–20 mil | Includes familiar metric 0.25, 0.30, 0.40 and 0.50 mm choices |
| Ordinary trace | 0.25 mm / 9.84 mil | Normal routing choice; existing valid wider tracks need not be changed |
| Controlled low-current path | 0.30 mm / 11.81 mil | Recheck noise, leakage, feedback geometry and actual current |
| Power/switching starting target | 0.50 mm / 19.69 mil | Size from RMS/peak current, copper weight, length and temperature; may exceed 20 mil |
| Minimum track | 0.1524 mm / 6 mil | Only use after confirming copper/process capability; not used by current Ionto or LM555 routes |
| Other-net routing clearance | 0.20 mm / 7.87 mil | Low-voltage starting value; voltage, contamination and process can require more |
| U4 hand-assembly pour clearance | 0.50 mm / 19.69 mil | Assembly moat, distinct from ordinary routing clearance |
| Pour edge inset | 0.50 mm | Must also meet actual board-edge fabrication clearance |
| Thermal gap / spoke | 0.50 / 0.50 mm | Review small-pad connectivity and solderability after refill |
| Minimum pour feature | 0.25 mm | Inspect slivers/islands; geometry is not evidence of physical yield |

Six mil is a selectable fine-routing option, not the default. Do not reduce every
track or clearance to the fabrication minimum. In particular, 20 mil is not a
maximum allowed power width and a ground plane is not a substitute for a verified
return path. Netclass widths guide the router; actual saved geometry must be
inspected separately. Project DRC rules are not interchangeable with dropdown sizes.

## Source comparison

- [PCBWay manufacturing tolerances](https://www.pcbway.com/pcb_prototype/PCB_Manufacturing_tolerances.html)
  lists 4 mil manufacturing minima and recommends above roughly 6 mil for economy.
- [JLCPCB copper-weight guidance](https://jlcpcb.com/help/article/jlcpcb-copper-weight)
  shows copper-dependent limits; its 2 oz guidance is around 0.16 mm / 6.5 mil.
  Therefore a 6 mil setting is not a universal rule for heavier copper.
- [LPKF U4 brochure](https://www.lpkf.com/fileadmin/mediafiles/user_upload/products/pdf/DQ/brochure_lpkf_protolaser_u4_en.pdf)
  specifies 50/20 µm line/space on FR4 with 18 µm copper. This is a specified
  substrate/process capability, not a guarantee for uncharacterized stock or hand
  soldering. The 0.50 mm assembly moat is our recommendation, not LPKF's minimum.

The selected 0.50 mm pour moat replaces the previous 1.00 mm recommendation to
reduce excessive clearance while retaining assembly room. Its actual laser-time
benefit must be checked in CircuitPro; no machining time or physical yield was
measured here. U4 laser structuring and mechanical milling have different tool
limits; do not transfer cutter-runout assumptions to a laser recipe.

For conventional masked outsourced boards, a smaller pour clearance may be suitable
when it satisfies the chosen manufacturer's rules and the electrical requirements.
Do not change the repository's active U4 assembly profile merely to match a board
house minimum. Refill, DRC, inspect copper at pad scale, and regenerate the affected
manufacturing packages after changing these values.
