"""Prompt reuse must skip LLM/free, never reuse seeds or stale visual input."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.prompt_cache import PromptCache, make_cache_key

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class PromptCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = PromptCache(self.root / "cache.sqlite3")
        self.config = core.load_config(CONFIG)
        self.image = self.root / "image.png"
        self.image.write_bytes(b"source")

    def test_reuse_plan_not_seed_and_skip_unload(self):
        plan = {"workflow_id": core.H3_I2V_ID, "parameters": {"positive_prompt": "A tree sways."}}
        with patch.object(lmstudio.LMStudio, "interpret", return_value=plan) as llm, patch.object(core, "ComfyUI") as api:
            comfy = api.return_value
            comfy.upload_image.return_value = "img.png"
            comfy.submit.return_value = "job"
            comfy.wait.return_value = {"outputs": {}}
            common = {"image": self.image, "selected_workflow": core.H3_I2V_ID, "prompt_cache": self.cache}
            first = core.execute(self.config, CONFIG, "木が揺れる", overrides={"seed": 1}, **common)
            second = core.execute(self.config, CONFIG, "木が揺れる", overrides={"seed": 2, "steps": 16}, **common)
            self.assertEqual(first["parameters"]["seed"], 1)
            self.assertEqual(second["parameters"]["seed"], 2)
            self.assertEqual(second["parameters"]["steps"], 16)
            llm.assert_called_once()
            comfy.free_if_idle.assert_called_once()
            self.assertEqual(self.cache.clear(), 1)
            core.execute(self.config, CONFIG, "木が揺れる", **common)
            self.assertEqual(llm.call_count, 2)

    def test_key_distinguishes_file_content_and_settings(self):
        def key(settings):
            return make_cache_key("x", settings, {}, {}, {"image": self.image}, None)
        a = key({"model": "a"})
        self.assertNotEqual(a, key({"model": "b"}))
        self.image.write_bytes(b"changed")
        self.assertNotEqual(a, key({"model": "a"}))

    def test_identical_uploads_have_same_content_name(self):
        other = self.root / "different_name.png"
        other.write_bytes(self.image.read_bytes())
        with patch.object(core, "_open_json", return_value={"name": "accepted.png"}) as api:
            comfy = core.ComfyUI(self.config["comfyui"])
            comfy.upload_image(self.image)
            comfy.upload_image(other)
        import re
        names = [re.search(rb'filename="([^"]+)"', call.args[0].data).group(1)
                 for call in api.call_args_list]
        self.assertEqual(names[0], names[1])
        self.assertTrue(names[0].startswith(b"asobiba_"))


if __name__ == "__main__":
    unittest.main()
