from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

ALLOWED_BACKENDS = {
    "modular_architecture_v2", "environment_structure_v2", "tree_polyflow_v3",
    "foliage_cluster_v2", "character_surface_v2", "vehicle_chassis_v2",
    "defense_device_v2", "prop_family_v2", "ui_asset_v2", "vfx_graph_v2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite_positive(value: Any, maximum: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0 or number > maximum:
        raise ValueError(f"invalid bounded number: {value}")
    return number


def validate_contract(contract: dict[str, Any]) -> None:
    required = {
        "asset_id", "display_name", "category", "family", "backend", "prompt",
        "godot_destination", "target_vertices", "target_triangles", "lod_ratios",
        "collision", "rig", "validation_profile",
    }
    missing = required - contract.keys()
    if missing:
        raise ValueError(f"contract missing fields: {sorted(missing)}")
    if contract["backend"] not in ALLOWED_BACKENDS:
        raise ValueError(f"unapproved backend: {contract['backend']}")
    if not str(contract["godot_destination"]).startswith("Assets/Generated/"):
        raise ValueError("destination must be repository-owned Assets/Generated path")
    if ".." in str(contract["godot_destination"]):
        raise ValueError("path traversal rejected")
    _finite_positive(contract["target_vertices"], 1_000_000)
    _finite_positive(contract["target_triangles"], 2_000_000)
    ratios = [float(value) for value in contract["lod_ratios"]]
    if not ratios or ratios[0] != 1.0 or any(not 0 < value <= 1 for value in ratios):
        raise ValueError("invalid LOD ratios")


def write_generation_request(contract: dict[str, Any], output_root: Path) -> Path:
    validate_contract(contract)
    request = {
        "version": 3,
        "asset_prompt": contract["prompt"],
        "asset_id": contract["asset_id"],
        "backend": contract["backend"],
        "geometry": {
            "target_vertices": contract["target_vertices"],
            "target_triangles": contract["target_triangles"],
            "topology_state": "z=[position,normal,topology_embedding]",
            "topology_decode": "spacetime_threshold_then_manifold_validation",
            "lod_ratios": contract["lod_ratios"],
        },
        "godot": {
            "destination": contract["godot_destination"],
            "coordinate_system": "y_up",
            "unit_scale_meters": 1.0,
            "collision": contract["collision"],
            "rig": contract["rig"],
            "animations": contract.get("animations", []),
        },
        "security": {
            "execute_model_python": False,
            "allow_remote_asset_urls": False,
            "generated_destination_is_advisory_only": True,
        },
    }
    path = output_root / "generation_request.json"
    path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    return path


def run_asset_contract(contract: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """Prepare a deterministic run directory and invoke reviewed backend glue.

    Specialized model execution remains explicit in the Universal PolyFlow notebook.
    This function never executes model-written code and never invents a successful GLB.
    """
    output_root.mkdir(parents=True, exist_ok=True)
    request_path = write_generation_request(contract, output_root)
    backend_driver = Path("AssetFoundry/backends") / f"{contract['backend']}.py"
    result = {
        "asset_id": contract["asset_id"],
        "backend": contract["backend"],
        "request": str(request_path),
        "backend_driver": str(backend_driver),
        "driver_available": backend_driver.exists(),
        "status": "prepared",
    }
    if backend_driver.exists():
        subprocess.run(
            ["python", str(backend_driver), "--request", str(request_path), "--output", str(output_root)],
            check=True,
        )
        result["status"] = "backend_completed"
    else:
        print(
            "No specialized backend driver is installed yet. Use the Universal PolyFlow "
            "cells to generate the GLB, textures, rigs, and previews into:", output_root
        )
    (output_root / "runner_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def validate_asset_bundle(contract: dict[str, Any], output_root: Path) -> dict[str, Any]:
    validate_contract(contract)
    glbs = sorted(output_root.glob("*.glb"))
    textures = sorted(path for path in output_root.rglob("*.png") if path.is_file())
    required_maps = {"albedo", "normal", "roughness"}
    texture_names = " ".join(path.name.lower() for path in textures)
    missing_maps = sorted(name for name in required_maps if name not in texture_names)
    checks = {
        "exactly_one_glb": len(glbs) == 1,
        "required_texture_maps": not missing_maps,
        "generation_request_exists": (output_root / "generation_request.json").exists(),
        "asset_contract_exists": (output_root / "asset_contract.json").exists(),
    }
    files = []
    for path in sorted(p for p in output_root.rglob("*") if p.is_file()):
        files.append({
            "path": str(path.relative_to(output_root)),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    validation = {
        "asset_id": contract["asset_id"],
        "passed": all(checks.values()),
        "checks": checks,
        "missing_texture_maps": missing_maps,
        "files": files,
        "godot_destination": contract["godot_destination"],
    }
    (output_root / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    return validation


def package_asset_bundle(contract: dict[str, Any], output_root: Path) -> Path:
    validation = json.loads((output_root / "validation.json").read_text(encoding="utf-8"))
    if not validation.get("passed"):
        raise RuntimeError("refusing to package a failed asset bundle")
    manifest = {
        "version": 2,
        "asset_id": contract["asset_id"],
        "repository_destination": contract["godot_destination"],
        "backend": contract["backend"],
        "validation_profile": contract["validation_profile"],
        "provenance": {
            "manual_colab_run": True,
            "model_written_code_executed": False,
        },
    }
    (output_root / "asset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    destination = output_root.parent / f"{contract['asset_id']}_asset_bundle.zip"
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in output_root.rglob("*"):
            if path.is_file():
                archive.write(path, arcname=f"{contract['asset_id']}/{path.relative_to(output_root)}")
    return destination
