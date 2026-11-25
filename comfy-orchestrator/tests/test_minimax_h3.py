"""Offline regression coverage of the native H3 FL2VA workflow."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio

ROOT = Path(__file__).resolve().parents[1]


class MiniMaxH3Tests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")
        self.entry = self.config["workflows"][core.H3_I2V_ID]

    def test_native_audio_and_video_graph(self):
        graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])
        rendered = core.render_workflow(graph, self.entry["bindings"], dict(
            self.entry["defaults"], positive_prompt="A gentle breeze.", frames=362, seed=88,
        ), "source.png")
        self.assertEqual(rendered["104"]["inputs"]["length"], 362)
        self.assertEqual(rendered["104"]["inputs"]["first_frame"], ["114", 0])
        self.assertEqual(rendered["114"]["inputs"]["image"], "source.png")
        self.assertEqual(rendered["14"]["inputs"]["latent_image"], ["104", 1])
        self.assertEqual(rendered["91"]["inputs"]["audio"], ["23", 0])
        self.assertEqual(rendered["91"]["inputs"]["fps"], 24)
        self.assertEqual(rendered["15"]["inputs"]["noise_seed"], 88)

    def test_host_controls_and_schema(self):
        fields = core.plan_schema({core.H3_I2V_ID: self.entry})["properties"]["parameters"]["properties"]
        self.assertEqual(set(fields), {"positive_prompt"})
        for count in gui.H3_DURATIONS.values():
            core.validate_h3_video_parameters(dict(self.entry["defaults"], frames=count))
        for values in ({"fps": 30}, {"frames": 121}, {"width": 320}, {"height": 720}):
            with self.assertRaises(core.OrchestratorError):
                core.validate_h3_video_parameters(dict(self.entry["defaults"], **values))

    def test_dry_run_and_automatic_still_route(self):
        self.assertEqual(gui.resolve_generation_workflow(self.config, "自動", True), "wai_i2i_basic")
        self.assertEqual(gui.resolve_generation_workflow(self.config, core.H3_I2V_ID, False), core.H3_I2V_ID)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"img")
            def interpret(instance, request, workflows, image, **kwargs):
                self.assertEqual(instance.settings["_h3_duration_seconds"], 362 / 24)
                return {"workflow_id": core.H3_I2V_ID, "parameters": {
                    "positive_prompt": "The subject moves.", "negative_prompt": "unused",
                    "frames": 999, "fps": 30, "cfg": 9,
                }}
            with patch.object(lmstudio.LMStudio, "interpret", autospec=True, side_effect=interpret):
                result = core.execute(self.config, ROOT / "config.example.json", "動く",
                    image=source, dry_run=True, selected_workflow=core.H3_I2V_ID,
                    overrides={"frames": 362})
            self.assertEqual(result["parameters"]["frames"], 362)
            self.assertNotIn("cfg", result["parameters"])
            self.assertNotIn("negative_prompt", result["parameters"])

    def test_separate_h3_controls(self):
        var = lambda text: SimpleNamespace(get=lambda: text)
        app = SimpleNamespace(h3_size=var("480 × 864"), h3_duration=var("約15秒 (362f)"),
                              steps=var("20"), seed=var(""))
        self.assertEqual(gui.Application._h3_overrides(app),
            {"width": 480, "height": 864, "frames": 362, "fps": 24, "steps": 20})


if __name__ == "__main__":
    unittest.main()
