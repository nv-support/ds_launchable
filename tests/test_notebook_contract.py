"""Regression contracts for notebook source, prompt availability, and served paths."""

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import nbformat


BREV_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BREV_ROOT.parents[1]
SCRIPTS = BREV_ROOT / "scripts"
os.environ.setdefault("OUTPUT_ROOT", tempfile.mkdtemp(prefix="brev-tests-output-"))
sys.path.insert(0, str(SCRIPTS))
lab = importlib.import_module("ds_agent_lab")
build_notebook = importlib.import_module("build_notebook")


class NotebookSourceTests(unittest.TestCase):
    def test_checked_in_notebook_matches_build_source(self):
        notebook = nbformat.read(BREV_ROOT / "deepstream_code_agent_launchable.ipynb", as_version=4)
        expected = build_notebook.build_cells()

        self.assertEqual(len(notebook.cells), len(expected))
        for cell, (kind, source) in zip(notebook.cells, expected):
            self.assertEqual(cell.cell_type, "markdown" if kind == "md" else "code")
            self.assertEqual(cell.source, source.rstrip("\n"))

    def test_prompt_callbacks_invalidate_and_lock_cross_step_controls(self):
        source = build_notebook.CODE_STEP3 + build_notebook.CODE_STEP4

        self.assertIn("lab.set_selection(lab.AGENT, prompt_dd.value)", source)
        self.assertIn('lab.set_selection(lab.AGENT, change["new"])', source)
        self.assertIn('lab.state["generated"] = False', source)
        self.assertIn('prompt_tx.observe(_on_prompt_edit, names="value")', source)
        self.assertIn('globals().get("run_btn")', source)
        self.assertIn('globals().get("gen_btn")', source)
        self.assertEqual(source.count("controls=tuple("), 2)

    def test_default_prompt_has_public_subset_fallback(self):
        self.assertIn(
            '"video_infer_app" if "video_infer_app" in lab.MENU_PROMPT_IDS',
            build_notebook.CODE_STEP3,
        )


class PromptCatalogTests(unittest.TestCase):
    def test_full_checkout_catalog_matches_present_markdown_prompts(self):
        prompt_files = {path.stem for path in (REPO_ROOT / "example_prompts").glob("*.md")}
        self.assertEqual(set(lab.PROMPT_IDS), prompt_files)

    def test_public_subset_hides_missing_prompts_and_degrades_partial_sequence(self):
        with tempfile.TemporaryDirectory(prefix="brev-catalog-") as tmp:
            root = Path(tmp)
            scripts = root / "deploy/brev/scripts"
            prompts = root / "example_prompts"
            scripts.mkdir(parents=True)
            prompts.mkdir()
            shutil.copy2(SCRIPTS / "ds_lab_config.py", scripts)
            for name in ("rtvi_vlm_core_app.md", "video_infer_app.md"):
                shutil.copy2(REPO_ROOT / "example_prompts" / name, prompts)
            code = (
                "import json,sys; "
                f"sys.path.insert(0, {str(scripts)!r}); "
                "import ds_lab_config as c; "
                "print(json.dumps([c.PROMPT_IDS,c.MENU_PROMPT_IDS,c.PROMPT_SEQUENCES]))"
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                text=True,
                capture_output=True,
                check=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            prompt_ids, menu_ids, sequences = json.loads(result.stdout)

        self.assertEqual(prompt_ids, ["rtvi_vlm_core_app", "video_infer_app"])
        self.assertEqual(menu_ids, ["rtvi_vlm_core_app", "video_infer_app"])
        self.assertEqual(sequences, {})


class DeploymentScriptTests(unittest.TestCase):
    def test_brev_post_setup_replaces_legacy_bootstrap(self):
        post_setup = SCRIPTS / "brev_post_setup.sh"

        self.assertTrue(post_setup.is_file())
        self.assertFalse((SCRIPTS / "bootstrap_host_ubuntu2404.sh").exists())
        self.assertTrue(post_setup.read_text().startswith("#!/bin/bash\n"))
        self.assertIn("poppler-utils", post_setup.read_text())
        subprocess.run(["bash", "-n", str(post_setup)], check=True)

    def test_vlm_launcher_is_present_and_referenced_by_runtime(self):
        launcher = SCRIPTS / "serve_vlm.sh"
        runtime_source = (SCRIPTS / "ds_agent_lab.py").read_text()

        self.assertTrue(launcher.is_file())
        self.assertIn('"deploy/brev/scripts/serve_vlm.sh"', runtime_source)
        subprocess.run(["bash", "-n", str(launcher)], check=True)


class JupyterPathTests(unittest.TestCase):
    def test_repo_root_server_url(self):
        with tempfile.TemporaryDirectory(prefix="brev-repo-root-") as tmp:
            repo = Path(tmp) / "deepstream"
            artifact = repo / "deploy/brev/outputs/workspace/app/out.mp4"
            with mock.patch(
                "jupyter_server.serverapp.list_running_servers",
                return_value=[{"root_dir": str(repo)}],
            ):
                url = lab._jupyter_file_url(artifact)
        self.assertEqual(url, "/files/deploy/brev/outputs/workspace/app/out.mp4")

    def test_home_root_server_url_includes_checkout_directory(self):
        with tempfile.TemporaryDirectory(prefix="brev-home-root-") as tmp:
            home = Path(tmp)
            artifact = home / "deepstream/deploy/brev/outputs/workspace/app/out.mp4"
            with mock.patch(
                "jupyter_server.serverapp.list_running_servers",
                return_value=[{"root_dir": str(home)}],
            ):
                url = lab._jupyter_file_url(artifact)
        self.assertEqual(url, "/files/deepstream/deploy/brev/outputs/workspace/app/out.mp4")

    def test_file_url_escapes_path_and_can_download(self):
        with tempfile.TemporaryDirectory(prefix="brev-url-root-") as tmp:
            root = Path(tmp)
            artifact = root / "result files/report #1.pdf"
            with mock.patch(
                "jupyter_server.serverapp.list_running_servers",
                return_value=[{"root_dir": str(root)}],
            ):
                url = lab._jupyter_file_url(artifact, download=True)
        self.assertEqual(url, "/files/result%20files/report%20%231.pdf?download=1")


if __name__ == "__main__":
    unittest.main()
