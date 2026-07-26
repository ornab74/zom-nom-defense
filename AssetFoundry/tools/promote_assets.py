#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    incoming = Path(args.incoming)
    destination = Path(args.destination)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    for spec in manifest["assets"]:
        source = incoming / spec["id"]
        if not source.exists():
            continue
        target = destination / spec["category"] / spec["id"]
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        (target / "godot_import.json").write_text(
            json.dumps(
                {
                    "asset_id": spec["id"],
                    "collision": spec["collision"],
                    "lods": spec["lods"],
                    "unit_scale_meters": manifest["defaults"]["unit_scale_meters"],
                    "generated": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"promoted {spec['id']} -> {target}")


if __name__ == "__main__":
    main()
