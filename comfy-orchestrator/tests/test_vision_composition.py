"""Local composition analysis: VLM source, pose input and text-only fallback."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio


ROOT = Path(__file__).resolve().parents[1]


class CompositionVisionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = core.load_config(ROOT / "config.example.json")
        self.cfg["llm"]["model"] = "test-vision-model"
        self.cfg["llm"]["send_reference_to_llm"] = True
        self.answer = {
            "workflow_id": "wai_i2i_basic",
            "parameters": {
                "positive_prompt": (
                    "1girl, full body, low angle, sitting on chair, "
                    "subject on left third of frame"
                ),
            },
        }

    def _interpret_and_capture(self, kind: str, role: str):
        catalog = {kind: self.cfg["workflows"][kind]}
        self.answer["workflow_id"] = kind
        calls = []

        def fake_request(settings, route, payload=None):
            calls.append((route, payload))
            if route == "/v1/chat/completions":
                return {
                    "choices": [
                        {"message": {"content": json.dumps(self.answer)}}
                    ]
                }
            if route == "/api/v1/models/unload":
                return {"instance_id": "vision-instance"}
            raise AssertionError(f"unexpected route {route}")

        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "pose.png"
            reference.write_bytes(b"test-image-bytes")
            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="vision-instance"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                result = lmstudio.LMStudio(self.cfg["llm"]).interpret(
                    "この構図の人物を赤髪の少女にして",
                    catalog, reference,
                )
        self.assertEqual(result["workflow_id"], kind)
        payload = next(body for name, body in calls if name == "/v1/chat/completions")
        system = payload["messages"][0]["content"]
        message = payload["messages"][1]["content"]
        self.assertIsInstance(message, list)
        self.assertEqual(message[1]["type"], "image_url")
        self.assertTrue(
            message[1]["image_url"]["url"].startswith("data:image/png;base64,")
        )
        self.assertIn("COMPOSITION", system)
        self.assertIn("camera elevation", system)
        self.assertIn("subject location in the frame", system)
        self.assertIn("Reference image visible to the LLM: yes", message[0]["text"])
        self.assertIn(role, system)
        self.assertEqual(calls[-1][0], "/api/v1/models/unload")
        return payload

    def test_i2i_image_informs_composition_prompt(self):
        self._interpret_and_capture("wai_i2i_basic", "image to be edited")

    def test_pose_reference_is_limited_to_pose_and_viewpoint(self):
        payload = self._interpret_and_capture("wai_pose_detect", "POSE reference")
        self.assertIn("do not borrow the mannequin's material", payload["messages"][0]["content"])
        self.assertIn("Reference role: pose and camera only", payload["messages"][1]["content"][0]["text"])

    def test_pose_photo_is_passed_to_local_lmstudio(self):
        seen = []
        self.cfg["llm"]["model"] = "test-vision-model"

        class FakeLM:
            def __init__(self, settings):
                self.settings = settings

            def interpret(self, text, workflows, image, progress=None):
                seen.append((image, tuple(workflows), self.settings["send_reference_to_llm"]))
                return {
                    "workflow_id": "wai_pose_detect",
                    "parameters": {"positive_prompt": "1girl, sitting, side view"},
                }

        with tempfile.TemporaryDirectory() as folder:
            photo = Path(folder) / "designdoll.png"
            photo.write_bytes(b"example")
            with patch.object(lmstudio, "LMStudio", FakeLM):
                result = core.execute(
                    self.cfg, ROOT / "config.example.json",
                    "モデルと同じ構図のイラストを描く",
                    selected_workflow="wai_pose_detect",
                    pose_image=photo, dry_run=True,
                )
            self.assertEqual(result["workflow_id"], "wai_pose_detect")
            self.assertEqual(seen, [(photo.resolve(), ("wai_pose_detect",), True)])

    def test_known_text_only_model_is_rejected_before_loading(self):
        client = lmstudio.LMStudio({
            **self.cfg["llm"], "model": "plain-text-model",
        })
        client._has_visual_input = True
        model = {
            "type": "llm", "key": "plain-text-model",
            "capabilities": {"vision": False}, "loaded_instances": [],
        }
        with patch.object(lmstudio, "list_models", return_value=[model]):
            with patch.object(lmstudio, "_request") as mock_request:
                with self.assertRaisesRegex(core.OrchestratorError, "画像入力に非対応"):
                    client._ensure_loaded()
                mock_request.assert_not_called()

    def test_without_image_no_vlm_is_required_even_when_toggle_is_on(self):
        client = lmstudio.LMStudio({
            **self.cfg["llm"], "model": "plain-text-model",
        })
        client._has_visual_input = False
        model = {
            "type": "llm", "key": "plain-text-model",
            "capabilities": {"vision": False},
            "loaded_instances": [{"id": "plain-running"}],
        }
        with patch.object(lmstudio, "list_models", return_value=[model]):
            self.assertEqual(client._ensure_loaded(), "plain-running")

    def test_invalid_vision_setting_rejected_by_config_validation(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["llm"]["send_reference_to_llm"] = "yes"
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)
            # load_config expects templates relative to the config directory.
            for entry in cfg["workflows"].values():
                entry["file"] = str((ROOT / entry["file"]).resolve())
            # The config loader rejects invalid options before checking workflow files.
            settings = destination / "config.json"
            settings.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(core.OrchestratorError, "send_reference_to_llm"):
                core.load_config(settings)

    def test_bootstrap_backfills_option_without_overriding_user_settings(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["llm"].pop("send_reference_to_llm")
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "config.json"
            target.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            with patch.object(gui, "CONFIG", target):
                loaded = gui.bootstrap_config()
            self.assertIs(loaded["llm"]["send_reference_to_llm"], False)

            cfg["llm"]["send_reference_to_llm"] = True
            target.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
            with patch.object(gui, "CONFIG", target):
                loaded = gui.bootstrap_config()
            self.assertIs(loaded["llm"]["send_reference_to_llm"], True)


if __name__ == "__main__":
    unittest.main()
