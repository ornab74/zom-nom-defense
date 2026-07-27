from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load_module("world_bundle_planner", ROOT / "WorldBundle/tools/world_bundle_planner.py")
stitcher = load_module("godot_stitcher", ROOT / "WorldBundle/tools/godot_stitcher.py")
notebooks = load_module("generate_stage_notebooks", ROOT / "WorldBundle/tools/generate_stage_notebooks.py")


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.preset = planner.load_json(ROOT / "WorldBundle/presets/zom_nom_defense.json")
        self.matrix = planner.load_json(ROOT / "WorldBundle/notebook_matrix.json")
        self.policy = planner.Policy()

    def test_matrix_has_exactly_36_unique_stages(self):
        planner.validate_inputs(self.preset, self.matrix, self.policy)
        ids = [stage["id"] for stage in self.matrix["stages"]]
        self.assertEqual(36, len(ids))
        self.assertEqual(36, len(set(ids)))

    def test_catalog_is_zom_nom_specific_and_bounded(self):
        jobs = planner.build_jobs(self.preset, self.matrix, self.policy)
        self.assertGreater(len(jobs), 100)
        self.assertLessEqual(len(jobs), self.policy.max_assets)
        names = {job.display_name for job in jobs}
        self.assertIn("two-story pool house shell", names)
        self.assertIn("climber zombie", names)
        self.assertIn("survivor muscle car base", names)
        self.assertIn("scrap automated turret", names)
        self.assertNotIn("expedition rifle", names)

    def test_jobs_have_safe_ids_and_destinations(self):
        jobs = planner.build_jobs(self.preset, self.matrix, self.policy)
        for job in jobs:
            self.assertRegex(job.asset_id, r"^[a-z0-9_]{1,80}$")
            self.assertTrue(job.godot_destination.startswith("Assets/Generated/"))
            self.assertNotIn("..", job.godot_destination)
            self.assertGreaterEqual(job.variants, 1)
            self.assertLessEqual(job.variants, self.policy.max_variants)

    def test_planner_writes_jsonl_and_stage_files(self):
        jobs = planner.build_jobs(self.preset, self.matrix, self.policy)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            planner.write_outputs(jobs, self.preset, self.matrix, output)
            lines = (output / "asset_jobs.jsonl").read_text().splitlines()
            self.assertEqual(len(jobs), len(lines))
            self.assertTrue((output / "10_pool_house_exterior.json").exists())
            summary = json.loads((output / "bundle_summary.json").read_text())
            self.assertEqual(len(jobs), summary["asset_count"])
            self.assertFalse(summary["security"]["execute_model_code"])


class NotebookTests(unittest.TestCase):
    def test_generator_emits_valid_notebook_shape_for_every_stage(self):
        matrix = json.loads((ROOT / "WorldBundle/notebook_matrix.json").read_text())
        for stage in matrix["stages"]:
            payload = notebooks.notebook(stage, "ornab74/zom-nom-defense", "agent/world-bundle-part1")
            self.assertEqual(4, payload["nbformat"])
            self.assertGreaterEqual(len(payload["cells"]), 5)
            source = "\n".join("".join(cell.get("source", [])) for cell in payload["cells"])
            self.assertIn(stage["id"], source)
            self.assertIn("execute", source.lower())


class StitcherTests(unittest.TestCase):
    def test_rejects_path_traversal_asset_id(self):
        with self.assertRaises(ValueError):
            stitcher.validate_asset_id("../escape")

    def test_stitches_fake_glb_into_registry_and_scene(self):
        job = {
            "asset_id": "climber_zombie",
            "display_name": "Climber Zombie",
            "category": "character",
            "backend": "character_pipeline",
            "variants": 4,
            "validation_profile": "character_pipeline_v1",
            "scenario_tags": ["pool_house_siege", "shared"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming"
            source = incoming / "climber_zombie"
            source.mkdir(parents=True)
            (source / "game_asset.glb").write_bytes(b"glTF-fake-test")
            (source / "metadata.json").write_text('{"license":"original"}')
            patch = root / "patch"
            result = stitcher.stitch([job], incoming, patch)
            entry = result["registry"]["assets"]["climber_zombie"]
            self.assertTrue(entry["scene"].endswith("climber_zombie.tscn"))
            self.assertTrue((patch / "Assets/Generated/character/climber_zombie/climber_zombie.tscn").exists())
            self.assertTrue((patch / "Common/Systems/world_bundle/world_bundle_registry.gd").exists())
            self.assertEqual(1, result["install"]["generated_asset_count"])

    def test_missing_asset_is_reported_not_invented(self):
        job = {
            "asset_id": "missing_asset",
            "display_name": "Missing Asset",
            "category": "prop",
            "backend": "prop_family",
            "variants": 1,
            "validation_profile": "prop_family_v1",
            "scenario_tags": ["shared"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = stitcher.stitch([job], root / "incoming", root / "patch")
            self.assertIn("missing_asset", result["registry"]["missing"])
            self.assertEqual(0, result["install"]["generated_asset_count"])


if __name__ == "__main__":
    unittest.main()
