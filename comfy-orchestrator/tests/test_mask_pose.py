"""Offline tests for one-click I2I, paint masks and SDXL pose workflows."""

from __future__ import annotations

import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, history, lmstudio, mask_editor


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.cfg = core.load_config(ROOT / "config.example.json")
        self.entries = self.cfg["workflows"]

    def test_registered_workflows_are_api_json_and_bind_all_inputs(self):
        for key in (
            "wai_t2i_basic", "wai_i2i_basic", "wai_inpaint_basic",
            "wai_pose_skeleton", "wai_pose_detect",
        ):
            entry = self.entries[key]
            graph = core.load_workflow(ROOT / entry["file"], entry["bindings"])
            self.assertTrue(graph)
            self.assertIn("positive_prompt", entry["bindings"])

    def test_inpainting_graph_protects_original_pixels(self):
        entry = self.entries["wai_inpaint_basic"]
        w = core.load_workflow(ROOT / entry["file"], entry["bindings"])
        self.assertEqual(w["19"]["class_type"], "LoadImageMask")
        self.assertEqual(w["19"]["inputs"]["channel"], "red")
        self.assertEqual(w["18"]["class_type"], "VAEEncodeForInpaint")
        self.assertEqual(w["18"]["inputs"]["mask"], ["19", 0])
        self.assertEqual(w["11"]["inputs"]["latent_image"], ["18", 0])
        self.assertEqual(w["20"]["class_type"], "ImageCompositeMasked")
        self.assertEqual(w["20"]["inputs"]["destination"], ["16", 0])
        self.assertEqual(w["20"]["inputs"]["mask"], ["19", 0])
        self.assertEqual(w["13"]["inputs"]["images"], ["20", 0])
        rendered = core.render_workflow(
            w, entry["bindings"],
            {"positive_prompt": "beautiful fingers", "denoise": 0.7, "seed": 99},
            "source_uploaded.png", "mask_uploaded.png",
        )
        self.assertEqual(rendered["16"]["inputs"]["image"], "source_uploaded.png")
        self.assertEqual(rendered["19"]["inputs"]["image"], "mask_uploaded.png")
        self.assertEqual(rendered["11"]["inputs"]["seed"], 99)
        self.assertEqual(w["19"]["inputs"]["image"], "mask.png")  # immutable template

    def test_pose_workflows_use_only_openpose_control_conditioning(self):
        for name, uses_preprocess in (("wai_pose_skeleton", False), ("wai_pose_detect", True)):
            entry = self.entries[name]
            w = core.load_workflow(ROOT / entry["file"], entry["bindings"])
            self.assertEqual(w["22"]["class_type"], "ControlNetLoader")
            self.assertEqual(w["23"]["class_type"], "ControlNetApplyAdvanced")
            self.assertEqual(w["11"]["inputs"]["positive"], ["23", 0])
            self.assertEqual(w["11"]["inputs"]["negative"], ["23", 1])
            self.assertEqual(w["23"]["inputs"]["image"], ["24", 0] if uses_preprocess else ["21", 0])
            if uses_preprocess:
                self.assertEqual(w["24"]["class_type"], "DWPreprocessor")
                self.assertEqual(w["24"]["inputs"]["image"], ["21", 0])
            render = core.render_workflow(
                w, entry["bindings"],
                {"positive_prompt": "girl", "control_strength": 0.7, "seed": 5},
                None, pose_name="pose_uploaded.png",
            )
            self.assertEqual(render["21"]["inputs"]["image"], "pose_uploaded.png")
            self.assertEqual(render["23"]["inputs"]["strength"], 0.7)

    def test_auto_chooses_plain_t2i_without_image_even_when_previous_mode_was_i2i(self):
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "wai_i2i_basic", False),
            "wai_t2i_basic",
        )
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "wai_inpaint_basic", False),
            "wai_t2i_basic",
        )
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "wai_pose_detect", False),
            "wai_t2i_basic",
        )
        self.assertEqual(gui.resolve_generation_workflow(self.cfg, "自動", True), "wai_i2i_basic")
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "wai_i2i_basic", True, has_mask=True),
            "wai_inpaint_basic",
        )
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "自動", False, has_pose=True, pose_mode="photo"),
            "wai_pose_detect",
        )
        self.assertEqual(
            gui.resolve_generation_workflow(self.cfg, "自動", False, has_pose=True, pose_mode="skeleton"),
            "wai_pose_skeleton",
        )

    def test_overrides_drop_width_for_inpaint_and_keep_size_for_pose(self):
        basics = {"width": 768, "height": 768, "steps": 20, "cfg": 5.0, "seed": 17}
        mask = gui.image_aware_overrides(self.cfg, "wai_inpaint_basic", True, basics, "0.6")
        self.assertEqual(mask, {"steps": 20, "cfg": 5.0, "seed": 17, "denoise": 0.6})
        pose = gui.image_aware_overrides(
            self.cfg, "wai_pose_detect", False, basics, "invalid", "0.8"
        )
        self.assertEqual(pose["control_strength"], 0.8)
        self.assertEqual(pose["width"], 768)
        self.assertNotIn("denoise", pose)
        with self.assertRaises(core.OrchestratorError):
            gui.image_aware_overrides(self.cfg, "wai_pose_detect", False, basics, "0.5", "99")

    def test_mask_pose_requirements_route_before_llm(self):
        self.cfg["llm"]["model"] = "unit-test-model"
        seen = []
        class FakeLM:
            def __init__(self, settings):
                pass

            def interpret(self, request, workflows, image, progress=None):
                seen.append(tuple(workflows))
                return {
                    "workflow_id": next(iter(workflows)),
                    "parameters": {"positive_prompt": "standing girl"},
                }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            img = root / "source.png"
            mask = root / "mask.png"
            pose = root / "pose.png"
            for item in (img, mask, pose):
                item.write_bytes(b"small")
            with patch.object(lmstudio, "LMStudio", FakeLM):
                core.execute(self.cfg, ROOT / "config.example.json", "hello", dry_run=True)
                core.execute(self.cfg, ROOT / "config.example.json", "hello", image=img, dry_run=True)
                core.execute(self.cfg, ROOT / "config.example.json", "hello", image=img, mask_image=mask, dry_run=True)
                core.execute(
                    self.cfg, ROOT / "config.example.json", "hello",
                    pose_image=pose, selected_workflow="wai_pose_detect", dry_run=True,
                )
        self.assertEqual(seen, [
            ("wai_t2i_basic",),
            ("wai_i2i_basic",),
            ("wai_inpaint_basic",),
            ("wai_pose_detect",),
        ])

    def test_inpaint_without_mask_fails_before_model_load(self):
        with tempfile.TemporaryDirectory() as directory:
            img = Path(directory) / "source.png"
            img.write_bytes(b"x")
            with self.assertRaisesRegex(core.OrchestratorError, "一致"):
                core.execute(
                    self.cfg, ROOT / "config.example.json", "hello",
                    image=img, selected_workflow="wai_inpaint_basic", dry_run=True,
                )

    def test_model_dependency_failures_explain_missing_weights(self):
        entry = self.entries["wai_pose_skeleton"]
        workflow = core.load_workflow(ROOT / entry["file"], entry["bindings"])
        def mock_http(_base, route, timeout=60):
            if route == "/object_info/ControlNetLoader":
                return {"ControlNetLoader": {
                    "input": {"required": {"control_net_name": [["other-model.safetensors"]]}}
                }}
            raise AssertionError(route)
        with patch.object(core, "http_json", side_effect=mock_http):
            with self.assertRaisesRegex(core.OrchestratorError, "OpenPose用ControlNetモデルがありません"):
                core.ComfyUI(self.cfg["comfyui"]).ensure_pose_dependencies(workflow)

    def test_dwpose_extension_is_checked(self):
        entry = self.entries["wai_pose_detect"]
        workflow = core.load_workflow(ROOT / entry["file"], entry["bindings"])
        expected_name = workflow["22"]["inputs"]["control_net_name"]
        def mock_http(_base, route, timeout=60):
            if route == "/object_info/ControlNetLoader":
                return {"ControlNetLoader": {
                    "input": {"required": {"control_net_name": [[expected_name]]}}
                }}
            if route == "/object_info/DWPreprocessor":
                return {}
            raise AssertionError(route)
        with patch.object(core, "http_json", side_effect=mock_http):
            with self.assertRaisesRegex(core.OrchestratorError, "comfyui_controlnet_aux"):
                core.ComfyUI(self.cfg["comfyui"]).ensure_pose_dependencies(workflow)

    def test_saved_inpaint_replay_uploads_both_images(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            mask = Path(folder) / "mask.png"
            source.write_bytes(b"s")
            mask.write_bytes(b"m")
            entry = self.entries["wai_inpaint_basic"]
            params = dict(entry["defaults"], positive_prompt="hand", seed=55)
            with patch.object(core, "ComfyUI") as mocked:
                runner = mocked.return_value
                runner.upload_image.side_effect = ["source_cloud.png", "mask_cloud.png"]
                runner.submit.return_value = "some-prompt"
                runner.wait.return_value = {}
                core.execute_saved(
                    self.cfg, ROOT / "config.example.json",
                    "wai_inpaint_basic", params,
                    reference_image=source, mask_image=mask,
                )
                graph = runner.submit.call_args.args[0]
            self.assertEqual(graph["16"]["inputs"]["image"], "source_cloud.png")
            self.assertEqual(graph["19"]["inputs"]["image"], "mask_cloud.png")
            self.assertEqual(graph["11"]["inputs"]["seed"], 55)


class HistoryInputTests(unittest.TestCase):
    def test_mask_and_pose_are_archived_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = history.HistoryStore(root)
            output = store.outputs / "out.png"
            output.write_bytes(b"o")
            mask = root / "mask.png"
            mask.write_bytes(b"m")
            original = root / "original.png"
            original.write_bytes(b"r")
            entry = store.record(
                prompt_id="123", workflow_id="wai_inpaint_basic", kind="inpaint",
                request_text="指を直す", parameters={"positive_prompt": "hand", "seed": 2},
                images=[output], reference_image=original, mask_image=mask,
            )
            mask.unlink()
            original.unlink()
            reloaded = history.HistoryStore(root).get(entry.id)
            self.assertEqual(reloaded.mask_image.read_bytes(), b"m")
            self.assertEqual(reloaded.reference_image.read_bytes(), b"r")
            pose = root / "pose.png"
            pose.write_bytes(b"pose bytes")
            entry2 = store.record(
                prompt_id="124", workflow_id="wai_pose_detect", kind="pose",
                request_text="座って", parameters={"positive_prompt": "girl", "seed": 1},
                images=[output], pose_image=pose,
            )
            pose.unlink()
            self.assertEqual(store.get(entry2.id).pose_image.read_bytes(), b"pose bytes")

    def test_schema_migration_from_old_database_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            with sqlite3.connect(data / "history.sqlite3") as con:
                con.execute(
                    """CREATE TABLE generations (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    prompt_id TEXT NOT NULL UNIQUE, workflow_id TEXT NOT NULL,
                    kind TEXT NOT NULL, request_text TEXT NOT NULL,
                    parameters_json TEXT NOT NULL, images_json TEXT NOT NULL,
                    reference_file TEXT, legacy INTEGER NOT NULL DEFAULT 0)"""
                )
                con.execute(
                    "INSERT INTO generations VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("old", "2026-01-01T00:00:00+00:00", "old", "wai_t2i_basic",
                     "t2i", "old sample", '{"positive_prompt":"girl","seed":42}',
                     '["old.png"]', None, 0),
                )
            store = history.HistoryStore(root)
            self.assertIsNone(store.get("old").mask_image)
            self.assertIsNone(store.get("old").pose_image)
            self.assertEqual(store.get("old").parameters["seed"], 42)


@unittest.skipUnless(importlib.util.find_spec("PIL") is not None, "Pillow optional")
class MaskRasterTests(unittest.TestCase):
    def test_strokes_rasterize_at_original_resolution(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "mask.png"
            mask_editor.export_strokes(
                (512, 384), (256, 192),
                [(15, [(40, 30), (100, 70)])],
                target,
            )
            with Image.open(target) as loaded:
                self.assertEqual(loaded.size, (512, 384))
                self.assertEqual(loaded.mode, "RGB")
                self.assertEqual(loaded.getpixel((0, 0)), (0, 0, 0))
                self.assertEqual(loaded.getpixel((80, 60)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
