from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SAFE_ID = re.compile(r"^[a-z0-9_]{1,96}$")


@dataclass(frozen=True)
class AssetJob:
    asset_id: str
    display_name: str
    category: str
    family: str
    backend: str
    scenario_tags: tuple[str, ...]
    godot_destination: str
    prompt: str
    variants: int = 1
    target_vertices: int = 4000
    target_triangles: int = 8000
    texture_resolution: int = 2048
    lod_ratios: tuple[float, ...] = (1.0, 0.5, 0.22, 0.08)
    collision: str = "convex"
    rig: str = "none"
    animations: tuple[str, ...] = ()
    validation_profile: str = "static_prop_v2"


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not SAFE_ID.fullmatch(result):
        raise ValueError(f"unsafe id: {value!r}")
    return result


def add_family(
    jobs: list[AssetJob],
    *,
    category: str,
    family: str,
    backend: str,
    names: Iterable[str],
    scenario_tags: tuple[str, ...],
    prompt_prefix: str,
    variants: int = 1,
    vertices: int = 4000,
    triangles: int = 8000,
    collision: str = "convex",
    rig: str = "none",
    animations: tuple[str, ...] = (),
    validation: str = "static_prop_v2",
) -> None:
    for name in names:
        asset_id = slug(name)
        jobs.append(
            AssetJob(
                asset_id=asset_id,
                display_name=name.replace("_", " ").title(),
                category=category,
                family=family,
                backend=backend,
                scenario_tags=scenario_tags,
                godot_destination=f"Assets/Generated/{category}/{asset_id}",
                prompt=(
                    f"{prompt_prefix}. Produce {name.replace('_', ' ')} for Zom Nom Defense; "
                    "grounded stylized realism, readable three-quarter tactical silhouette, "
                    "meter scale, clean origin and pivots, original design, no logos, no text, "
                    "game-ready UVs, coherent PBR materials, deterministic naming, Godot 4 GLB."
                ),
                variants=variants,
                target_vertices=vertices,
                target_triangles=triangles,
                collision=collision,
                rig=rig,
                animations=animations,
                validation_profile=validation,
            )
        )


def build_catalog() -> list[AssetJob]:
    jobs: list[AssetJob] = []

    add_family(jobs, category="architecture", family="pool_house_exterior", backend="modular_architecture_v2",
        names=("pool_house_shell_a", "pool_house_shell_b", "pool_house_roof_main", "pool_house_roof_damage_a", "pool_house_balcony", "pool_house_sliding_door", "pool_house_front_door", "pool_house_window_small", "pool_house_window_large", "pool_house_garage_door", "pool_house_gutter_set", "pool_house_downspout_set", "pool_house_chimney", "pool_house_foundation", "pool_house_exterior_trim"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Modular two-story southeastern suburban pool house exterior kit", vertices=16000, triangles=30000, collision="trimesh_static", validation="modular_architecture_v2")
    add_family(jobs, category="architecture", family="pool_house_interior", backend="modular_architecture_v2",
        names=("interior_wall_plain", "interior_wall_door", "interior_wall_window", "interior_floor_tile", "interior_floor_wood", "interior_ceiling", "stair_straight", "stair_landing", "stair_railing", "doorframe_interior", "door_interior", "kitchen_counter", "kitchen_island", "bathroom_fixture_set", "bedroom_closet", "garage_workbench", "attic_hatch", "interior_trim_set"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Metric modular suburban house interior construction kit", vertices=12000, triangles=24000, collision="trimesh_static", validation="navigation_architecture_v2")
    add_family(jobs, category="environment", family="pool_yard", backend="environment_structure_v2",
        names=("pool_basin", "pool_water_surface", "pool_coping_straight", "pool_coping_corner", "pool_steps", "pool_ladder", "pool_filter_pump", "pool_deck_tile_clean", "pool_deck_tile_cracked", "pool_deck_drain", "privacy_fence_straight", "privacy_fence_corner", "privacy_fence_gate", "garden_shed", "patio_pergola", "retaining_wall", "yard_drain", "hose_spigot"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Backyard pool, deck and yard structural asset", vertices=9000, triangles=18000, collision="trimesh_static", validation="environment_structure_v2")
    add_family(jobs, category="architecture", family="highway_structures", backend="modular_architecture_v2",
        names=("highway_lane_segment", "highway_curve_segment", "highway_shoulders", "highway_guardrail", "highway_median_barrier", "highway_overpass", "highway_culvert", "highway_drainage_ditch", "gas_station_shell", "gas_station_canopy", "gas_pump_original", "motel_shell", "motel_balcony", "roadside_diner_shell", "parking_lot_module", "service_road_module", "billboard_blank", "utility_pole"),
        scenario_tags=("highway_last_stand",), prompt_prefix="Abandoned southeastern highway and roadside modular structure", vertices=18000, triangles=34000, collision="trimesh_static", validation="modular_architecture_v2")

    add_family(jobs, category="foliage", family="trees", backend="tree_polyflow_v3",
        names=("live_oak_young", "live_oak_mature", "live_oak_old", "loblolly_pine_young", "loblolly_pine_mature", "red_maple_young", "red_maple_mature", "crepe_myrtle", "dogwood_tree", "dead_tree_snag", "storm_fallen_tree", "trimmed_suburban_tree"),
        scenario_tags=("shared",), prompt_prefix="Southeastern United States tree with physically scaled multi-profile leaves and wind hierarchy", variants=3, vertices=12000, triangles=24000, collision="capsule", rig="wind_hierarchy", animations=("wind_idle", "wind_storm"), validation="tree_polyflow_v3")
    add_family(jobs, category="foliage", family="ground_foliage", backend="foliage_cluster_v2",
        names=("lawn_grass_clean", "lawn_grass_overgrown", "ditch_grass", "crabgrass_patch", "clover_patch", "weed_cluster_small", "weed_cluster_large", "azalea_shrub", "boxwood_hedge", "privet_hedge", "ornamental_grass", "fern_cluster", "ivy_wall_patch", "fallen_leaf_cluster", "pine_needle_cluster"),
        scenario_tags=("shared",), prompt_prefix="Optimized foliage card and mesh cluster", variants=4, vertices=1800, triangles=2800, collision="none", rig="wind_simple", animations=("wind_idle",), validation="foliage_cluster_v2")

    add_family(jobs, category="character", family="survivors", backend="character_surface_v2",
        names=("survivor_mechanic_female", "survivor_paramedic_male", "survivor_neighbor_male", "survivor_college_student_female", "survivor_retired_veteran", "survivor_delivery_rider", "survivor_construction_worker", "survivor_nurse", "survivor_firefighter", "survivor_runner"),
        scenario_tags=("shared",), prompt_prefix="Original survivor character in neutral A-pose with separate clothing layers and deformation-ready hands", variants=3, vertices=26000, triangles=50000, collision="capsule", rig="humanoid", animations=("idle", "walk", "run", "aim", "repair", "build", "hurt", "downed"), validation="character_surface_v2")
    add_family(jobs, category="character", family="zombie_common", backend="character_surface_v2",
        names=("zombie_shambler_male_01", "zombie_shambler_female_01", "zombie_runner_male_01", "zombie_runner_female_01", "zombie_neighbor", "zombie_office_worker", "zombie_landscaper", "zombie_delivery_driver", "zombie_pool_guest", "zombie_construction_worker"),
        scenario_tags=("shared",), prompt_prefix="Non-graphic stylized-realistic common zombie with clean deformation topology", variants=4, vertices=22000, triangles=42000, collision="capsule", rig="humanoid", animations=("idle", "shuffle", "run", "attack", "hit", "death"), validation="character_surface_v2")
    add_family(jobs, category="character", family="zombie_vertical", backend="character_surface_v2",
        names=("climber_zombie_male_01", "climber_zombie_female_01", "roofer_zombie", "swimmer_zombie", "crawler_zombie", "fence_vault_zombie", "window_breaker_zombie", "gutter_climber_zombie"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Vertical-navigation zombie with long-reach readable anatomy and topology for climbing, swimming or crawling", variants=4, vertices=24000, triangles=46000, collision="capsule", rig="humanoid_extended", animations=("idle", "run", "climb", "vault", "crawl", "swim", "attack", "fall"), validation="character_navigation_v2")
    add_family(jobs, category="character", family="zombie_heavy_special", backend="character_surface_v2",
        names=("brute_zombie", "armored_riot_zombie", "firefighter_zombie", "construction_brute", "screecher_zombie", "spitter_zombie", "electrician_zombie", "gas_station_boss", "pool_house_boss", "highway_boss"),
        scenario_tags=("shared",), prompt_prefix="Distinct special zombie gameplay archetype with readable weak points and original silhouette", variants=3, vertices=32000, triangles=62000, collision="capsule", rig="humanoid_extended", animations=("idle", "locomotion", "special_attack", "hit", "stagger", "death"), validation="character_boss_v2")

    add_family(jobs, category="vehicle", family="survivor_vehicle", backend="vehicle_chassis_v2",
        names=("survivor_muscle_car_base", "survivor_muscle_car_armored", "survivor_muscle_car_turret", "survivor_muscle_car_electric", "survivor_muscle_car_damage_light", "survivor_muscle_car_damage_heavy"),
        scenario_tags=("highway_last_stand",), prompt_prefix="Original late-1970s-inspired survivor muscle car with separate wheels, doors, hood, trunk and upgrade sockets", variants=2, vertices=42000, triangles=80000, collision="convex_decomposition", rig="vehicle", animations=("wheel_spin", "suspension", "doors", "hood", "damage"), validation="vehicle_chassis_v2")
    add_family(jobs, category="vehicle", family="world_vehicles", backend="vehicle_chassis_v2",
        names=("sedan_clean", "sedan_wreck_a", "sedan_wreck_b", "pickup_clean", "pickup_wreck", "suv_wreck", "delivery_van", "ambulance_wreck", "school_bus_wreck", "tow_truck", "box_truck", "motorcycle_small", "utility_cart", "landscape_trailer", "boat_trailer"),
        scenario_tags=("shared",), prompt_prefix="Original unbranded southeastern road vehicle or wreck with believable chassis and damage layers", variants=3, vertices=26000, triangles=50000, collision="convex_decomposition", rig="vehicle_optional", animations=("wheel_spin",), validation="vehicle_chassis_v2")

    add_family(jobs, category="defense", family="defenses", backend="defense_device_v2",
        names=("wood_barricade_tier1", "wood_barricade_tier2", "scrap_fence_tier1", "scrap_fence_tier2", "electric_fence", "spike_fence", "scrap_turret", "heavy_turret", "water_sprinkler_trap", "noise_decoy", "repair_station", "ammo_station", "medical_station", "zombie_scanner", "floodlight_tower", "car_bumper_barricade", "pool_gate_reinforcement", "roof_ladder_blocker"),
        scenario_tags=("shared",), prompt_prefix="Coherent scrap-built survivor defense device with sockets, damage states and clear gameplay function", variants=3, vertices=10000, triangles=19000, collision="convex", rig="mechanical", animations=("deploy", "idle", "activate", "damage", "destroy"), validation="defense_device_v2")

    add_family(jobs, category="props", family="backyard_props", backend="prop_family_v2",
        names=("gas_grill", "charcoal_grill", "patio_table", "patio_chair", "patio_umbrella", "pool_float_ring", "pool_float_mattress", "cooler_large", "cooler_small", "hose_reel", "garden_hose", "planter_round", "planter_box", "lawn_mower", "leaf_blower", "wheelbarrow", "trash_bin", "recycling_bin", "outdoor_storage_box", "pool_skimmer", "pool_chemical_bucket", "towel_stack"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Weathered unbranded backyard prop", variants=2, vertices=5000, triangles=9000, collision="convex", validation="prop_family_v2")
    add_family(jobs, category="props", family="interior_props", backend="prop_family_v2",
        names=("sofa_sectional", "armchair", "coffee_table", "television", "bookshelf", "floor_lamp", "kitchen_fridge", "kitchen_stove", "kitchen_sink", "microwave", "dining_table", "dining_chair", "bed_frame", "mattress", "dresser", "nightstand", "toilet", "bathroom_sink", "shower_unit", "washer", "dryer", "tool_chest", "garage_shelf", "cardboard_box_set", "food_can_set", "water_bottle_case"),
        scenario_tags=("pool_house_siege",), prompt_prefix="Suburban interior prop with damage-ready separable components", variants=2, vertices=6500, triangles=12000, collision="convex", validation="prop_family_v2")
    add_family(jobs, category="props", family="road_props", backend="prop_family_v2",
        names=("traffic_cone", "road_barrier", "blank_road_sign", "guardrail_end", "tire_single", "tire_stack", "pallet_wood", "pallet_plastic", "oil_drum", "plastic_barrel", "sandbag_stack", "scrap_pile_small", "scrap_pile_large", "camp_tent", "camp_chair", "shopping_cart", "gas_can", "toolbox", "portable_generator", "road_flare_unlit", "roadkill_marker", "broken_luggage"),
        scenario_tags=("highway_last_stand",), prompt_prefix="Roadside survival and apocalypse prop", variants=3, vertices=4500, triangles=8500, collision="convex", validation="prop_family_v2")

    add_family(jobs, category="ui", family="interface", backend="ui_asset_v2",
        names=("title_logo_original", "boot_background", "main_menu_background", "pool_house_scenario_card", "highway_scenario_card", "survivor_portrait_set", "zombie_portrait_set", "build_wheel_icons", "resource_icons", "defense_icons", "vehicle_upgrade_icons", "objective_icons", "status_effect_icons", "minimap_symbols", "crosshair_set", "damage_direction_set", "loading_screen_set", "achievement_icon_set"),
        scenario_tags=("shared",), prompt_prefix="Original Zom Nom Defense interface art with clean alpha and readable compact shapes", variants=4, vertices=1, triangles=1, collision="none", validation="ui_asset_v2")
    add_family(jobs, category="vfx", family="effects", backend="vfx_graph_v2",
        names=("muzzle_flash_set", "bullet_impact_set", "electric_arc_set", "water_splash_set", "pool_ripple_set", "fire_small", "fire_large", "smoke_set", "dust_impact_set", "debris_burst_set", "repair_spark_set", "healing_effect", "scanner_pulse", "zombie_spit_effect", "screecher_wave", "bloodless_hit_effect", "weather_rain", "weather_fog", "weather_lightning"),
        scenario_tags=("shared",), prompt_prefix="Godot-ready VFX texture or mesh effect with clean flipbook and alpha", variants=4, vertices=1000, triangles=1800, collision="none", validation="vfx_graph_v2")

    ids = [job.asset_id for job in jobs]
    if len(ids) != len(set(ids)):
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        raise ValueError(f"duplicate asset ids: {duplicates}")
    if len(jobs) < 200:
        raise AssertionError(f"catalog unexpectedly small: {len(jobs)}")
    return jobs


def write_catalog(path: Path) -> None:
    jobs = build_catalog()
    payload = {
        "version": 2,
        "project": "zom-nom-defense",
        "manual_colab_workflow": True,
        "asset_count": len(jobs),
        "assets": [asdict(job) for job in jobs],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    destination = Path("AssetFoundry/generated/asset_catalog.json")
    write_catalog(destination)
    print(f"Wrote {destination} with {len(build_catalog())} asset jobs")
