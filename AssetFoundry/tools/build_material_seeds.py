#!/usr/bin/env python3
"""Build deterministic seamless PBR texture seeds without external packages.

These are art-direction and fallback materials. Production generators can replace
individual maps later while preserving names and Godot material descriptors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import struct
import zlib
from pathlib import Path


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def write_png(path: Path, width: int, height: int, channels: int, pixels: bytes) -> None:
    color_type = {1: 0, 3: 2, 4: 6}[channels]
    stride = width * channels
    raw = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    path.write_bytes(data)


def hash01(x: int, y: int, seed: int) -> float:
    n = x * 374761393 + y * 668265263 + seed * 1442695040888963407
    n = (n ^ (n >> 13)) * 1274126177
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def smooth_noise(x: float, y: float, seed: int, period: int) -> float:
    x %= period
    y %= period
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = (x0 + 1) % period, (y0 + 1) % period
    tx, ty = x - x0, y - y0
    tx = tx * tx * (3.0 - 2.0 * tx)
    ty = ty * ty * (3.0 - 2.0 * ty)
    a = hash01(x0, y0, seed)
    b = hash01(x1, y0, seed)
    c = hash01(x0, y1, seed)
    d = hash01(x1, y1, seed)
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def fbm(x: float, y: float, seed: int, period: int) -> float:
    total = 0.0
    weight = 0.5
    scale = 1.0
    norm = 0.0
    for octave in range(5):
        total += smooth_noise(x * scale, y * scale, seed + octave * 101, max(2, int(period * scale))) * weight
        norm += weight
        weight *= 0.5
        scale *= 2.0
    return total / norm


def material_height(spec: dict, x: int, y: int, size: int, seed: int) -> float:
    scale = float(spec.get("scale", 8.0))
    u = x / size
    v = y / size
    h = fbm(u * scale, v * scale, seed, max(4, int(scale)))

    if spec.get("grain"):
        h = 0.72 * h + 0.28 * (0.5 + 0.5 * math.sin((u * scale * 4.0 + fbm(u * 2, v * 2, seed + 13, 4)) * math.tau))
    if spec.get("weave"):
        weave = (math.sin(u * scale * 6 * math.tau) + math.sin(v * scale * 6 * math.tau)) * 0.5
        h = h * 0.75 + (weave * 0.5 + 0.5) * 0.25
    if spec.get("grout"):
        cells = max(2, int(scale))
        gx = min((u * cells) % 1.0, 1.0 - ((u * cells) % 1.0))
        gy = min((v * cells) % 1.0, 1.0 - ((v * cells) % 1.0))
        grout = min(gx, gy)
        h *= 0.45 if grout < float(spec["grout"]) else 1.0
    if spec.get("cracks"):
        line = abs(math.sin((u * 7.0 + fbm(u * 3, v * 3, seed + 29, 8)) * math.tau))
        if line < float(spec["cracks"]) * 0.12:
            h *= 0.25
    return max(0.0, min(1.0, h))


def lerp_color(a: list[int], b: list[int], t: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(a[i] * (1.0 - t) + b[i] * t))) for i in range(3))


def build_material(spec: dict, output_root: Path, size: int) -> dict:
    seed = int(hashlib.sha256(spec["id"].encode()).hexdigest()[:8], 16)
    heights = [[material_height(spec, x, y, size, seed) for x in range(size)] for y in range(size)]
    albedo = bytearray()
    normal = bytearray()
    roughness = bytearray()
    ao = bytearray()
    metallic = bytearray()
    base = spec["base_color"]
    accent = spec["accent_color"]
    stain_strength = float(spec.get("stains", 0.0))

    for y in range(size):
        for x in range(size):
            h = heights[y][x]
            stain = fbm(x / size * 5.0, y / size * 5.0, seed + 777, 5)
            color_mix = max(0.0, min(1.0, h * 0.55 + stain * stain_strength))
            albedo.extend(lerp_color(base, accent, color_mix))

            left = heights[y][(x - 1) % size]
            right = heights[y][(x + 1) % size]
            down = heights[(y - 1) % size][x]
            up = heights[(y + 1) % size][x]
            nx, ny, nz = left - right, down - up, 0.45
            length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            normal.extend((round((nx / length * 0.5 + 0.5) * 255), round((ny / length * 0.5 + 0.5) * 255), round((nz / length * 0.5 + 0.5) * 255)))

            rough = max(0.0, min(1.0, float(spec["roughness"]) + (0.5 - h) * 0.18))
            roughness.append(round(rough * 255))
            ao.append(round((0.62 + h * 0.38) * 255))
            metallic.append(round(float(spec["metallic"]) * 255))

    folder = output_root / spec["family"] / spec["id"]
    folder.mkdir(parents=True, exist_ok=True)
    paths = {
        "albedo": folder / f"{spec['id']}_albedo.png",
        "normal": folder / f"{spec['id']}_normal.png",
        "roughness": folder / f"{spec['id']}_roughness.png",
        "ao": folder / f"{spec['id']}_ao.png",
        "metallic": folder / f"{spec['id']}_metallic.png",
    }
    write_png(paths["albedo"], size, size, 3, bytes(albedo))
    write_png(paths["normal"], size, size, 3, bytes(normal))
    write_png(paths["roughness"], size, size, 1, bytes(roughness))
    write_png(paths["ao"], size, size, 1, bytes(ao))
    write_png(paths["metallic"], size, size, 1, bytes(metallic))

    descriptor = {
        "asset_id": spec["id"],
        "family": spec["family"],
        "shader": "standard_material_3d",
        "uv_scale": [1.0, 1.0],
        "textures": {key: path.name for key, path in paths.items()},
        "roughness": spec["roughness"],
        "metallic": spec["metallic"],
        "generated_seed": True,
        "checksums": {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()},
    }
    (folder / "material.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    return descriptor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="AssetFoundry/materials/material_seed_manifest.json")
    parser.add_argument("--output", default="Assets/Generated/Materials")
    parser.add_argument("--resolution", type=int)
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    size = args.resolution or int(manifest.get("resolution", 256))
    if size < 32 or size > 2048 or size & (size - 1):
        raise SystemExit("resolution must be a power of two from 32 to 2048")

    output = Path(args.output)
    descriptors = [build_material(spec, output, size) for spec in manifest["materials"]]
    index = {"version": 1, "resolution": size, "materials": descriptors}
    output.mkdir(parents=True, exist_ok=True)
    (output / "material_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"built {len(descriptors)} seamless PBR seed materials at {size}x{size}")


if __name__ == "__main__":
    main()
