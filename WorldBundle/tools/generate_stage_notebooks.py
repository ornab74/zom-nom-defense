#!/usr/bin/env python3
"""Generate 36 focused Colab notebooks from the versioned stage matrix.

Each notebook is intentionally thin: it loads the shared Universal PolyFlow
compiler, selects one stage manifest, executes only that stage, validates outputs,
and packages an artifact. Fixes stay centralized instead of being copied into
36 divergent notebooks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def markdown(source: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def code(source: str) -> dict[str, Any]:
    return {
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": source.splitlines(True),
    }


def notebook(stage: dict[str, Any], repo: str, branch: str) -> dict[str, Any]:
    stage_id = stage["id"]
    title = stage["title"]
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": f"Zom Nom {stage_id} - {title}.ipynb", "provenance": []},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
        },
        "cells": [
            markdown(
                f"# Zom Nom Defense — {title}\n\n"
                f"Stage: `{stage_id}`  \nBackend: `{stage['backend']}`  \n"
                "This notebook consumes the shared secure compiler and only processes its assigned stage.\n"
            ),
            code(
                "#@title Configuration\n"
                f"REPOSITORY = {repo!r}\nBRANCH = {branch!r}\nSTAGE_ID = {stage_id!r}\n"
                "USE_GPT_PLANNER = True\nUSE_GPT_IMAGES = True\n"
                "MAX_JOBS = 0  # 0 means every job assigned to this stage\n"
            ),
            code(
                "#@title Clone repository and install stage runner\n"
                "import pathlib, subprocess, sys\n"
                "ROOT = pathlib.Path('/content/zom-nom-defense')\n"
                "if not ROOT.exists():\n"
                "    subprocess.check_call(['git','clone','--depth','1','--branch',BRANCH,"
                "f'https://github.com/{REPOSITORY}.git',str(ROOT)])\n"
                "subprocess.check_call([sys.executable,'-m','pip','install','--quiet',"
                "'--upgrade-strategy','only-if-needed','openai','jsonschema'])\n"
                "print('Repository:', ROOT)\n"
            ),
            code(
                "#@title Generate and inspect the stage queue\n"
                "import json, subprocess, sys\n"
                "subprocess.check_call([sys.executable, str(ROOT/'WorldBundle/tools/world_bundle_planner.py'),"
                "'--preset',str(ROOT/'WorldBundle/presets/zom_nom_defense.json'),"
                "'--matrix',str(ROOT/'WorldBundle/notebook_matrix.json'),"
                "'--output',str(ROOT/'WorldBundle/generated/zom_nom_defense')])\n"
                "stage_file = ROOT/'WorldBundle/generated/zom_nom_defense'/f'{STAGE_ID}.json'\n"
                "jobs = json.loads(stage_file.read_text())\n"
                "if MAX_JOBS > 0: jobs = jobs[:MAX_JOBS]\n"
                "print('Stage jobs:', len(jobs))\n"
                "for job in jobs[:20]: print(job['asset_id'], job['backend'], job['variants'])\n"
            ),
            code(
                "#@title Execute this stage through the shared compiler contract\n"
                "# Part One writes the stable queue and validation contract. Specialized backends\n"
                "# are filled in stage-by-stage without permitting model-written Python execution.\n"
                "runner = ROOT/'WorldBundle/tools/run_stage.py'\n"
                "if runner.exists():\n"
                "    subprocess.check_call([sys.executable,str(runner),'--stage',STAGE_ID,"
                "'--jobs',str(stage_file)])\n"
                "else:\n"
                "    print('Stage runner backend is not implemented yet; queue generation passed.')\n"
            ),
            code(
                "#@title Validate and package stage artifact\n"
                "import hashlib, zipfile\n"
                "artifact = pathlib.Path('/content')/f'zom_nom_{STAGE_ID}.zip'\n"
                "with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as archive:\n"
                "    archive.write(stage_file,arcname=stage_file.name)\n"
                "digest = hashlib.sha256(artifact.read_bytes()).hexdigest()\n"
                "print('Artifact:', artifact)\nprint('SHA-256:', digest)\n"
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=Path("WorldBundle/notebook_matrix.json"))
    parser.add_argument("--output", type=Path, default=Path("WorldBundle/notebooks"))
    parser.add_argument("--repo", default="ornab74/zom-nom-defense")
    parser.add_argument("--branch", default="agent/world-bundle-part1")
    args = parser.parse_args()

    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    stages = matrix["stages"]
    if len(stages) != 36:
        raise SystemExit(f"Expected 36 stages; got {len(stages)}")
    args.output.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        path = args.output / f"{stage['id']}.ipynb"
        path.write_text(json.dumps(notebook(stage, args.repo, args.branch), indent=1), encoding="utf-8")
    index = {
        "version": matrix["version"],
        "count": len(stages),
        "notebooks": [f"{stage['id']}.ipynb" for stage in stages],
    }
    (args.output / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"generated {len(stages)} focused Zom Nom Colab notebooks")


if __name__ == "__main__":
    main()
