---
name: kicad-pcb-layout
description: Place, route, and verify KiCad PCBs with emphasis on manufacturability, hand-solderable SMT, single-sided prototypes, mechanical constraints, and DRC-backed visual QA.
---

# KiCad PCB Layout

Use this skill after schematic connectivity and footprints are sufficiently stable.

## Placement

- Synchronize from the verified schematic and confirm footprint/net counts.
- Verify package, pad numbering, polarity, courtyard, and assembly method.
- Establish outline, holes, keepouts, layers, clearances, trace/via rules, and voltage constraints.
- Place fixed mechanical items first. Then place by functional block, keeping decoupling, protection, feedback, and switching loops electrically close.
- Preserve deliberate connector orientation, signal flow, symmetry, and return paths.
- Treat routing feasibility as placement feedback. If a legal escape corridor does not exist, move or rotate the blocking part and replan the local topology instead of repeatedly retrying impossible trace geometry.

## Hand-soldered single-sided priority

When requested, prefer common SMT packages with hand-solder pads, accessible component spacing, and readable polarity. Begin with a zero-via budget. Route on the chosen copper side with wide practical traces; use a documented zero-ohm jumper when a crossover is unavoidable rather than silently adding vias or a second copper layer.

### Soldermask-free milled prototypes

For an in-house milled board that will be hand-soldered without solder mask, treat copper-pour spacing as an assembly constraint, not merely as the minimum electrical clearance. Establish final values from the actual isolation tool, runout, registration, copper condition, and a process coupon. When those measurements are not yet available, use the following conservative starting recommendation:

- 0.50 mm zone clearance to copper on other nets;
- 0.50 mm thermal-relief gap and 0.50 mm thermal spoke width;
- 0.50 mm minimum zone feature thickness; and
- local zone keepouts or cutouts around dense pads when solder access or isolation remains doubtful.

These are recommended prototype defaults, not universal fabrication limits. Increase them for voltage, contamination, poor tool control, or difficult hand soldering; reduce them only with measured process evidence and an electrical/thermal review. Remember that zone clearance separates different nets only: same-net pads and tracks intentionally merge into the pour, while thermal settings govern the moat and spokes around thermally connected pads.

After every change, refill the zones and inspect the actual filled geometry at realistic scale. Reject narrow slivers, isolated islands, starved thermals, copper left between closely spaced pads, and milling channels that the selected cutter cannot enter. Run DRC after refill, but do not treat a clean DRC as proof that the milled isolation or hand-solder result is reliable.

## Routing and verification

- Route critical, switching, sensitive analog, clock, differential, and power nets in an electrically appropriate order.
- Keep high-current and fast loops compact and returns continuous. Apply creepage/clearance appropriate to actual voltages.
- On a one-layer SMT layout, reserve short width transitions only for pad escape, then widen immediately. Refill ground zones after each local placement/routing change and verify that narrow channels do not create isolated islands, starved thermals, or apparently connected but electrically separate ground regions.
- Before full rerouting, close the editor, remove old routing, prove zero stale segments/vias/zones as applicable, and generate fresh router input.
- After routing, count layers, vias, jumpers, and unrouted items. Refill zones and run DRC.
- Inspect 2D, 3D, silkscreen, solder mask, copper-to-edge clearance, connector accessibility, and realistic assembly scale.

Record measured results and waivers in the design's `VALIDATION.md`; keep reusable policy here.

## Parametric circular contact boards

For a square two-layer connector coupon with one exposed circular contact on each side and a central through interconnect, use `scripts/generate_circular_contact_board.py`. The required parameters are front contact diameter, back contact diameter, and square board side, all in millimetres. The helper emits deterministic KiCad PCB files, keeps paste off the contact surfaces, names both pads and the via `CONTACT`, validates copper-to-edge margin and via geometry, supports repeatable `--spec` and CSV batches, and refuses accidental overwrite unless `--force` is explicit. Use `--drc` when creating a new deliverable so every candidate must pass KiCad DRC in temporary staging before any final file is written.

Keep the three geometric inputs as the primary interface. Treat via geometry and minimum copper-to-edge clearance as advanced manufacturing parameters, validate every generated family member, and do not assume that one DRC result covers the batch.

For a repeated-size manufacturing panel of these coupons, use `scripts/generate_circular_contact_panel.py`. It reads the same family CSV, creates an independent net for every coupon, places one continuous processing boundary on `Edge.Cuts`, and keeps each finished coupon contour on `User.1` (`Coupon.Cuts`) for a separate Gerber and final depaneling operation. This separation prevents CAM software from treating disjoint coupon contours as competing board outlines and rejecting valid copper as outside the board. For CircuitPro RP 1.x/U4 delivery, export `Edge.Cuts` as `BoardOutline.gm1` mapped to `BoardOutline`, and export `User.1` as `CutInside.gm2` mapped to `CutInside`; never map the repeated coupon contours to `BoardOutline`. The helper keeps a configurable gap between finished outlines and checks that the coupon envelope, processing rail, automatic-fiducial distance and diameter, and stock-edge margin all fit the raw stock. Use repeated `--row SIDE:COUNT,...` arguments when mixed-size rows improve material use while preserving a reviewable layout and minimum count per variant. Its raw-stock rectangle and expected fiducial circles are documentation geometry on `Dwgs.User`, not manufacturing cuts or pre-created fiducials.

When an in-house milling process does not plate holes, a KiCad via or through-hole pad proves only the intended copper geometry and logical net. Document the physical interconnect operation, provide a hole and annulus that the chosen drill and hand-solder process can access, and require continuity testing after solder is wicked through the hole. Do not report DRC success as proof of the manual metallurgical connection.
