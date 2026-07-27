#!/usr/bin/env python3
"""Stitch validated generated assets into a Godot 4 project patch.

The stitcher consumes asset job manifests and validated output folders. It never
executes generated scripts. It creates deterministic import metadata, wrapper
scenes, registry resources, scenario manifests, and a ZIP patch for review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

SAFE_ID = re.compile(r"^[a-z0-9_]{1,80}$")
ALLOWED_EXTENSIONS = {".glb", ".gltf", ".png", ".jpg", ".jpeg", ".webp", ".json", ".tres", ".tscn", ".wav", ".ogg"}
MAX_FILE_BYTES = 512 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jobs(path: Path) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                jobs.append(json.loads(line))
    return jobs


def validate_asset_id(asset_id: str) -> None:
    if not SAFE_ID.fullmatch(asset_id):
        raise ValueError(f"Unsafe asset id: {asset_id}")


def wrapper_scene(asset_id: str, glb_res_path: str, category: str) -> str:
    collision_mode = "trimesh" if category in {"architecture", "terrain", "environment"} else "convex"
    return f'''[gd_scene load_steps=2 format=3]\n\n[ext_resource type="PackedScene" path="{glb_res_path}" id="1_asset"]\n\n[node name="{asset_id}" type="Node3D"]\nmetadata/asset_id = "{asset_id}"\nmetadata/category = "{category}"\nmetadata/collision_profile = "{collision_mode}"\n\n[node name="Visual" parent="." instance=ExtResource("1_asset")]\n'''


def registry_script() -> str:
    return '''extends Node\n\nvar _assets: Dictionary = {}\n\nfunc _ready() -> void:\n\t_load_registry()\n\nfunc _load_registry() -> void:\n\tvar file := FileAccess.open("res://Assets/Generated/world_bundle_registry.json", FileAccess.READ)\n\tif file == null:\n\t\tpush_warning("World bundle registry is missing")\n\t\treturn\n\tvar parsed = JSON.parse_string(file.get_as_text())\n\tif parsed is Dictionary:\n\t\t_assets = parsed.get("assets", {})\n\nfunc has_asset(asset_id: StringName) -> bool:\n\treturn _assets.has(String(asset_id))\n\nfunc scene_path(asset_id: StringName) -> String:\n\tvar entry: Dictionary = _assets.get(String(asset_id), {})\n\treturn entry.get("scene", "")\n\nfunc instantiate(asset_id: StringName) -> Node:\n\tvar path := scene_path(asset_id)\n\tif path.is_empty():\n\t\treturn null\n\tvar packed := load(path) as PackedScene\n\treturn packed.instantiate() if packed else null\n'''


def scenario_resource(scenario_id: str, display_name: str, asset_ids: list[str]) -> str:
    quoted = ", ".join(json.dumps(asset_id) for asset_id in sorted(asset_ids))
    return f'''[gd_resource type="Resource" format=3]\n\n[resource]\nresource_name = "{display_name}"\nmetadata/scenario_id = "{scenario_id}"\nmetadata/generated_asset_ids = [{quoted}]\n'''


def find_primary_glb(folder: Path) -> Path | None:
    preferred = [folder / "game_asset.glb", folder / "asset.glb"]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    matches = sorted(folder.glob("*.glb"))
    return matches[0] if matches else None


def copy_validated_files(source: Path, destination: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"Oversized asset file: {path}")
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append({
            "path": str(relative).replace(os.sep, "/"),
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
        })
    return copied


def stitch(jobs: list[dict[str, Any]], incoming: Path, patch_root: Path) -> dict[str, Any]:
    generated_root = patch_root / "Assets" / "Generated"
    systems_root = patch_root / "Common" / "Systems" / "world_bundle"
    scenarios_root = patch_root / "Stages" / "GeneratedScenarios"
    generated_root.mkdir(parents=True, exist_ok=True)
    systems_root.mkdir(parents=True, exist_ok=True)
    scenarios_root.mkdir(parents=True, exist_ok=True)

    registry: dict[str, Any] = {"version": 1, "assets": {}, "missing": []}
    scenario_assets: dict[str, list[str]] = {"pool_house_siege": [], "highway_last_stand": [], "shared": []}

    for job in jobs:
        asset_id = job["asset_id"]
        validate_asset_id(asset_id)
        source = incoming / asset_id
        if not source.is_dir():
            registry["missing"].append(asset_id)
            continue

        category = job["category"]
        destination = generated_root / category / asset_id
        destination.mkdir(parents=True, exist_ok=True)
        copied = copy_validated_files(source, destination)
        primary_source = find_primary_glb(destination)
        if primary_source is None:
            registry["missing"].append(asset_id)
            continue

        relative_glb = primary_source.relative_to(patch_root).as_posix()
        scene_path = destination / f"{asset_id}.tscn"
        scene_path.write_text(
            wrapper_scene(asset_id, f"res://{relative_glb}", category),
            encoding="utf-8",
        )
        registry["assets"][asset_id] = {
            "display_name": job["display_name"],
            "category": category,
            "backend": job["backend"],
            "scene": f"res://{scene_path.relative_to(patch_root).as_posix()}",
            "files": copied,
            "variants": job["variants"],
            "validation_profile": job["validation_profile"],
        }
        for tag in job.get("scenario_tags", ["shared"]):
            scenario_assets.setdefault(tag, []).append(asset_id)

    (generated_root / "world_bundle_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    (systems_root / "world_bundle_registry.gd").write_text(registry_script(), encoding="utf-8")

    names = {"pool_house_siege": "Pool House Siege", "highway_last_stand": "Highway Last Stand", "shared": "Shared Zom Nom Assets"}
    for scenario_id, asset_ids in scenario_assets.items():
        if not asset_ids:
            continue
        (scenarios_root / f"{scenario_id}.tres").write_text(
            scenario_resource(scenario_id, names.get(scenario_id, scenario_id), asset_ids),
            encoding="utf-8",
        )

    install = {
        "version": 1,
        "autoload": {
            "name": "WorldBundleRegistry",
            "path": "res://Common/Systems/world_bundle/world_bundle_registry.gd",
        },
        "generated_asset_count": len(registry["assets"]),
        "missing_asset_count": len(registry["missing"]),
        "instructions": [
            "Copy patch contents into the Godot project root.",
            "Add WorldBundleRegistry as an autoload if not already present.",
            "Open the project once so Godot imports GLB and texture files.",
            "Review collisions, navigation, LOD transitions, animations, and material flags before release.",
        ],
    }
    (patch_root / "WORLD_BUNDLE_INSTALL.json").write_text(json.dumps(install, indent=2), encoding="utf-8")
    return {"registry": registry, "install": install}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("WorldBundle/output/godot_patch"))
    parser.add_argument("--zip", type=Path, default=Path("WorldBundle/output/zom_nom_godot_patch.zip"))
    args = parser.parse_args()

    jobs = load_jobs(args.jobs)
    with tempfile.TemporaryDirectory(prefix="zom_nom_stitch_") as temporary:
        patch_root = Path(temporary) / "patch"
        result = stitch(jobs, args.incoming, patch_root)
        if args.output.exists():
            shutil.rmtree(args.output)
        shutil.copytree(patch_root, args.output)
        args.zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(patch_root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(patch_root).as_posix())
    print(json.dumps(result["install"], indent=2))
    print("Patch ZIP:", args.zip)


if __name__ == "__main__":
    main()
