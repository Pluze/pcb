---
name: pcb-component-engineering
description: Select and verify electronic components for PCB designs, including exact MPNs, distributor availability, symbol-pin and footprint-pad mapping, ratings, alternates, and procurement evidence.
---

# PCB Component Engineering

Use this skill when a PCB task requires component choice, replacement, symbol/footprint assignment, or current availability evidence.

## Evidence and identity

Give every consequential part a procurement identity: manufacturer, exact MPN, package, assigned KiCad symbol and footprint, and distributor identifiers when available. Treat distributor stock as a dated observation, not a permanent property.

Distinguish:

1. tool-reported internal consistency;
2. direct KiCad source and connectivity inspection;
3. manufacturer-datasheet confirmation;
4. dated distributor lifecycle and stock evidence.

Never call a pin mapping verified merely because the schematic and PCB agree with each other.

## Selection workflow

- Derive electrical limits from the design contract before searching parts: voltage, current, power, tolerance, temperature, bandwidth, leakage, quiescent current, and fault stress.
- Search the repository before the distributor catalog. Inspect existing BOM files, design READMEs, validation records, and exact-MPN occurrences for parts already qualified for the same function. Build the candidate list from those known parts first.
- Prefer an existing exact MPN and its proven footprint when it satisfies the present electrical, mechanical, assembly, lifecycle, and sourcing constraints. Also consolidate identical passive values and connector families where doing so does not reduce required margin or usability.
- Treat repository reuse as a reduction in search and qualification work, not as inherited proof. Recheck the current datasheet revision, exact suffix, ratings, symbol-to-pin mapping, footprint-to-pad mapping, lifecycle, and dated distributor stock in the context of the new design.
- Add a new MPN only when no existing part meets a material requirement, the previous part is unavailable or lifecycle-risky, a different package materially improves assembly or manufacturability, or the new choice reduces a documented engineering risk. Record the reason instead of silently proliferating near-duplicate parts.
- Prefer widely stocked US-distributor parts and common hand-solderable packages when requested. Record acceptable alternates without silently changing pinout or footprint.
- For low-pin-count external connections, default to reusable 2.54 mm pin headers, preferably a previously verified hand-solderable SMT header when the assembly goal is front-side SMT. Adapt to JST, clips, terminal blocks, or a harness with flying leads or a small adapter instead of proliferating board connector families. Override this default only when a documented requirement needs polarization, retention, touch protection, shielding, controlled impedance, hot-plug sequencing, or greater voltage/current capacity; exposed headers are not an acceptable shortcut when safety or misuse prevention depends on the connector.
- Verify the exact package suffix. Cross-check every active device, connector, diode, polarized part, and variant-prone package against the manufacturer pin table and recommended land pattern.
- Confirm symbol pin numbers, footprint pad numbers, orientation, exposed pads, no-connect pins, and connector mating direction.
- Recalculate regulator dividers, current-set resistors, filters, protection limits, and component derating from the placed values.

## Deliverable

For each consequential selection, identify whether the exact MPN is reused from the repository or newly introduced. For a new MPN, state why existing candidates were unsuitable. Report the resulting unique-MPN count when preparing or reviewing a complete BOM so inventory complexity is visible.

Put reusable sourcing method here; put only the selected BOM, calculations, dated stock results, reuse/new-part decisions, alternates, and unresolved risks in the design directory.
