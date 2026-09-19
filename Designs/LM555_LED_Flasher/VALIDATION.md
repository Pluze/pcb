# Validation

Validated with KiCad 10.0.6. Commands run from the repository root:

```sh
./pcb check --design LM555_LED_Flasher
./pcb review --design LM555_LED_Flasher
./pcb verify --design LM555_LED_Flasher --no-cache
```

- ERC: 0 errors and 0 warnings.
- Native exported-netlist comparison: 8 components, 22 physical endpoints, zero
  value/footprint/connectivity differences; source hashes remain unchanged.
- All 8 references lack structured schematic MPN fields; exact procurement
  identity remains a separate evidence scope.
- Routing: 62 F.Cu segments, 123.2619 mm total, 0.25 mm width, zero vias, jumpers,
  non-45-degree segments and degree-two right-angle bends. Selectable 6 mil is unused.
- Routing-only and refilled-pour boards: 0 DRC errors, 0 unconnected items, and
  8 retained library mismatch warnings for customized footprints per board.
- Pour spacing and thermals follow the repository profile. U1 pin 1 uses explicit
  GND routing with no direct zone connection (zone_connect 0), avoiding a starved
  thermal without relaxing DRC. Pad geometry and net assignment are unchanged.
- U4, LightBurn and Gerber freshness audits pass for both variants. The board has
  front copper and mask only, with zero drill hits. Gerber includes every declared
  layer, the native job and matching drill files.
- LightBurn DXFs pass ezdxf with 0 errors/0 fixes; rounded outline and pad apertures
  match the source. Board/pour previews show readable labels, visible C1 polarity
  and accessible pads. Actual timing and assembly performance remain unmeasured.
