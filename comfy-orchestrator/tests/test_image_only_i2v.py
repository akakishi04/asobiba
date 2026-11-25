"""Reference-only video generation must not require a user prompt or LLM."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, lmstudio

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class ImageOnlyI2VTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.config["llm"]["send_reference_to_llm"] = False

    def test_h3_and_wan_accept_blank_request_without_llm(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            for workflow in (core.H3_I2V_ID, core.WAN_I2V_ID):
                with self.subTest(workflow=workflow), patch.object(lmstudio.LMStudio, "interpret") as llm:
                    result = core.execute(
                        self.config, CONFIG, "   ", image=source, dry_run=True,
                        selected_workflow=workflow, overrides={"seed": 11},
                    )
                    self.assertEqual(result["parameters"]["positive_prompt"], core.I2V_DEFAULT_PROMPT)
                    self.assertEqual(result["parameters"]["seed"], 11)
                    llm.assert_not_called()

    def test_image_only_h3_submits_selected_model_and_turbo(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret") as llm, patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "source.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                result = core.execute(
                    self.config, CONFIG, "", image=source,
                    selected_workflow=core.H3_I2V_ID,
                    overrides={"h3_model": "w4a8", "h3_turbo": "turbo8", "seed": 17},
                )
                llm.assert_not_called()
                comfy.free_if_idle.assert_not_called()
                graph = comfy.submit.call_args.args[0]
                self.assertEqual(graph["104"]["inputs"]["prompt"], core.I2V_DEFAULT_PROMPT)
                self.assertEqual(graph["6"]["inputs"]["unet_name"], core.H3_MODELS["w4a8"])
                self.assertEqual(graph["9"]["inputs"]["steps"], 8)
                self.assertEqual(result["parameters"]["h3_turbo"], "turbo8")

    def test_text_i2v_still_releases_before_llm(self):
        self.config["comfyui"]["free_before_llm"] = True
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret", return_value={
                "workflow_id": core.H3_I2V_ID,
                "parameters": {"positive_prompt": "Motion."},
            }), patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "source.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                core.execute(self.config, CONFIG, "動かす", image=source,
                             selected_workflow=core.H3_I2V_ID)
                comfy.free_if_idle.assert_called_once()

    def test_still_image_analysis_options_never_trigger_llm_on_empty_i2v(self):
        self.config["llm"]["send_reference_to_llm"] = True
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            for workflow in (core.H3_I2V_ID, core.WAN_I2V_ID):
                with self.subTest(workflow=workflow), patch.object(lmstudio.LMStudio, "interpret") as llm:
                    result = core.execute(
                        self.config, CONFIG, "", image=source, dry_run=True,
                        selected_workflow=workflow,
                        character_traits="still-image character description",
                        composition_image=Path(folder) / "missing-still-composition.png",
                    )
                    llm.assert_not_called()
                    self.assertEqual(result["parameters"]["positive_prompt"], core.I2V_DEFAULT_PROMPT)
        self.assertTrue(self.config["llm"]["send_reference_to_llm"])

    def test_nonempty_i2v_passes_only_text_to_lmstudio(self):
        self.config["llm"]["send_reference_to_llm"] = True
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            for workflow in (core.H3_I2V_ID, core.WAN_I2V_ID):
                with self.subTest(workflow=workflow), patch.object(lmstudio, "LMStudio") as factory:
                    llm = factory.return_value
                    llm.interpret.return_value = {
                        "workflow_id": workflow,
                        "parameters": {"positive_prompt": "Hair moves gently."},
                    }
                    result = core.execute(
                        self.config, CONFIG, "髪を揺らす", image=source, dry_run=True,
                        selected_workflow=workflow, character_traits="still-image traits",
                    )
                    self.assertFalse(factory.call_args.args[0]["send_reference_to_llm"])
                    self.assertEqual(llm.interpret.call_args.args[0], "髪を揺らす")
                    self.assertIsNone(llm.interpret.call_args.args[2])
                    self.assertNotIn("character_traits", llm.interpret.call_args.kwargs)
                    self.assertEqual(result["parameters"]["positive_prompt"], "Hair moves gently.")
        self.assertTrue(self.config["llm"]["send_reference_to_llm"])

    def test_ollama_i2v_also_uses_text_only(self):
        self.config["llm"]["provider"] = "ollama"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(b"image")
            with patch.object(core.Ollama, "interpret", return_value={
                "workflow_id": core.H3_I2V_ID,
                "parameters": {"positive_prompt": "Motion."},
            }) as llm:
                core.execute(self.config, CONFIG, "動かす", image=source, dry_run=True,
                             selected_workflow=core.H3_I2V_ID)
                self.assertIsNone(llm.call_args.args[2])

    def test_still_and_missing_reference_do_not_accept_blank(self):
        for workflow, image in (("wai_t2i_basic", None), (core.H3_I2V_ID, None),
                                ("wai_i2i_basic", Path("source.png")), (None, Path("source.png"))):
            with self.subTest(workflow=workflow):
                self.assertFalse(core.supports_empty_i2v_request(self.config, workflow, image))
                with self.assertRaisesRegex(core.OrchestratorError, "自然文"):
                    core.execute(self.config, CONFIG, "", image=image, dry_run=True,
                                 selected_workflow=workflow)

    def test_context_detection(self):
        self.assertFalse(core.needs_prompt_llm(self.config, " "))
        self.assertTrue(core.needs_prompt_llm(self.config, "髪を揺らす"))
        self.assertTrue(core.needs_prompt_llm(self.config, "", "character traits"))
        self.config["llm"]["send_reference_to_llm"] = True
        self.assertFalse(core.needs_prompt_llm(self.config, " ", "character traits",
                                               workflow_id=core.H3_I2V_ID))
        self.assertTrue(core.needs_prompt_llm(self.config, "動かす", workflow_id=core.WAN_I2V_ID))


if __name__ == "__main__":
    unittest.main()
