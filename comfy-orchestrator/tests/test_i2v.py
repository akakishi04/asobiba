"""Offline regressions for the registered Wan 2.2 native I2V workflow."""
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import core, gui, history, lmstudio

ROOT = Path(__file__).resolve().parents[1]


class VideoTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")
        self.entry = self.config["workflows"][core.WAN_I2V_ID]

    def test_graph_and_bindings(self):
        graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])
        params = dict(self.entry["defaults"], positive_prompt="Hair moves gently.", seed=42)
        rendered = core.render_workflow(graph, self.entry["bindings"], params, "first.png")
        self.assertEqual(rendered["55"]["inputs"]["start_image"], ["56", 0])
        self.assertEqual(rendered["56"]["inputs"]["image"], "first.png")
        self.assertEqual(rendered["55"]["inputs"]["length"], 49)
        self.assertEqual(rendered["57"]["inputs"]["fps"], 24)
        self.assertEqual(rendered["58"]["class_type"], "SaveVideo")
        self.assertEqual(rendered["3"]["inputs"]["seed"], 42)

    def test_explicit_selection_does_not_break_auto_i2i(self):
        self.assertEqual(gui.resolve_generation_workflow(self.config, "自動", True), "wai_i2i_basic")
        self.assertEqual(gui.resolve_generation_workflow(self.config, core.WAN_I2V_ID, False), core.WAN_I2V_ID)
        self.assertEqual(gui.resolve_generation_workflow(self.config, core.WAN_I2V_ID, True), core.WAN_I2V_ID)

    def test_video_technical_parameters_are_host_owned(self):
        schema = core.plan_schema({core.WAN_I2V_ID: self.entry})
        self.assertEqual(set(schema["properties"]["parameters"]["properties"]), {"positive_prompt", "negative_prompt"})
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "first.png"
            image.write_bytes(b"example")
            with patch.object(lmstudio.LMStudio, "interpret", return_value={
                "workflow_id": core.WAN_I2V_ID,
                "parameters": {"positive_prompt": "The camera remains fixed.", "frames": 9999, "width": 17},
            }):
                result = core.execute(
                    self.config, ROOT / "config.example.json", "カメラ固定",
                    image=image, dry_run=True, selected_workflow=core.WAN_I2V_ID,
                    overrides={"width": 480, "height": 832, "frames": 81, "fps": 24, "seed": 123},
                )
            self.assertEqual(result["parameters"]["frames"], 81)
            self.assertEqual(result["parameters"]["width"], 480)
            self.assertEqual(result["parameters"]["seed"], 123)
        with self.assertRaises(core.OrchestratorError):
            core.validate_wan_video_parameters(dict(self.entry["defaults"], frames=50))
        with self.assertRaises(core.OrchestratorError):
            core.validate_wan_video_parameters(dict(self.entry["defaults"], width=720))

    def test_native_video_output_and_download(self):
        item = {"filename": "clip.mp4", "subfolder": "video", "type": "output"}
        payload = {"outputs": {"58": {"images": [item], "animated": [True]}, "other": {"videos": [item]}}}
        self.assertEqual(gui.output_media(payload), [item])
        self.assertEqual(gui.output_images(payload), [])
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(gui, "OUTPUTS", Path(folder)), patch.object(
                gui.urllib.request, "urlopen", return_value=io.BytesIO(b"mp4-data")
            ):
                output = gui.save_output_image("http://localhost:8188", item, "prompt-id")
            self.assertEqual(output.suffix, ".mp4")
            self.assertEqual(output.read_bytes(), b"mp4-data")
            self.assertFalse(output.with_suffix(".mp4.part").exists())

    def test_video_history_retains_reference_and_replay_params(self):
        with tempfile.TemporaryDirectory() as folder:
            store = history.HistoryStore(Path(folder))
            video = store.outputs / "clip.mp4"
            video.write_bytes(b"mp4")
            source = Path(folder) / "first.png"
            source.write_bytes(b"image")
            entry = store.record(
                prompt_id="test", workflow_id=core.WAN_I2V_ID, kind="i2v",
                request_text="動かす", parameters=dict(self.entry["defaults"], positive_prompt="Motion.", seed=7),
                images=[video], reference_image=source,
            )
            saved = store.get(entry.id)
            self.assertEqual(saved.first_image, video)
            self.assertEqual(saved.parameters["frames"], 49)
            self.assertTrue(saved.reference_image.is_file())

    def test_dependency_check_detects_missing_model(self):
        graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])
        def info(base, route, **kwargs):
            node = route.rsplit("/", 1)[-1]
            if node == "CLIPLoader":
                return {node: {"input": {"required": {"clip_name": [[]]}}}}
            return {node: {}}
        comfy = core.ComfyUI(self.config["comfyui"])
        with patch.object(core, "http_json", side_effect=info):
            with self.assertRaisesRegex(core.OrchestratorError, "umt5_xxl"):
                comfy.ensure_video_dependencies(graph)

    def test_video_controls_do_not_replace_still_image_size(self):
        v = lambda text: SimpleNamespace(get=lambda: text)
        fake = SimpleNamespace(video_size=v("480 × 832"), video_frames=v("81"), video_fps=v("24"),
                               steps=v("20"), cfg=v("5.0"), seed=v(""))
        self.assertEqual(gui.Application._video_overrides(fake),
                         {"width": 480, "height": 832, "frames": 81, "fps": 24, "steps": 20, "cfg": 5.0})


if __name__ == "__main__":
    unittest.main()
