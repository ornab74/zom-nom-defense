from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
from dataclasses import asdict
from pathlib import Path

from asset_catalog import AssetJob, build_catalog

SAFE_ID = re.compile(r"^[a-z0-9_]{1,96}$")
ALLOWED_EXTENSIONS = {
    ".glb", ".gltf", ".bin", ".png", ".jpg", ".jpeg", ".webp", ".exr",
    ".json", ".md", ".txt", ".tres", ".anim", ".wav", ".ogg", ".mp3",
}
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(root: Path, path: Path) -> Path:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    if root_resolved != path_resolved and root_resolved not in path_resolved.parents:
        raise ValueError(f"path escapes root: {path}")
    return path_resolved.relative_to(root_resolved)


def reject_symlink(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"symlink rejected: {path}")
    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink rejected: {path}")
    except FileNotFoundError:
        raise


def validate_source_file(bundle_root: Path, path: Path) -> None:
    reject_symlink(path)
    relative = safe_relative(bundle_root, path)
    if any(part in {"..", ".git", ".github", "addons"} for part in relative.parts):
        raise ValueError(f"unsafe bundle path: {relative}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"extension not approved: {path.suffix}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file too large: {path}")


def godot_scene(job: AssetJob, glb_name: str) -> str:
    return f'''[gd_scene load_steps=2 format=3]\n\n[ext_resource type="PackedScene" path="res://{job.godot_destination}/{glb_name}" id="1_asset"]\n\n[node name="{job.asset_id}" type="Node3D"]\nmetadata/asset_id = "{job.asset_id}"\nmetadata/family = "{job.family}"\nmetadata/backend = "{job.backend}"\nmetadata/validation_profile = "{job.validation_profile}"\n\n[node name="Visual" parent="." instance=ExtResource("1_asset")]\n'''


def import_metadata(job: AssetJob, copied_files: list[dict]) -> dict:
    return {
        "version": 2,
        "asset": asdict(job),
        "files": copied_files,
        "mapping": {
            "destination": job.godot_destination,
            "scene": f"{job.godot_destination}/{job.asset_id}.tscn",
            "scenario_tags": list(job.scenario_tags),
            "backend": job.backend,
        },
        "godot": {
            "coordinate_system": "y_up",
            "unit_scale_meters": 1.0,
            "lod_ratios": list(job.lod_ratios),
            "collision": job.collision,
            "rig": job.rig,
            "animations": list(job.animations),
        },
    }


def stitch(incoming: Path, output: Path) -> dict:
    catalog = {job.asset_id: job for job in build_catalog()}
    output.mkdir(parents=True, exist_ok=True)
    registry: dict[str, dict] = {}
    missing: list[str] = []
    quarantined: dict[str, str] = {}

    for asset_id, job in sorted(catalog.items()):
        if not SAFE_ID.fullmatch(asset_id):
            raise ValueError(f"catalog contains unsafe id: {asset_id}")
        source = incoming / asset_id
        if not source.exists():
            missing.append(asset_id)
            continue
        if not source.is_dir():
            quarantined[asset_id] = "bundle path is not a directory"
            continue

        try:
            reject_symlink(source)
            all_files = [path for path in source.rglob("*") if path.is_file()]
            total_bytes = sum(path.stat().st_size for path in all_files)
            if total_bytes > MAX_BUNDLE_BYTES:
                raise ValueError("bundle exceeds byte limit")
            glbs = [path for path in all_files if path.suffix.lower() == ".glb"]
            if len(glbs) != 1:
                raise ValueError(f"expected exactly one GLB, found {len(glbs)}")

            destination = output / job.godot_destination
            destination.mkdir(parents=True, exist_ok=True)
            copied: list[dict] = []
            for path in all_files:
                validate_source_file(source, path)
                relative = safe_relative(source, path)
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                copied.append({
                    "path": str(relative).replace(os.sep, "/"),
                    "sha256": sha256(target),
                    "bytes": target.stat().st_size,
                })

            glb_relative = safe_relative(source, glbs[0])
            wrapper = destination / f"{asset_id}.tscn"
            wrapper.write_text(godot_scene(job, str(glb_relative).replace(os.sep, "/")), encoding="utf-8")
            metadata = import_metadata(job, copied)
            (destination / "asset_mapping.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            registry[asset_id] = {
                "scene": f"res://{job.godot_destination}/{asset_id}.tscn",
                "destination": job.godot_destination,
                "category": job.category,
                "family": job.family,
                "backend": job.backend,
                "scenario_tags": list(job.scenario_tags),
                "files": copied,
            }
        except Exception as exc:
            quarantined[asset_id] = str(exc)

    registry_root = output / "Common/Systems/asset_foundry"
    registry_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "assets": registry,
        "missing": missing,
        "quarantined": quarantined,
    }
    (registry_root / "asset_foundry_registry.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (registry_root / "asset_foundry_registry.gd").write_text(
        '''extends Node\n\nconst REGISTRY_PATH := "res://Common/Systems/asset_foundry/asset_foundry_registry.json"\nvar registry: Dictionary = {}\n\nfunc _ready() -> void:\n    if FileAccess.file_exists(REGISTRY_PATH):\n        var file := FileAccess.open(REGISTRY_PATH, FileAccess.READ)\n        var parsed = JSON.parse_string(file.get_as_text())\n        if parsed is Dictionary:\n            registry = parsed\n\nfunc scene_for(asset_id: String) -> PackedScene:\n    var entry: Dictionary = registry.get("assets", {}).get(asset_id, {})\n    var path: String = entry.get("scene", "")\n    return load(path) as PackedScene if not path.is_empty() else null\n''',
        encoding="utf-8",
    )
    install = {
        "generated_asset_count": len(registry),
        "missing_asset_count": len(missing),
        "quarantined_asset_count": len(quarantined),
        "autoload": {
            "name": "AssetFoundryRegistry",
            "path": "res://Common/Systems/asset_foundry/asset_foundry_registry.gd",
        },
        "copy_root_into_project": str(output),
    }
    (output / "ASSET_FOUNDRY_INSTALL.json").write_text(json.dumps(install, indent=2), encoding="utf-8")
    return {"registry": payload, "install": install}


def archive_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--zip", type=Path)
    args = parser.parse_args()
    result = stitch(args.incoming, args.output)
    if args.zip:
        archive_directory(args.output, args.zip)
    print(json.dumps(result["install"], indent=2))


if __name__ == "__main__":
    main()
