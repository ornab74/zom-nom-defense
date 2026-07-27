# Zom Nom Defense — Coherent Game Overhaul

This document turns the requested expansion into one consistent game rather than a collection of unrelated features. The core fantasy is **prepare a ridiculous location, survive an escalating siege, and physically reshape how the horde reaches the survivors**.

## 1. Design pillars

1. **Readable chaos** — funny scenarios, but clear threats, routes, objectives, and feedback.
2. **Vertical defense** — stairs, balconies, roofs, ladders, windows, and destructible shortcuts are first-class paths.
3. **Reactive hordes** — zombies choose targets, push around congestion, recover from stalls, and react to defenses.
4. **Authored first, procedural second** — each map has a memorable layout; procedural dressing, loot, damage, weather, and route mutations create replay value.
5. **Beyond fixed tower defense** — the player clicks, builds, repairs, rescues, controls floors, triggers environmental traps, and adapts routes during a wave.

## 2. Full game flow

### Boot

- Studio mark fades in over distant radio static.
- A silhouette horde crosses behind the logo.
- `ZOM NOM DEFENSE` lands with the tagline `CLICK. BUILD. OUTSMART. SURVIVE.`
- Continue is instant after the first launch; no unskippable delay.

### Main menu

- Animated diorama of the last unlocked scenario.
- Primary actions: **Continue**, **Choose Scenario**, **New Run**.
- Secondary actions: Load, Tech, Survivors, Achievements, Settings, Credits.
- The current save, next unlock, and one daily challenge appear without opening another screen.

### Scenario briefing

- Location card, survivor roster, known horde traits, optional objectives, and starting scrap.
- A rotatable map preview highlights entrances and vertical connectors.
- Loadout selects three starting build recipes and one emergency ability.

### Preparation phase

- Place fences, traps, turrets, distractions, repair stations, and route-control pieces.
- Switch floors with dedicated floor-up/floor-down controls.
- Inspect route heat maps showing likely zombie traffic.
- Start early for a scrap/time bonus.

### Siege phase

- The wave director mixes enemy roles rather than only scaling health.
- New breaches can open at doors, windows, fences, drains, garages, and roof access points.
- Survivors panic, relocate, or perform assigned jobs.
- The player can click enemies, repair structures, trigger traps, and issue survivor commands.

### Recovery phase

- Collect dropped scrap and rescue resources.
- Patch breaches and move survivors.
- Choose one temporary run modifier.
- Review a short route replay showing where defenses failed.

### Results

- Grade survival, optional objectives, route efficiency, survivor injuries, and building losses.
- Unlock scenario variants, cosmetics, recipes, and horde mutations.
- Retry, continue, or return to the map.

## 3. Navigation architecture

The base enemy now preserves vertical movement, uses small path simplification, periodically replans, avoids nearby agents, and recovers when stalled. This fixes the common failure where stair switchbacks are simplified into a straight invalid segment.

### Scene requirements for reliable stairs

- Use one continuous baked `NavigationRegion3D` wherever possible.
- Stair treads may be represented by a smooth hidden navigation ramp while visible geometry remains stepped.
- Keep the ramp width at least `2 × agent radius + 0.5 m`.
- Provide at least one full agent diameter of flat landing space at turns.
- Do not disable upper-floor navigation when hiding that floor visually.
- Keep decorative railings out of navigation source geometry unless they are true blockers.
- Add `NavigationLink3D` only for discontinuous traversal such as vaults, ladders, roof drops, and window climbs.

### Route intelligence roadmap

- **Pressure routing:** score routes by distance, crowd density, hazards, and recent deaths.
- **Shared horde memory:** mark expensive choke points so later groups probe alternatives.
- **Role-aware movement:** brutes prefer barricades; climbers prefer vertical links; screamers remain behind the front line.
- **Destructible graph:** doors, fences, and walls expose new route edges when destroyed.
- **Flow-field fallback:** large hordes use regional flow directions while individual agents handle local avoidance.

## 4. Zombie roles

| Role | Navigation behavior | Gameplay purpose |
|---|---|---|
| Shambler | Reliable baseline route following | Readable core pressure |
| Runner | Uses low-congestion routes and vault links | Punishes open side paths |
| Brute | Scores destructible shortcuts highly | Breaks static choke strategies |
| Climber | Uses ladders, drainpipes, fences, and windows | Makes vertical maps matter |
| Screamer | Seeks protected line-of-sight positions | Buffs and redirects nearby hordes |
| Burrower | Appears from soft-ground breach volumes | Forces interior fallback plans |
| Hoarder | Steals dropped scrap and retreats | Creates moving priority targets |
| Mimic | Appears harmless until near survivors | Adds tension without pure stat inflation |
| Firefighter | Resistant to flame, attacks electrical traps | Counters one-dimensional builds |
| Packmind | Shares route discoveries with its group | Makes repeated waves feel adaptive |

## 5. Scenario overhaul

### Car Defense — Highway Pileup

- Expand into a blocked intersection with 8–14 vehicles, a bus, tow truck, fuel spill, median, and storefront edge.
- Cars act as cover, destructible route blockers, climb surfaces, and alarm distractions.
- Procedural variants rotate vehicle placement within authored lanes, select wreck states, scatter luggage, and choose blocked alleys.
- Mid-wave events: alarm cascade, rolling vehicle, fuel ignition, survivor trapped in a trunk.

### Campfire Survivors — Last Campsite

- Add cabins, restroom building, ranger tower, creek crossing, tents, and dense tree lanes.
- Firelight improves accuracy but attracts special infected.
- Trees can fall to create or close routes.

### Hammock Defense — Backyard Breakdown

- A suburban yard with sheds, fences, deck, trampoline, greenhouse, and neighboring lots.
- Fence gates and windows create a route-control puzzle.
- The hammock survivor can be relocated during recovery phases.

### Pool Party — Suburban Siege

- Build a complete two-story house beside the pool: garage, kitchen, living room, bedrooms, bathrooms, attic, roof, patio, and fenced yard.
- The pool is one defense zone, not the entire map.
- Stairs connect ground and upper floors; attic ladder and drainpipe are special links.
- Flooded tiles alter speed and electrical hazards.
- Windows can be boarded, broken, climbed, or used as firing positions.
- Floor controls reveal the selected level while keeping all collisions and navigation active.

### House variants

Use a modular shell with authored sockets rather than fully random rooms. Each run chooses:

- one of 3 stair positions;
- 2–4 locked or broken doors;
- furniture obstruction sets;
- window breach pattern;
- survivor starting rooms;
- loot and repair station locations;
- one major event: fire, blackout, flood, gas leak, or storm damage.

## 6. Defense families

- **Route control:** fence, gate, barricade, caltrops, foam wall, decoy sign.
- **Damage:** nail turret, scrap cannon, electric fence, flame trap, falling-object rig.
- **Support:** repair bench, ammo crate, range beacon, med station, generator.
- **Information:** motion sensor, route heatmap antenna, special-infected detector.
- **Environment:** car alarm remote, sprinkler valve, garage door, breaker panel, pool pump.

Every build icon should share a thick silhouette, warm cream foreground, dark teal backing, orange active accent, and one clear status badge. Avoid tiny illustrated scenes inside icons.

## 7. Procedural generation boundaries

Procedural generation may vary dressing and tactical state, but it must not destroy authored readability.

### Safe to generate

- prop clusters, debris, decals, foliage, parked-car variants;
- breach locations selected from authored sockets;
- loot, scrap, repair kits, and survivor jobs;
- weather, time of day, damage state, and lighting failures;
- wave composition and route pressure;
- cosmetic wall/floor material variants.

### Keep authored

- main circulation paths;
- stair dimensions and landings;
- survivor defense zones;
- camera bounds;
- buildable zones;
- major landmarks and scenario silhouette.

`ProceduralMapDresser` implements deterministic prop dressing for authored `detail_spawn_zone` markers.

## 8. Art direction

- Stylized, chunky geometry with slightly exaggerated scale.
- Materials use broad value separation, restrained roughness variation, and selective decals.
- Warm survivor/build colors contrast with cool zombie/environment shadows.
- Every map needs three material layers: base surface, damage/weather variation, story decals.
- Use trim sheets and atlas materials for houses and vehicles to reduce draw calls.
- Reserve emissive effects for interactables, danger, electricity, and navigation feedback.

## 9. Asset acquisition policy

Only import assets whose license permits redistribution in this repository. Record source URL, author, license, modifications, and imported file paths in `docs/ASSET_ATTRIBUTION.md`.

Recommended source families:

- Kenney CC0 packs for prototypes, UI, vehicles, and modular environment pieces.
- Quaternius CC0 packs for stylized characters, vehicles, nature, and modular buildings.
- Poly Haven CC0 textures and HDRIs for asphalt, concrete, wood, roofing, plaster, and sky lighting.

Do not mix raw packs directly into scenes. Normalize scale, pivots, collision, material naming, texture size, and palette first.

## 10. Delivery phases

### Phase A — Navigation foundation

- Stair-safe path following.
- Reachability checks without per-frame async calls.
- Stuck recovery, target refresh, and local avoidance.
- Multi-level floor controller.

### Phase B — Pool house vertical slice

- Complete two-story house shell.
- Ground/upper/roof floor switching.
- Continuous navmesh plus window/ladder links.
- Interior build sockets and destructible doors.

### Phase C — Coherent UI flow

- Boot sequence, animated main menu, scenario briefing, preparation HUD, floor controls, results replay.
- Unified icon set and interaction states.

### Phase D — Map remasters

- Highway pileup, campsite, backyard, and pool-house maps.
- Texture normalization, lighting passes, prop dressing, and scenario events.

### Phase E — Adaptive horde

- Role-based path scoring, route memory, destructible graph updates, and wave director mutations.

## 11. Definition of done

A multi-level scenario is ready only when:

- 50 zombies can traverse both directions on every stair without a permanent stall;
- survivors on any floor remain reachable through intended routes;
- hiding a floor does not invalidate navigation;
- the route remains readable at normal camera zoom;
- every breach has visual and audio telegraphing;
- controller and mouse users can change floors in one action;
- restart, victory, defeat, next scenario, and return-to-menu flows all work;
- all imported assets have recorded licenses and attribution.
