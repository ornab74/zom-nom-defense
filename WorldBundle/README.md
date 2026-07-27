# Zom Nom Defense World Bundle — Part One

This directory is the staged orchestration layer for generating and integrating the complete Zom Nom Defense asset world.

## What Part One provides

- A Zom Nom-specific world preset with the two current scenarios: Pool House Siege and Highway Last Stand.
- A 36-stage notebook matrix covering game design, maps, materials, architecture, foliage, props, survivors, zombies, vehicles, defenses, animation, VFX, audio, UI, AI, Godot integration, and validation.
- A deterministic planner that expands the preset into bounded asset jobs.
- A generator that emits one focused Colab notebook per stage.
- A secure Godot stitcher that copies only approved file types, hashes files, writes wrapper scenes, builds a runtime registry, creates scenario resources, and packages a reviewable patch ZIP.
- Unit tests and GitHub Actions validation.

## Security model

The orchestration layer preserves the same planner-to-schema-to-trusted-compiler architecture as the Universal PolyFlow notebook.

- Model-written Python is never executed.
- Remote URLs and third-party asset extraction are disabled.
- Identifiers are restricted to safe lowercase slugs.
- Asset counts, variants, prompt length, dependencies, and file sizes are bounded.
- The stitcher rejects path traversal and ignores unapproved file extensions.
- Generated files are hashed and included in the registry.
- Missing assets are reported rather than fabricated.

## Generate the staged queue

```bash
python WorldBundle/tools/world_bundle_planner.py \
  --preset WorldBundle/presets/zom_nom_defense.json \
  --matrix WorldBundle/notebook_matrix.json \
  --output WorldBundle/generated/zom_nom_defense
```

The output contains `asset_jobs.jsonl`, one JSON file per stage, and a bundle summary.

## Generate the 36 Colab notebooks

```bash
python WorldBundle/tools/generate_stage_notebooks.py \
  --matrix WorldBundle/notebook_matrix.json \
  --output WorldBundle/notebooks
```

The generated notebooks are intentionally thin and share the repository's compiler contract. They do not duplicate the Universal PolyFlow compiler.

## Stitch completed assets into Godot

Each completed asset folder should use its planned `asset_id` and contain a validated `game_asset.glb` plus optional textures, audio, and metadata.

```text
incoming/
  climber_zombie/
    game_asset.glb
    metadata.json
    textures/
  two_story_pool_house_shell/
    game_asset.glb
    metadata.json
```

Run:

```bash
python WorldBundle/tools/godot_stitcher.py \
  --jobs WorldBundle/generated/zom_nom_defense/asset_jobs.jsonl \
  --incoming incoming \
  --output WorldBundle/output/godot_patch \
  --zip WorldBundle/output/zom_nom_godot_patch.zip
```

The patch includes generated wrapper scenes, an asset registry, an autoload-compatible registry script, scenario resources, checksums, and installation instructions.

## What is deliberately not claimed yet

Part One does not make every backend production-ready. Character topology, advanced hard-surface vehicles, modular architecture, animation synthesis, navigation validation, and closed-loop visual critique remain specialized backend stages. The matrix and contracts now exist so those stages can be implemented and tested independently without pretending primitive blockouts are final art.

## Next parts

1. Specialized modular architecture compiler for the pool house and highway structures.
2. Character and zombie topology/rigging pipeline.
3. Vehicle chassis, damage-state, and animation pipeline.
4. Defense-device family compiler.
5. Map graph and procedural dressing compiler.
6. Render/mesh critic loop with revision proposals.
7. Godot headless import and gameplay validation.
8. CustomTkinter desktop orchestrator that runs stages, resumes jobs, reviews outputs, and launches Godot.
