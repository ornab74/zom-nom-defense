from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "AssetFoundry/tools"
sys.path.insert(0, str(TOOLS))

import asset_catalog
import generate_asset_notebooks
import manual_colab_runner
import mapping_surfer


class ExpandedCatalogTests(unittest.TestCase):
    def test_catalog_has_hundreds_of_unique_jobs(self):
        jobs = asset_catalog.build_catalog()
        self.assertGreaterEqual(len(jobs), 200)
        self.assertEqual(len(jobs), len({job.asset_id for job in jobs}))
        ids = {job.asset_id for job in jobs}
        for expected in (
            "pool_house_shell_a",
            "live_oak_mature",
            "climber_zombie_male_01",
            "survivor_muscle_car_base",
            "scrap_turret",
            "build_wheel_icons",
        ):
            self.assertIn(expected, ids)

    def test_every_job_has_safe_project_mapping(self):
        for job in asset_catalog.build_catalog():
            self.assertTrue(job.godot_destination.startswith("Assets/Generated/"))
            self.assertNotIn("..", job.godot_destination)
            self.assertEqual(1.0, job.lod_ratios[0])

    def test_notebook_count_matches_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            count = generate_asset_notebooks.write_notebooks(
                root, "ornab74/zom-nom-defense", "test-branch"
            )
            notebooks = list(root.rglob("*.ipynb"))
            self.assertEqual(len(asset_catalog.build_catalog()), count)
            self.assertEqual(count, len(notebooks))
            payload = json.loads(notebooks[0].read_text(encoding="utf-8"))
            self.assertEqual(4, payload["nbformat"])


class MappingSurfacerTests(unittest.TestCase):
    def test_known_asset_is_mapped_and_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "incoming/live_oak_mature"
            bundle.mkdir(parents=True)
            (bundle / "game_asset.glb").write_bytes(b"glTF-test")
            (bundle / "bark_albedo.png").write_bytes(b"png-test")
            (bundle / "metadata.json").write_text('{"license":"original"}')
            result = mapping_surfer.stitch(root / "incoming", root / "patch")
            entry = result["registry"]["assets"]["live_oak_mature"]
            self.assertEqual("foliage", entry["category"])
            self.assertTrue(entry["scene"].endswith("live_oak_mature.tscn"))
            self.assertTrue(all(file["sha256"] for file in entry["files"]))

    def test_unknown_asset_is_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "incoming/not_in_catalog"
            bundle.mkdir(parents=True)
            (bundle / "game_asset.glb").write_bytes(b"glTF-test")
            result = mapping_surfer.stitch(root / "incoming", root / "patch")
            self.assertNotIn("not_in_catalog", result["registry"]["assets"])

    def test_runner_rejects_destination_traversal(self):
        contract = dict(asset_catalog.build_catalog()[0].__dict__)
        contract["godot_destination"] = "Assets/Generated/../../escape"
        with self.assertRaises(ValueError):
            manual_colab_runner.validate_contract(contract)


if __name__ == "__main__":
    unittest.main()
