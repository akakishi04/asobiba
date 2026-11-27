"""Regression for ComfyUI legacy and V3 dropdown API responses."""
import unittest
from unittest.mock import patch

from comfy_orchestrator import core, http_api


def schema(field, spec):
    return {"input": {"required": {field: spec}}}


class ComboSchemaTests(unittest.TestCase):
    def setUp(self):
        self.comfy = core.ComfyUI({"base_url": "http://127.0.0.1:8188"})

    def test_user_attention_response(self):
        graph = {"1": {"class_type": "ModelAttentionBackend",
                       "inputs": {"attention": "comfy kitchen attention"}}}
        info = {"ModelAttentionBackend": schema("attention", [
            "COMBO", {"display_name": "backend", "default": "pytorch attention",
                      "multiselect": False,
                      "options": ["pytorch attention", "comfy kitchen attention"]}])}
        with patch.object(http_api, "http_json", return_value=info):
            self.comfy.ensure_video_dependencies(graph)
        info["ModelAttentionBackend"]["input"]["required"]["attention"][1]["options"].pop()
        with patch.object(http_api, "http_json", return_value=info):
            with self.assertRaisesRegex(core.OrchestratorError, "Attention backend"):
                self.comfy.ensure_video_dependencies(graph)

    def test_both_schema_versions_and_empty_list(self):
        for spec in ([["model.safetensors"]], ["COMBO", {"options": ["model.safetensors"]}]):
            self.assertEqual(core.combo_choices(schema("name", spec), "name"), ("model.safetensors",))
        for spec in ([[]], ["COMBO", {"options": []}]):
            self.assertEqual(core.combo_choices(schema("name", spec), "name"), ())

    def test_invalid_spec_rejected_not_substring_matched(self):
        for spec in (["STRING", {"default": "model.safetensors"}], ["COMBO", {}],
                     ["COMBO", {"options": "model.safetensors"}], [["model.safetensors", 1]]):
            with self.subTest(spec=spec), self.assertRaises(TypeError):
                core.combo_choices(schema("name", spec), "name")

    def test_inventory_modern_combo(self):
        def api(base, route, **kwargs):
            node = route.rsplit("/", 1)[-1]
            if node == "UnetLoaderGGUF":
                return {}
            field = "ckpt_name" if node == "CheckpointLoaderSimple" else "unet_name"
            return {node: schema(field, ["COMBO", {"options": ["model.safetensors"]}])}
        with patch.object(http_api, "http_json", side_effect=api):
            self.assertEqual(self.comfy.list_generation_models(), {
                "CheckpointLoaderSimple": ("model.safetensors",),
                "UNETLoader": ("model.safetensors",), "UnetLoaderGGUF": ()})

    def test_controlnet_modern_combo(self):
        graph = {"1": {"class_type": "ControlNetLoader",
                       "inputs": {"control_net_name": "pose.safetensors"}}}
        with patch.object(http_api, "http_json", return_value={
                "ControlNetLoader": schema("control_net_name", ["COMBO", {"options": ["pose.safetensors"]}])}):
            self.comfy.ensure_pose_dependencies(graph)


if __name__ == "__main__":
    unittest.main()
