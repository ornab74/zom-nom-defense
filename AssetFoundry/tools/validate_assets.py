#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incoming", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    incoming = Path(args.incoming)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report: dict[str, list[dict]] = {"passed": [], "failed": []}

    for spec in manifest["assets"]:
        folder = incoming / spec["id"]
        glbs = sorted(folder.glob("*.glb"))
        metadata = folder / "metadata.json"
        failures: list[str] = []

        if not glbs:
            failures.append("missing GLB")
        if not metadata.exists():
            failures.append("missing metadata.json")
        for map_name in spec["pbr"]:
            texture = folder / f"{spec['id']}_{map_name}.png"
            if not texture.exists():
                failures.append(f"missing texture {texture.name}")

        if glbs:
            size_mb = glbs[0].stat().st_size / (1024 * 1024)
            if size_mb > 250:
                failures.append(f"GLB too large: {size_mb:.1f} MB")

        record = {"id": spec["id"], "files": []}
        if folder.exists():
            for file in sorted(folder.glob("*")):
                if file.is_file():
                    record["files"].append({
                        "name": file.name,
                        "sha256": sha256(file),
                        "bytes": file.stat().st_size,
                    })

        if failures:
            record["failures"] = failures
            report["failed"].append(record)
        else:
            report["passed"].append(record)

    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if report["failed"]:
        raise SystemExit(f"{len(report['failed'])} asset groups failed validation")
    print(f"{len(report['passed'])} asset groups passed")


if __name__ == "__main__":
    main()
