from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_catalog import AssetJob, build_catalog


def source(lines: str) -> list[str]:
    return [line + "\n" for line in lines.strip("\n").splitlines()]


def notebook(job: AssetJob, repository: str, branch: str) -> dict:
    contract_json = json.dumps(job.__dict__, separators=(",", ":"))
    contract_literal = repr(contract_json)
    title = f"# Zom Nom AssetFoundry — {job.display_name}"
    setup = f'''#@title Clone compiler and select asset contract
REPOSITORY = {repository!r}
BRANCH = {branch!r}
ASSET_ID = {job.asset_id!r}
!rm -rf /content/zom-nom-defense
!git clone --depth 1 --branch "$BRANCH" "https://github.com/$REPOSITORY.git" /content/zom-nom-defense
%cd /content/zom-nom-defense
'''
    contract_cell = f'''#@title Immutable repository-owned generation contract
import json
from pathlib import Path
ASSET_CONTRACT = json.loads({contract_literal})
OUTPUT_ROOT = Path('/content/asset_output') / ASSET_CONTRACT['asset_id']
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
(OUTPUT_ROOT / 'asset_contract.json').write_text(
    json.dumps(ASSET_CONTRACT, indent=2), encoding='utf-8'
)
print(json.dumps(ASSET_CONTRACT, indent=2))
'''
    execution = '''#@title Run the Universal PolyFlow compiler in manual mode
# This thin notebook delegates executable logic to the reviewed repository compiler.
# Model responses remain data-only and are validated before trusted code consumes them.
%run AssetFoundry/tools/manual_colab_runner.py
result = run_asset_contract(ASSET_CONTRACT, OUTPUT_ROOT)
print(json.dumps(result, indent=2))
'''
    validation = '''#@title Validate mesh, materials, rig, LODs, collision, and Godot mapping
validation = validate_asset_bundle(ASSET_CONTRACT, OUTPUT_ROOT)
print(json.dumps(validation, indent=2))
if not validation['passed']:
    raise RuntimeError('Asset bundle validation failed')
'''
    packaging = '''#@title Package for manual download and later mapping
from google.colab import files
bundle = package_asset_bundle(ASSET_CONTRACT, OUTPUT_ROOT)
print('Godot destination:', ASSET_CONTRACT['godot_destination'])
print('Download and keep this asset ID unchanged:', ASSET_CONTRACT['asset_id'])
files.download(str(bundle))
'''
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": f"{job.asset_id}.ipynb", "provenance": []},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
        },
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": source(title + "\n\n" + job.prompt)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source(setup)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source(contract_cell)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source(execution)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source(validation)},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source(packaging)},
        ],
    }


def write_notebooks(output: Path, repository: str, branch: str) -> int:
    jobs = build_catalog()
    output.mkdir(parents=True, exist_ok=True)
    index = []
    for job in jobs:
        family_dir = output / job.category / job.family
        family_dir.mkdir(parents=True, exist_ok=True)
        path = family_dir / f"{job.asset_id}.ipynb"
        path.write_text(json.dumps(notebook(job, repository, branch), indent=1), encoding="utf-8")
        index.append({
            "asset_id": job.asset_id,
            "notebook": str(path.relative_to(output)),
            "godot_destination": job.godot_destination,
            "backend": job.backend,
        })
    (output / "notebook_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return len(jobs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("AssetFoundry/Notebooks"))
    parser.add_argument("--repository", default="ornab74/zom-nom-defense")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()
    count = write_notebooks(args.output, args.repository, args.branch)
    print(f"Generated {count} focused Colab notebooks in {args.output}")


if __name__ == "__main__":
    main()
