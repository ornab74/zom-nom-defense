# Zom Nom Defense AssetFoundry

AssetFoundry is the manual-generation layer for producing hundreds of focused Zom Nom Defense assets in Google Colab, downloading each completed bundle, and later stitching uploaded outputs into the Godot project.

## Manual workflow

1. Generate the repository-owned asset catalog.
2. Generate the focused notebook suite.
3. Run notebooks individually in Colab.
4. Download each validated `<asset_id>_asset_bundle.zip`.
5. Extract completed bundles beneath `incoming/<asset_id>/` without renaming IDs.
6. Run the mapping surfacer.
7. Review the generated Godot patch before copying it into the project.

No Colab is allowed to push generated assets directly into the repository. This keeps API keys, model caches, unreviewed meshes, and failed generations outside Git history.

## Generate the expanded catalog

```bash
python AssetFoundry/tools/asset_catalog.py
```

The catalog expands architecture, pool structures, highway structures, foliage, survivors, zombies, vehicles, defenses, props, UI, and VFX into more than 200 concrete asset jobs. Every job records its exact Godot destination, specialized backend, prompt, scale, topology budget, textures, LODs, collision, rig, animation list, scenario tags, and validation profile.

## Generate hundreds of focused Colabs

```bash
python AssetFoundry/tools/generate_asset_notebooks.py \
  --output AssetFoundry/Notebooks \
  --repository ornab74/zom-nom-defense \
  --branch main
```

Notebooks are placed beneath:

```text
AssetFoundry/Notebooks/<category>/<family>/<asset_id>.ipynb
```

Each notebook is a thin launcher. Executable compiler logic remains in reviewed repository modules, so security fixes and backend improvements propagate across the full suite instead of leaving hundreds of divergent notebook copies.

## Universal compiler worker

`Universal_PolyFlow_Asset_Compiler.For.Google.Colab.ipynb` remains the advanced universal worker. AssetFoundry mode selects an immutable catalog contract and writes:

- `game_asset.glb`
- PBR textures
- render and thumbnail previews
- optional rig and animation files
- collision and LOD metadata
- `asset_contract.json`
- `asset_mapping_surface.json`
- `validation.json`
- checksums and provenance
- a manual download ZIP

The tree path remains the most specialized backend. Other backend families are staged independently so modular architecture, characters, vehicles, defenses, props, UI, VFX, and maps can advance without pretending one primitive assembler solves every topology class.

## PolyFlow-compatible topology contract

The foundry uses a continuous per-vertex state contract:

```text
z_i = [p_i, n_i, e_i]
```

where position, normal, and topology embedding are refined together. Candidate adjacency is decoded from spacetime distance:

```text
d_st(e_i,e_j) = ||e_i^s-e_j^s||² - ||e_i^t-e_j^t||²
```

and is then subjected to deterministic manifold, face-winding, component, self-intersection, UV, scale, LOD, collision, rig, animation, and Godot-import checks. The repository implements compatible contracts and deterministic refiners; it does not claim to contain unreleased research checkpoints.

The design is informed by PolyFlow's continuous topology embedding, joint position/normal/topology state, parallel flow matching, and explicit vertex-count control.

## Mapping surfacer

After manually uploading completed bundles:

```bash
python AssetFoundry/tools/mapping_surfer.py \
  --incoming incoming \
  --output AssetFoundry/output/godot_patch \
  --zip AssetFoundry/output/zom_nom_asset_patch.zip
```

The mapping surfacer never trusts a bundle-provided destination. It resolves placement from `asset_catalog.py`, validates the asset ID, rejects traversal and symlinks, enforces extension and byte limits, hashes every installed file, writes GLB wrapper scenes and mapping metadata, and builds:

- `Assets/Generated/<category>/<asset_id>/...`
- `Common/Systems/asset_foundry/asset_foundry_registry.json`
- `Common/Systems/asset_foundry/asset_foundry_registry.gd`
- `ASSET_FOUNDRY_INSTALL.json`
- a reviewable patch ZIP

Missing bundles remain listed as missing. Invalid bundles remain quarantined with an explicit reason.

## Security

- model-written Python is never executed
- bundle destinations are advisory and ignored during installation
- only repository-catalog IDs can be installed
- remote asset URLs are disabled
- paths must resolve beneath the bundle root
- symlinks are rejected
- approved file extensions and byte limits are enforced
- generated files are hashed
- provenance records model, prompt, seed, software, license, and validation state
- generated or compatible CC0 inputs only

## Relationship to WorldBundle

`WorldBundle` plans scenario-level generation and integration across 36 stages. `AssetFoundry` expands those stages into hundreds of concrete manual generation jobs. Completed AssetFoundry bundles are mapped into Godot first; WorldBundle can then assemble map, scenario, navigation, and gameplay-level patches from the validated registry.
