# Zom Nom Asset Foundry

This directory defines a reproducible GPU asset pipeline for the game's pool house, vehicles, foliage, zombies, defenses, props, textures, collisions, and LODs.

## Architecture

1. `asset_manifest.json` is the source of truth.
2. GitHub Actions validates requests and publishes a generation bundle.
3. A Colab or Colab Enterprise GPU notebook consumes the bundle.
4. The notebook generates one isolated asset directory per manifest entry.
5. A topology/refinement stage repairs geometry, creates UVs, bakes PBR maps, and creates LODs.
6. Results are uploaded to a versioned Cloud Storage job folder.
7. The `Asset Foundry` workflow imports a specified completed job.
8. Blender/trimesh validators reject missing maps, broken packaging, oversized outputs, and metadata failures.
9. Validated assets are promoted under `Assets/Generated/<category>/<asset_id>/`.

GitHub-hosted runners are intentionally not treated as the main generation GPUs. GitHub orchestrates, reviews, hashes, and promotes; Colab or Vertex supplies accelerator compute.

## Flow matching and topology refinement

The production design separates generation from repair:

- **Global proposal:** an image-conditioned 3D model proposes geometry and appearance.
- **Vertex flow:** vertices are optimized against silhouette, normal consistency, edge-length, Laplacian, and surface-distance objectives.
- **Topology repair:** non-manifold edges, duplicate vertices, self intersections, floating components, and inverted normals are repaired or rejected.
- **Retopology:** hard-surface and organic presets use different decimation and quad-remesh targets.
- **Game packaging:** UV unwrap, PBR bake, LOD generation, collision generation, origin normalization, metric scaling, and GLB export.

The repository begins with a practical deterministic repair pipeline. A trainable DiT/GNN topology refiner can later replace the proposal/refinement module without changing the manifest or promotion contract.

## Colab operation

Open `colab/asset_foundry_colab.ipynb`, then set:

- repository and branch
- requested asset IDs
- Cloud Storage bucket
- job ID
- generation quality

The notebook writes to:

```text
gs://<bucket>/jobs/<job-id>/output/<asset-id>/
```

Each asset folder must contain:

- `<asset-id>.glb`
- `<asset-id>_albedo.png`
- every required PBR map listed in the manifest
- `metadata.json`
- optional previews and source meshes

Then run the GitHub workflow with the same job ID.

## Security

Use GitHub OpenID Connect with Google Workload Identity Federation. Do not store long-lived Google service-account JSON keys in repository secrets. Limit the service account to the asset bucket and required job execution APIs.

## Licensing

Only generated assets and explicitly compatible CC0 inputs may enter `Assets/Generated`. Every generated metadata file should record model, prompt, seeds, source conditioning images, licenses, software versions, and checksums.
