#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "asset_manifest.json"


def load_manifest() -> dict:
    with MANIFEST.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate() -> None:
    data = load_manifest()
    seen: set[str] = set()
    required = {"id", "category", "prompt", "target_triangles", "collision", "lods", "pbr"}
    for asset in data.get("assets", []):
        missing = required - set(asset)
        if missing:
            raise SystemExit(f"{asset.get('id', '<unknown>')}: missing {sorted(missing)}")
        if asset["id"] in seen:
            raise SystemExit(f"duplicate asset id: {asset['id']}")
        seen.add(asset["id"])
        if asset["target_triangles"] <= 0:
            raise SystemExit(f"{asset['id']}: target_triangles must be positive")
        if not 1 <= asset["lods"] <= 5:
            raise SystemExit(f"{asset['id']}: lods must be between 1 and 5")
    print(f"validated {len(seen)} assets")


def matrix(requested: str) -> None:
    data = load_manifest()
    by_id = {asset["id"]: asset for asset in data["assets"]}
    ids = list(by_id) if requested.strip().lower() == "all" else [x.strip() for x in requested.split(",") if x.strip()]
    unknown = [asset_id for asset_id in ids if asset_id not in by_id]
    if unknown:
        raise SystemExit(f"unknown asset IDs: {', '.join(unknown)}")
    include = [
        {
            "asset_id": asset_id,
            "category": by_id[asset_id]["category"],
            "priority": by_id[asset_id]["priority"],
        }
        for asset_id in ids
    ]
    print("matrix=" + json.dumps({"include": include}, separators=(",", ":")))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if command == "validate":
        validate()
    elif command == "matrix":
        matrix(sys.argv[2] if len(sys.argv) > 2 else "all")
    else:
        raise SystemExit(f"unknown command: {command}")
