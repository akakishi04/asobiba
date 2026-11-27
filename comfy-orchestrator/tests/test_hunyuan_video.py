import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui, lmstudio, http_api

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class HunyuanTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.entry = self.config["workflows"][core.HUNYUAN_I2V_ID]
        self.graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])

    def test_graph_settings_and_schema(self):
        self.assertEqual(self.graph["130"]["inputs"]["shift"], 7)
        self.assertEqual(self.graph["126"]["inputs"]["model"], ["130", 0])
        self.assertEqual(self.graph["129"]["inputs"]["cfg"], 1)
        self.assertEqual(self.graph["78"]["inputs"]["start_image"], ["80", 0])
        self.assertEqual(self.graph["125"]["inputs"]["latent_image"], ["78", 2])
        self.assertEqual(self.graph["101"]["inputs"]["fps"], 24)
        core.validate_video_parameters(core.HUNYUAN_I2V_ID, self.entry["defaults"])
        for changes in ({"steps": 20}, {"fps": 30}, {"frames": 124}, {"width": 1280}):
            with self.subTest(changes=changes), self.assertRaises(core.OrchestratorError):
                core.validate_video_parameters(core.HUNYUAN_I2V_ID, {**self.entry["defaults"], **changes})

    def test_image_only_without_llm(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret") as llm, patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "source.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                result = core.execute(self.config, CONFIG, "", image=source,
                    selected_workflow=core.HUNYUAN_I2V_ID, overrides={"seed": 11, "steps": 12})
                llm.assert_not_called()
                comfy.free_if_idle.assert_not_called()
                graph = comfy.submit.call_args.args[0]
                self.assertEqual(graph["44"]["inputs"]["text"], core.I2V_DEFAULT_PROMPT)
                self.assertEqual(graph["126"]["inputs"]["steps"], 12)
                self.assertEqual(graph["127"]["inputs"]["noise_seed"], 11)
                self.assertEqual(result["workflow_id"], core.HUNYUAN_I2V_ID)

    def test_preflight_checks_both_encoders(self):
        fields = {"UNETLoader": ("unet_name",), "DualCLIPLoader": ("clip_name1", "clip_name2"),
                  "CLIPVisionLoader": ("clip_name",), "VAELoader": ("vae_name",)}
        def fake_info(base, route, **kwargs):
            kind = route.rsplit("/", 1)[-1]
            required = {}
            for field in fields.get(kind, ()):
                required[field] = [[n["inputs"][field] for n in self.graph.values()
                                    if n["class_type"] == kind and field != "clip_name2"]]
            return {kind: {"input": {"required": required}}}
        with patch.object(http_api, "http_json", side_effect=fake_info):
            with self.assertRaisesRegex(core.OrchestratorError, "byt5_small_glyphxl"):
                core.ComfyUI(self.config["comfyui"]).ensure_video_dependencies(self.graph)

    def test_separate_gui_parameters(self):
        v = gui.parameter_visibility(self.config, core.HUNYUAN_I2V_ID)
        self.assertTrue(v["hunyuan"])
        self.assertFalse(v["h3"] or v["wan"] or v["cfg"] or v["steps"])
        var = lambda s: SimpleNamespace(get=lambda: s)
        app = SimpleNamespace(hunyuan_size=var("480 × 848"), hunyuan_frames=var("81"),
                              hunyuan_steps=var("12"), seed=var("7"))
        self.assertEqual(gui.Application._hunyuan_overrides(app),
                         {"width": 480, "height": 848, "frames": 81, "fps": 24, "steps": 12, "seed": 7})


if __name__ == "__main__":
    unittest.main()
