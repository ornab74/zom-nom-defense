from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FOUNDRY_ROOT = REPO_ROOT / "AssetFoundry"
TOOLS = FOUNDRY_ROOT / "tools"
MANIFEST = FOUNDRY_ROOT / "asset_manifest.json"


class AssetFoundryTests(unittest.TestCase):
    def run_tool(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOLS / script), *arguments],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_repository_manifest_validates(self) -> None:
        result = self.run_tool("manifest_cli.py", "validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validated 16 assets", result.stdout)

    def test_matrix_contains_requested_asset(self) -> None:
        result = self.run_tool("manifest_cli.py", "matrix", "pool_house_shell")
        self.assertEqual(result.returncode, 0, result.stderr)
        line = next(line for line in result.stdout.splitlines() if line.startswith("matrix="))
        matrix = json.loads(line.removeprefix("matrix="))
        self.assertEqual(matrix["include"][0]["asset_id"], "pool_house_shell")
        self.assertEqual(matrix["include"][0]["category"], "architecture")
        self.assertEqual(matrix["include"][0]["priority"], "critical")

    def test_validator_accepts_complete_asset_and_hashes_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            incoming = root / "incoming"
            asset = incoming / "test_asset"
            asset.mkdir(parents=True)
            glb = asset / "test_asset.glb"
            glb.write_bytes(b"glTF-test-payload")
            (asset / "metadata.json").write_text('{"generator":"unit-test"}', encoding="utf-8")
            (asset / "test_asset_albedo.png").write_bytes(b"albedo")
            (asset / "test_asset_normal.png").write_bytes(b"normal")

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "defaults": {"unit_scale_meters": 1.0},
                        "assets": [
                            {
                                "id": "test_asset",
                                "category": "props",
                                "collision": "box",
                                "lods": 2,
                                "pbr": ["albedo", "normal"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "report.json"
            result = self.run_tool(
                "validate_assets.py",
                "--incoming",
                str(incoming),
                "--manifest",
                str(manifest),
                "--report",
                str(report_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["passed"]), 1)
            files = {entry["name"]: entry for entry in report["passed"][0]["files"]}
            self.assertEqual(files[glb.name]["sha256"], hashlib.sha256(glb.read_bytes()).hexdigest())

    def test_validator_reports_missing_texture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            incoming = root / "incoming"
            asset = incoming / "broken_asset"
            asset.mkdir(parents=True)
            (asset / "broken_asset.glb").write_bytes(b"glTF")
            (asset / "metadata.json").write_text("{}", encoding="utf-8")
            (asset / "broken_asset_albedo.png").write_bytes(b"albedo")

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "defaults": {"unit_scale_meters": 1.0},
                        "assets": [
                            {
                                "id": "broken_asset",
                                "category": "props",
                                "collision": "box",
                                "lods": 1,
                                "pbr": ["albedo", "normal"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            report_path = root / "report.json"
            result = self.run_tool(
                "validate_assets.py",
                "--incoming",
                str(incoming),
                "--manifest",
                str(manifest),
                "--report",
                str(report_path),
            )
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("missing texture broken_asset_normal.png", report["failed"][0]["failures"])

    def test_promoter_writes_godot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            incoming = root / "incoming"
            source = incoming / "test_asset"
            source.mkdir(parents=True)
            (source / "test_asset.glb").write_bytes(b"glTF")
            destination = root / "generated"
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "defaults": {"unit_scale_meters": 1.0},
                        "assets": [
                            {
                                "id": "test_asset",
                                "category": "environment",
                                "collision": "trimesh_static",
                                "lods": 3,
                                "pbr": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_tool(
                "promote_assets.py",
                "--incoming",
                str(incoming),
                "--destination",
                str(destination),
                "--manifest",
                str(manifest),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata_path = destination / "environment" / "test_asset" / "godot_import.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["asset_id"], "test_asset")
            self.assertEqual(metadata["collision"], "trimesh_static")
            self.assertEqual(metadata["lods"], 3)
            self.assertEqual(metadata["unit_scale_meters"], 1.0)
            self.assertTrue(metadata["generated"])


if __name__ == "__main__":
    unittest.main()
