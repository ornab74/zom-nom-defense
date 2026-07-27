#!/usr/bin/env python3
"""Compile a large, coherent prompt library for Zom Nom Defense.

The source vocabulary is intentionally curated and compositional. It can emit
thousands of controlled prompt jobs without producing random, incoherent art.
Every prompt carries geometry, topology, material, camera, licensing, and Godot
import requirements so generated assets remain part of one visual language.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

STYLE_BIBLE = {
    "identity": (
        "grounded stylized realism, handcrafted survival-comedy, sun-faded "
        "southeastern suburbia, believable construction, strong top-down "
        "readability, no generic science-fiction, no brand logos"
    ),
    "camera": (
        "orthographic-friendly three-quarter product view, centered object, "
        "neutral lens, full silhouette visible, generous negative space"
    ),
    "lighting": (
        "neutral overcast studio lighting, soft contact shadow only, no baked "
        "dramatic lighting, physically plausible material response"
    ),
    "palette": [
        "sun-faded teal",
        "warm weathered stucco",
        "charcoal asphalt",
        "oxidized orange",
        "pool cyan",
        "dry grass olive",
        "cream plastic",
        "deep plum interface accents",
    ],
    "negative": (
        "AI artifacts, melted geometry, fused parts, duplicate features, floating "
        "objects, impossible construction, non-manifold mesh, zero-area faces, "
        "interior polygon soup, stretched UVs, baked shadows, text, logos, "
        "watermarks, excessive gore, generic cyberpunk, toy proportions"
    ),
}

QUALITY_TIERS = {
    "draft": {
        "resolution": 768,
        "texture_resolution": 1024,
        "shape_steps": 12,
        "texture_steps": 12,
        "lods": 2,
    },
    "production": {
        "resolution": 1536,
        "texture_resolution": 2048,
        "shape_steps": 24,
        "texture_steps": 28,
        "lods": 4,
    },
    "cinematic": {
        "resolution": 2048,
        "texture_resolution": 4096,
        "shape_steps": 36,
        "texture_steps": 40,
        "lods": 4,
    },
}

MATERIAL_STATES = [
    "clean but lived-in",
    "sun-faded and lightly weathered",
    "rain-streaked with grounded grime",
    "neglected for several months",
    "recently damaged during evacuation",
    "field-repaired with coherent scavenged materials",
]

DAMAGE_STATES = [
    "intact",
    "light cosmetic damage",
    "one clear functional failure",
    "partially collapsed but readable",
]

REFERENCE_VIEWS = [
    "front three-quarter",
    "rear three-quarter",
    "left orthographic",
    "right orthographic",
    "top orthographic",
    "detail material crop",
]

CATEGORY_RULES = {
    "architecture": {
        "collision": "trimesh_static",
        "topology": [
            "real wall thickness",
            "closed roof volumes",
            "separate doors and windows",
            "walkable floor surfaces",
            "no hidden duplicate walls",
            "modular grid alignment at 0.5 meter increments",
        ],
        "pbr": ["albedo", "normal", "roughness", "ao"],
        "triangle_range": [50000, 180000],
    },
    "environment": {
        "collision": "box_or_trimesh",
        "topology": [
            "grounded origin",
            "tileable modular seams",
            "no floating under-surfaces",
            "wind-safe foliage cards where applicable",
        ],
        "pbr": ["albedo", "normal", "roughness", "ao", "opacity_optional"],
        "triangle_range": [8000, 80000],
    },
    "vehicle": {
        "collision": "convex_decomposition",
        "topology": [
            "believable wheelbase and suspension clearance",
            "separate wheels",
            "closed body panels",
            "simple readable interior",
            "no manufacturer marks",
        ],
        "pbr": ["albedo", "normal", "roughness", "metallic", "ao"],
        "triangle_range": [55000, 150000],
    },
    "character": {
        "collision": "capsule",
        "topology": [
            "animation-ready deformation loops",
            "separate fingers where budget permits",
            "closed mouth and eye sockets",
            "no fused clothing layers",
            "neutral bind pose",
            "clean shoulder, elbow, hip, knee and ankle loops",
        ],
        "pbr": ["albedo", "normal", "roughness", "ao"],
        "triangle_range": [35000, 80000],
    },
    "defense": {
        "collision": "box_or_convex",
        "topology": [
            "consistent 2 meter gameplay footprint",
            "visible upgrade sockets",
            "separate animated parts",
            "three readable damage states",
            "no real-world weapon branding",
        ],
        "pbr": ["albedo", "normal", "roughness", "metallic", "ao"],
        "triangle_range": [22000, 52000],
    },
    "prop": {
        "collision": "convex_decomposition",
        "topology": [
            "grounded pivot",
            "separate movable lids or doors",
            "no unreadable micro-clutter",
            "silhouette readable from tactical camera",
        ],
        "pbr": ["albedo", "normal", "roughness", "metallic_optional", "ao"],
        "triangle_range": [3000, 50000],
    },
    "ui": {
        "collision": "none",
        "topology": [
            "transparent background",
            "safe margins",
            "no text baked into image",
            "consistent line weight",
            "recognizable at 24 pixels",
        ],
        "pbr": ["rgba"],
        "triangle_range": [0, 0],
    },
    "vfx": {
        "collision": "none",
        "topology": [
            "transparent background",
            "frame-safe sprite bounds",
            "no hard rectangular edges",
            "consistent animation cadence",
        ],
        "pbr": ["rgba"],
        "triangle_range": [0, 0],
    },
}

ASSET_FAMILIES = {
    "architecture": {
        "pool_house": [
            "two-story suburban pool house exterior",
            "modular two-story house interior shell",
            "L-shaped residential staircase with landing",
            "second-floor balcony and sliding-door threshold",
            "attached two-car garage interior",
            "small pool pump utility shed",
            "reinforced survivor safe room",
            "roof-access and gutter kit",
        ],
        "roadside": [
            "abandoned roadside gas station shell",
            "weathered motel room and balcony kit",
            "concrete highway overpass segment",
            "storm-drain tunnel junction",
            "sewer access shaft and chamber",
            "freestanding corrugated carport",
        ],
    },
    "environment": {
        "pool_yard": [
            "in-ground swimming pool basin",
            "pool coping and ceramic tile band",
            "weathered modular concrete pool deck",
            "patchy southeastern backyard lawn",
            "neglected raised vegetable garden",
            "privacy hedge and fence line",
        ],
        "road": [
            "cracked asphalt road module",
            "muddy roadside drainage ditch",
            "galvanized highway guardrail",
            "concrete culvert opening",
            "storm debris cluster",
            "leaf litter and wet organic decal set",
        ],
        "foliage": [
            "mature live oak tree",
            "loblolly pine tree",
            "wind-shaped maple tree",
            "ornamental crepe myrtle",
            "overgrown hedge section",
            "roadside weed and grass cluster",
        ],
    },
    "vehicle": {
        "survivor": [
            "late 1970s American muscle car survivor platform",
            "small unbranded 125cc street motorcycle with cargo rack",
            "pool-maintenance electric utility cart",
            "weathered flatbed tow truck",
        ],
        "wrecks": [
            "front-damaged compact sedan",
            "rear-damaged midsize sedan",
            "abandoned work pickup truck",
            "early-2000s family SUV",
            "unbranded delivery van",
            "decommissioned generic patrol sedan",
            "evacuation school bus barricade",
        ],
    },
    "character": {
        "common": [
            "adult male grunt zombie in torn work clothes",
            "adult female grunt zombie in damaged casual clothes",
            "elder shambler zombie in cardigan and loose trousers",
            "fast runner zombie in damaged athletic clothing",
        ],
        "specialists": [
            "lean climber zombie with strong hands and feet",
            "broad brute zombie in layered workwear",
            "low-profile crawler zombie",
            "thin screecher zombie in torn rain jacket",
            "slender spitter zombie in stained utility clothing",
            "waterlogged pool swimmer zombie",
            "construction roofer zombie with removable harness",
            "generic paramedic zombie without agency marks",
            "roadside mechanic zombie in coveralls",
            "heavy firefighter zombie with removable gear",
        ],
        "bosses": [
            "eccentric backyard host zombie boss with separate float ring",
            "highway pileup brute boss wearing layered road debris armor",
            "storm-drain lurker boss with asymmetric silhouette",
        ],
    },
    "defense": {
        "barriers": [
            "basic lumber and sheet-metal barricade",
            "reinforced sandbag barricade",
            "electrified scrap fence",
            "angled spike fence",
            "temporary vehicle-door wall",
        ],
        "devices": [
            "speaker-horn noise decoy",
            "pool-pump cooling sprinkler",
            "fictional controlled flame emitter",
            "scrap-built automated turret",
            "construction-tool rapid turret",
            "portable survivor spotlight tower",
            "compact repair station",
            "survivor command beacon",
            "tripwire warning bell",
            "battery-powered route scanner",
        ],
    },
    "prop": {
        "backyard": [
            "propane grill",
            "patio table and stackable chairs",
            "pool float and foam noodle set",
            "hard cooler and drink jug",
            "pool maintenance tools",
            "garden tools and wheelbarrow",
            "hose reel and sprinkler",
            "weathered planter set",
        ],
        "interior": [
            "worn living-room furniture set",
            "suburban kitchen clutter set",
            "bedroom furniture kit",
            "bathroom fixture kit",
            "garage storage and tool clutter",
            "survivor personal belongings",
            "medical supply set",
            "food and water supply set",
        ],
        "road": [
            "traffic barrier set",
            "blank road-sign set",
            "vehicle debris set",
            "camping supply set",
            "electrical supply set",
            "sorted scrap pile set",
            "trash and recycling set",
        ],
    },
    "ui": {
        "screens": [
            "main menu key art",
            "pool-house campaign card",
            "highway campaign card",
            "scenario briefing frame",
            "wave-start banner frame",
            "victory results frame",
            "defeat results frame",
            "minimal boot splash",
        ],
        "icons": [
            "defense icon family",
            "zombie threat icon family",
            "resource icon family",
            "floor navigation icon family",
            "status effect icon family",
            "scenario modifier icon family",
        ],
    },
    "vfx": {
        "sprites": [
            "electric arc sprite sheet",
            "pool splash sprite sheet",
            "dust and debris sprite sheet",
            "non-graphic zombie impact sprite sheet",
            "repair spark sprite sheet",
            "frost and slow-effect sprite sheet",
            "sound-wave lure sprite sheet",
            "status ring sprite sheet",
        ],
    },
}

FUNCTIONAL_VARIANTS = {
    "architecture": [
        "intact playable version",
        "breached gameplay version",
        "night-lit version with separate emissive masks",
    ],
    "environment": [
        "dry daylight state",
        "wet post-rain state",
        "damaged siege state",
    ],
    "vehicle": [
        "intact abandoned state",
        "collision-damaged state",
        "salvaged stripped state",
    ],
    "character": [
        "base clothing colorway",
        "alternate clothing colorway",
        "muddy wet variant",
        "lightly armored encounter variant",
    ],
    "defense": [
        "tier one",
        "tier two reinforced",
        "tier three specialized",
        "critical damage state",
    ],
    "prop": [
        "clean readable version",
        "weathered version",
        "damaged version",
    ],
    "ui": [
        "default state",
        "hover state",
        "disabled state",
        "completed state",
    ],
    "vfx": [
        "small impact",
        "medium impact",
        "large impact",
        "looping ambient state",
    ],
}

SCENARIO_TAGS = {
    "pool_house": ["pool_party", "vertical_house", "suburban_backyard"],
    "pool_yard": ["pool_party", "suburban_backyard"],
    "backyard": ["pool_party", "suburban_backyard"],
    "interior": ["pool_party", "vertical_house"],
    "roadside": ["car_defense", "highway"],
    "road": ["car_defense", "highway"],
    "wrecks": ["car_defense", "highway"],
    "survivor": ["shared"],
    "common": ["shared"],
    "specialists": ["shared"],
    "bosses": ["shared"],
    "barriers": ["shared"],
    "devices": ["shared"],
    "screens": ["shared"],
    "icons": ["shared"],
    "sprites": ["shared"],
    "foliage": ["shared"],
}


@dataclass(frozen=True)
class PromptJob:
    job_id: str
    asset_id: str
    category: str
    family: str
    subject: str
    functional_variant: str
    material_state: str
    damage_state: str
    view: str
    quality: str
    scenario_tags: list[str]
    positive_prompt: str
    negative_prompt: str
    target_triangles: int
    collision: str
    lods: int
    pbr: list[str]
    topology_rules: list[str]
    provenance_policy: str = "generated_or_cc0_only"
    output_format: str = "glb"
    unit_scale_meters: float = 1.0
    coordinate_system: str = "y_up"


def slug(value: str) -> str:
    result = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in result:
        result = result.replace("__", "_")
    return result.strip("_")


def stable_id(parts: Iterable[str]) -> str:
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def triangle_budget(category: str, subject_index: int, quality: str) -> int:
    low, high = CATEGORY_RULES[category]["triangle_range"]
    if high == 0:
        return 0
    position = (subject_index % 7) / 6.0
    base = int(low + (high - low) * position)
    multiplier = {"draft": 0.55, "production": 1.0, "cinematic": 1.35}[quality]
    return max(1000, int(base * multiplier))


def build_prompt(
    category: str,
    subject: str,
    functional_variant: str,
    material_state: str,
    damage_state: str,
    view: str,
) -> str:
    rules = "; ".join(CATEGORY_RULES[category]["topology"])
    return (
        f"Create {subject}, {functional_variant}, {material_state}, {damage_state}. "
        f"{STYLE_BIBLE['identity']}. {STYLE_BIBLE['camera']}. "
        f"Reference view: {view}. {STYLE_BIBLE['lighting']}. "
        f"Production geometry requirements: {rules}. "
        "Use real-world meter scale, grounded origin, separated logical parts, "
        "clean UVs, consistent texel density, and game-ready physically based materials."
    )


def compile_jobs(quality: str = "production", limit: int | None = None) -> list[PromptJob]:
    if quality not in QUALITY_TIERS:
        raise ValueError(f"unknown quality tier: {quality}")

    jobs: list[PromptJob] = []
    for category, families in ASSET_FAMILIES.items():
        variants = FUNCTIONAL_VARIANTS[category]
        for family, subjects in families.items():
            tags = SCENARIO_TAGS.get(family, ["shared"])
            for subject_index, subject in enumerate(subjects):
                asset_id = slug(subject)
                combinations = itertools.product(
                    variants,
                    MATERIAL_STATES,
                    DAMAGE_STATES,
                    REFERENCE_VIEWS,
                )
                for functional_variant, material_state, damage_state, view in combinations:
                    job_hash = stable_id(
                        [
                            category,
                            family,
                            subject,
                            functional_variant,
                            material_state,
                            damage_state,
                            view,
                            quality,
                        ]
                    )
                    job = PromptJob(
                        job_id=f"{asset_id}-{job_hash}",
                        asset_id=asset_id,
                        category=category,
                        family=family,
                        subject=subject,
                        functional_variant=functional_variant,
                        material_state=material_state,
                        damage_state=damage_state,
                        view=view,
                        quality=quality,
                        scenario_tags=list(tags),
                        positive_prompt=build_prompt(
                            category,
                            subject,
                            functional_variant,
                            material_state,
                            damage_state,
                            view,
                        ),
                        negative_prompt=STYLE_BIBLE["negative"],
                        target_triangles=triangle_budget(category, subject_index, quality),
                        collision=CATEGORY_RULES[category]["collision"],
                        lods=QUALITY_TIERS[quality]["lods"],
                        pbr=list(CATEGORY_RULES[category]["pbr"]),
                        topology_rules=list(CATEGORY_RULES[category]["topology"]),
                    )
                    jobs.append(job)
                    if limit is not None and len(jobs) >= limit:
                        return jobs
    return jobs


def write_jsonl(jobs: list[PromptJob], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for job in jobs:
            handle.write(json.dumps(asdict(job), separators=(",", ":")) + "\n")


def write_summary(jobs: list[PromptJob], output: Path) -> None:
    by_category: dict[str, int] = {}
    by_scenario: dict[str, int] = {}
    for job in jobs:
        by_category[job.category] = by_category.get(job.category, 0) + 1
        for tag in job.scenario_tags:
            by_scenario[tag] = by_scenario.get(tag, 0) + 1
    summary = {
        "version": 1,
        "job_count": len(jobs),
        "categories": by_category,
        "scenario_tags": by_scenario,
        "style_bible": STYLE_BIBLE,
        "quality_tiers": QUALITY_TIERS,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", choices=sorted(QUALITY_TIERS), default="production")
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--output", default="AssetFoundry/generated_prompt_jobs.jsonl")
    parser.add_argument("--summary", default="AssetFoundry/generated_prompt_summary.json")
    args = parser.parse_args()

    if args.limit <= 0:
        raise SystemExit("--limit must be positive")
    jobs = compile_jobs(args.quality, args.limit)
    write_jsonl(jobs, Path(args.output))
    write_summary(jobs, Path(args.summary))
    print(f"compiled {len(jobs)} coherent asset-generation jobs")


if __name__ == "__main__":
    main()
