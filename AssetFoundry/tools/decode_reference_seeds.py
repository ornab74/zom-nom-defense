#!/usr/bin/env python3
"""Decode embedded reference-board seeds with strict integrity checks."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", default="AssetFoundry/reference_seed_pack.json")
    parser.add_argument("--output", default="AssetFoundry/references/generated")
    args = parser.parse_args()

    pack_path = Path(args.pack)
    output_root = Path(args.output)
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    files = data.get("files", {})
    if not files:
        raise SystemExit("reference seed pack contains no files")

    output_root.mkdir(parents=True, exist_ok=True)
    for name, spec in files.items():
        raw = base64.b64decode(spec["base64"], validate=True)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != spec["sha256"]:
            raise SystemExit(f"checksum mismatch for {name}: {digest}")
        if len(raw) != int(spec["bytes"]):
            raise SystemExit(f"byte-length mismatch for {name}: {len(raw)}")
        destination = output_root / name
        destination.write_bytes(raw)
        print(f"decoded {name} -> {destination}")


if __name__ == "__main__":
    main()
