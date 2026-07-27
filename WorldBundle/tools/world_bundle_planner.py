#!/usr/bin/env python3
"""Generate a secure staged asset/world bundle for Zom Nom Defense.

This planner converts the game preset and 36-stage notebook matrix into bounded,
deterministic asset jobs. It never executes model-written code. The resulting
JSONL queue is consumed by specialized Colab notebooks and the Godot stitcher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

SAFE_ID = re.compile(r"^[a-z0-9_]{1,80}$")
PRIORITIES = {"hero", "high", "standard", "minor"}


@dataclass(frozen=True)
class Policy:
    max_assets: int = 2000
    max_variants: int = 16
    max_dependencies: int = 32
    max_prompt_chars: int = 16000
    execute_model_code: bool = False
    allow_remote_urls: bool = False
    allow_third_party_asset_extraction: bool = False


@dataclass(frozen=True)
class AssetJob:
    job_id: str
    asset_id: str
    display_name: str
    stage_id: str
    category: str
    backend: str
    prompt: str
    variants: int
    priority: str
    dependencies: list[str]
    godot_destination: str
    validation_profile: str
    scenario_tags: list[str]


def slug(value: str, limit: int = 80) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return (value[:limit] or "asset")


def stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:14]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_inputs(preset: dict[str, Any], matrix: dict[str, Any], policy: Policy) -> None:
    if not SAFE_ID.fullmatch(str(preset.get("preset_id", ""))):
        raise ValueError("Unsafe preset_id")
    prompt = str(preset.get("world_prompt", ""))
    if not prompt or len(prompt) > policy.max_prompt_chars:
        raise ValueError("Invalid world_prompt")
    stages = matrix.get("stages", [])
    if len(stages) != 36:
        raise ValueError(f"Expected 36 stages; found {len(stages)}")
    seen: set[str] = set()
    for stage in stages:
        stage_id = stage.get("id", "")
        if not SAFE_ID.fullmatch(stage_id) or stage_id in seen:
            raise ValueError(f"Invalid or duplicate stage id: {stage_id}")
        seen.add(stage_id)


def catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(stage: str, category: str, backend: str, names: Iterable[str],
            variants: int = 1, priority: str = "standard",
            scenarios: tuple[str, ...] = ("shared",), dependencies: tuple[str, ...] = ()) -> None:
        for name in names:
            rows.append({
                "stage_id": stage,
                "category": category,
                "backend": backend,
                "display_name": name,
                "variants": variants,
                "priority": priority,
                "scenario_tags": list(scenarios),
                "dependencies": list(dependencies),
            })

    add("05_skies_weather", "environment", "sky_environment", [
        "clear humid afternoon sky", "golden-hour suburban sky", "approaching thunderstorm sky",
        "rainy overcast sky", "moonlit cloudy night sky", "foggy dawn sky",
    ], 2, "high")

    add("06_pool_house_terrain", "terrain", "terrain_heightfield", [
        "pool-house yard terrain", "sloped front lawn terrain", "side-yard drainage terrain",
        "pool deck foundation terrain", "garden soil patches", "muddy siege-state yard",
    ], 3, "high", ("pool_house_siege",))
    add("07_highway_terrain", "terrain", "terrain_heightfield", [
        "cracked highway terrain", "left shoulder and ditch", "right shoulder and culvert",
        "gas station lot terrain", "motel parking edge", "wreck-field roadbed",
    ], 3, "high", ("highway_last_stand",))

    add("08_trees_foliage", "foliage", "tree_polyflow", [
        "mature live oak family", "loblolly pine family", "wind-shaped maple family",
        "crepe myrtle family", "privacy hedge family", "roadside weed family",
        "dry lawn grass family", "wet ditch grass family", "garden plant family",
    ], 6, "standard")

    add("09_rocks_debris", "environment", "implicit_surface", [
        "concrete rubble family", "broken asphalt chunks", "landscape rock family",
        "storm debris family", "soil clod family", "pool coping debris family",
    ], 6, "minor")

    add("10_pool_house_exterior", "architecture", "modular_architecture", [
        "two-story pool house shell", "warm stucco wall kit", "roof and gutter kit",
        "window and shutter kit", "front porch kit", "attached garage exterior",
        "balcony exterior kit", "pool pump shed exterior", "safe-room exterior",
    ], 4, "hero", ("pool_house_siege",), ("04_material_bible",))
    add("11_pool_house_interior", "architecture", "modular_architecture", [
        "ground-floor interior shell", "second-floor interior shell", "residential staircase with landing",
        "living room kit", "kitchen kit", "bedroom kit", "bathroom kit",
        "garage interior kit", "utility room kit", "safe-room interior kit",
    ], 4, "hero", ("pool_house_siege",), ("03_gameplay_metrics", "04_material_bible"))
    add("12_pool_deck_structures", "architecture", "modular_architecture", [
        "in-ground pool basin", "pool coping kit", "ceramic pool tile kit", "concrete pool deck kit",
        "privacy fence kit", "side gate kit", "balcony railing kit", "roof access kit",
        "pool equipment enclosure", "raised garden kit",
    ], 4, "high", ("pool_house_siege",))
    add("13_highway_structures", "architecture", "modular_architecture", [
        "highway lane kit", "guardrail kit", "concrete culvert kit", "storm drain kit",
        "gas station shell", "motel edge kit", "overpass segment", "corrugated carport",
        "roadside barrier kit", "blank sign kit",
    ], 4, "high", ("highway_last_stand",))

    add("14_backyard_props", "prop", "prop_family", [
        "propane grill family", "patio furniture family", "pool float family", "cooler family",
        "pool maintenance tool family", "garden tool family", "hose and sprinkler family",
        "planter family", "children backyard toy family", "outdoor lighting family",
    ], 8, "standard", ("pool_house_siege",))
    add("15_interior_props", "prop", "prop_family", [
        "living room furniture family", "kitchen appliance family", "kitchen clutter family",
        "bedroom furniture family", "bathroom fixture family", "garage storage family",
        "toolbox family", "medical supply family", "food and water supply family",
        "survivor personal belongings family", "electrical supply family",
    ], 8, "standard", ("pool_house_siege",))
    add("16_road_props", "prop", "prop_family", [
        "traffic cone and barrier family", "road sign family", "vehicle debris family",
        "camping supply family", "sorted scrap family", "trash and recycling family",
        "gas station prop family", "motel prop family", "roadside utility family",
    ], 8, "standard", ("highway_last_stand",))

    add("17_survivors", "character", "character_pipeline", [
        "survivor builder", "survivor mechanic", "survivor medic", "survivor scout",
        "survivor heavy defender", "survivor homeowner", "survivor driver",
    ], 4, "hero")
    add("18_zombie_common", "character", "character_pipeline", [
        "male workwear grunt zombie", "female casual grunt zombie", "elder shambler zombie",
        "athletic runner zombie", "delivery worker zombie", "office worker zombie",
    ], 5, "high")
    add("19_zombie_vertical", "character", "character_pipeline", [
        "climber zombie", "roofer zombie", "pool swimmer zombie", "crawler zombie",
        "balcony leaper zombie", "drainage lurker zombie",
    ], 5, "hero")
    add("20_zombie_heavy", "character", "character_pipeline", [
        "workwear brute zombie", "firefighter zombie", "armored construction zombie",
        "road-worker brute zombie", "swollen tank zombie",
    ], 5, "hero")
    add("21_zombie_special_boss", "character", "character_pipeline", [
        "screecher zombie", "spitter zombie", "paramedic specialist zombie",
        "mechanic specialist zombie", "backyard host boss zombie",
        "highway pileup boss zombie", "storm-drain boss zombie",
    ], 5, "hero")

    add("22_survivor_car", "vehicle", "vehicle_chassis", [
        "survivor muscle car base", "survivor muscle car reinforced", "survivor muscle car battle upgrade",
        "survivor muscle car critical damage", "survivor muscle car interior",
    ], 3, "hero", ("highway_last_stand",))
    add("23_wrecked_vehicles", "vehicle", "vehicle_chassis", [
        "front-damaged compact sedan", "rear-damaged midsize sedan", "abandoned work pickup",
        "family SUV wreck", "delivery van wreck", "patrol sedan wreck", "school bus barricade",
        "tow truck wreck", "burned hatchback", "rolled crossover",
    ], 3, "high", ("highway_last_stand",))
    add("24_small_vehicles", "vehicle", "vehicle_chassis", [
        "125cc street motorcycle with cargo rack", "pool utility cart", "small utility trailer",
        "portable generator trailer", "lawn tractor", "wheelbarrow vehicle prop",
    ], 3, "standard")

    add("25_defense_family", "defense", "defense_compiler", [
        "lumber sheet-metal barricade", "reinforced sandbag barricade", "electrified scrap fence",
        "angled spike fence", "vehicle-door wall", "speaker noise decoy", "pool-pump sprinkler",
        "fictional flame defense", "scrap automated turret", "construction rapid turret",
        "spotlight tower", "repair station", "survivor command beacon", "tripwire warning bell",
        "route scanner", "portable battery bank", "medical recovery station",
    ], 4, "hero")

    add("27_vfx_decals", "vfx", "vfx_graph", [
        "electric arc VFX", "pool splash VFX", "dust and debris VFX", "non-graphic impact VFX",
        "repair spark VFX", "slow-effect VFX", "sound-wave lure VFX", "status ring VFX",
        "rain impact VFX", "mud footprint decal", "wet tire mark decal", "barricade damage decal",
        "pool caustic decal", "smoke and ember VFX",
    ], 6, "standard")

    add("30_ui_hud", "ui", "ui_compiler", [
        "boot splash", "main menu key art", "pool-house scenario card", "highway scenario card",
        "scenario briefing frame", "wave-start banner", "victory results frame", "defeat results frame",
        "defense icon family", "zombie threat icon family", "resource icon family",
        "floor navigation icon family", "status effect icon family", "scenario modifier icon family",
        "build wheel", "repair interaction panel", "accessibility settings panel",
    ], 4, "high")

    return rows


def make_prompt(row: dict[str, Any], preset: dict[str, Any]) -> str:
    visual = preset["visual_language"]
    return (
        f"Create {row['display_name']} for Zom Nom Defense. "
        f"Game identity: {visual['identity']}. Camera rule: {visual['camera']}. "
        f"Material rule: {visual['material_rule']}. "
        "Use real meter scale, clean origins, separated logical parts, coherent UV density, "
        "PBR materials, Godot 4 GLB compatibility, collision, LODs, provenance, and no logos. "
        f"Scenario tags: {', '.join(row['scenario_tags'])}."
    )


def build_jobs(preset: dict[str, Any], matrix: dict[str, Any], policy: Policy) -> list[AssetJob]:
    stage_ids = {stage["id"] for stage in matrix["stages"]}
    jobs: list[AssetJob] = []
    for row in catalog():
        if row["stage_id"] not in stage_ids:
            raise ValueError(f"Unknown stage: {row['stage_id']}")
        asset_id = slug(row["display_name"])
        variants = int(row["variants"])
        if not 1 <= variants <= policy.max_variants:
            raise ValueError(f"Invalid variants for {asset_id}")
        priority = row["priority"]
        if priority not in PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")
        dependencies = row["dependencies"]
        if len(dependencies) > policy.max_dependencies:
            raise ValueError(f"Too many dependencies for {asset_id}")
        jobs.append(AssetJob(
            job_id=f"{asset_id}-{stable_id(preset['preset_id'], row['stage_id'], asset_id)}",
            asset_id=asset_id,
            display_name=row["display_name"],
            stage_id=row["stage_id"],
            category=row["category"],
            backend=row["backend"],
            prompt=make_prompt(row, preset),
            variants=variants,
            priority=priority,
            dependencies=list(dependencies),
            godot_destination=f"Assets/Generated/{row['category']}/{asset_id}",
            validation_profile=f"{row['backend']}_v1",
            scenario_tags=list(row["scenario_tags"]),
        ))
    if len(jobs) > policy.max_assets:
        raise ValueError(f"Asset count exceeds policy: {len(jobs)}")
    return jobs


def write_outputs(jobs: list[AssetJob], preset: dict[str, Any], matrix: dict[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / "asset_jobs.jsonl").open("w", encoding="utf-8") as handle:
        for job in jobs:
            handle.write(json.dumps(asdict(job), separators=(",", ":")) + "\n")

    by_stage: dict[str, list[dict[str, Any]]] = {s["id"]: [] for s in matrix["stages"]}
    for job in jobs:
        by_stage[job.stage_id].append(asdict(job))
    for stage_id, stage_jobs in by_stage.items():
        (output / f"{stage_id}.json").write_text(json.dumps(stage_jobs, indent=2), encoding="utf-8")

    summary = {
        "version": 1,
        "preset_id": preset["preset_id"],
        "asset_count": len(jobs),
        "stage_count": len(matrix["stages"]),
        "category_counts": {},
        "scenario_counts": {},
        "security": {
            "execute_model_code": False,
            "allow_remote_urls": False,
            "allow_third_party_asset_extraction": False,
        },
    }
    for job in jobs:
        summary["category_counts"][job.category] = summary["category_counts"].get(job.category, 0) + 1
        for tag in job.scenario_tags:
            summary["scenario_counts"][tag] = summary["scenario_counts"].get(tag, 0) + 1
    (output / "bundle_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", type=Path, default=Path("WorldBundle/presets/zom_nom_defense.json"))
    parser.add_argument("--matrix", type=Path, default=Path("WorldBundle/notebook_matrix.json"))
    parser.add_argument("--output", type=Path, default=Path("WorldBundle/generated/zom_nom_defense"))
    args = parser.parse_args()

    policy = Policy()
    preset = load_json(args.preset)
    matrix = load_json(args.matrix)
    validate_inputs(preset, matrix, policy)
    jobs = build_jobs(preset, matrix, policy)
    write_outputs(jobs, preset, matrix, args.output)
    print(f"planned {len(jobs)} Zom Nom Defense asset jobs across {len(matrix['stages'])} stages")


if __name__ == "__main__":
    main()
