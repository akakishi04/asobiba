"""Native T2VA for single H3 clips, using existing execution and history paths."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, h3_prompt as hp, lmstudio
from comfy_orchestrator.generation_controller import GenerationController
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.history_presentation import history_can_replay, history_summary
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.prompt_cache import PromptCache
from comfy_orchestrator.single_prompt import SinglePromptDraft

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
BACKEND = "http://localhost:8188"
PARAMS = {"width": 864, "height": 480, "frames": 124, "fps": 24,
          "seed": 11, "steps": 8, "h3_model": "w4a8", "h3_turbo": "turbo8"}


def fields(text="A woman in a red coat walks along a rainy street."):
    return {"integrated_multimodal_description": "[Shot 1] " + text,
            "overall_soundscape": "Quiet rain and footsteps.",
            "non_diegetic_music": "N/A"}


def reply(value):
    return {"choices": [{"message": {"content": json.dumps(value)}}]}


class TextOnlySingleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.config = core.load_config(CONFIG)
        self.config["llm"].update(model="test", unload_after_inference=False,
                                  h3_prompt_format=hp.LEGACY, h3_reference_vision=True)
        self.config["comfyui"].update(base_url=BACKEND, free_before_llm=False)
        self.journal = JobJournal(self.root / "jobs")
        self.history = HistoryStore(self.root)
        self.cache = PromptCache(self.root / "plans.sqlite3")
        self.catalog = [{"key": "test", "capabilities": {"vision": True},
                         "loaded_instances": [{"id": "instance"}]}]
        self.comfy = Mock(base=BACKEND)
        self.comfy.submit.side_effect = lambda graph, prompt_id: prompt_id
        self.comfy.wait.return_value = {"outputs": {}}

    def execute(self, **kwargs):
        return core.execute(self.config, CONFIG, "雨の街を歩く",
                            selected_workflow=core.H3_I2V_ID,
                            overrides=kwargs.pop("overrides", PARAMS), **kwargs)

    def assert_text_graph(self, graph):
        self.assertNotIn("114", graph)
        self.assertEqual(graph["104"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertNotIn("first_frame", graph["104"]["inputs"])
        self.assertNotIn("last_frame", graph["104"]["inputs"])
        self.assertNotIn(hp.I2VA_HEADER, graph["104"]["inputs"]["prompt"])
        self.assertNotIn("<Picture 1>", graph["104"]["inputs"]["prompt"])
        self.assertEqual(graph["91"]["inputs"]["audio"], ["23", 0])
        self.assertFalse(any(node.get("class_type") == "LoadImage" for node in graph.values()))

    def test_direct_t2va_preflight_prompt_graph_and_journal(self):
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", return_value=reply(fields())) as req:
            result = self.execute(job_journal=self.journal)
        req.assert_called_once()
        payload = req.call_args.args[2]
        self.assertEqual(payload["response_format"]["json_schema"]["name"], "h3_official_prompt")
        self.assertIn("no source image", payload["messages"][0]["content"])
        content = json.loads(payload["messages"][1]["content"])
        self.assertEqual(content["reference_mode"], "T2VA")
        self.assertIsNone(content["reference_observations"])
        self.assertTrue(result["parameters"]["text_only_h3"])
        self.comfy.upload_image.assert_not_called()
        self.assert_text_graph(self.comfy.submit.call_args.args[0])
        checked = self.comfy.ensure_video_dependencies.call_args.args[0]
        self.assertNotIn("114", checked)
        row = self.journal.read(result["job_id"])
        self.assertIsNone(row["context"]["reference_image"])
        self.assertTrue(row["context"]["text_only_h3"])
        self.assertTrue(row["parameters"]["text_only_h3"])
        self.assertEqual(self.comfy.submit.call_count, 1)

    def test_prompt_review_can_edit_and_generate_without_llm_reinterpretation(self):
        service = GenerationController(self.config, CONFIG, self.root, self.history, self.journal,
                                        cancel_event=threading.Event())
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", return_value=reply(fields())):
            draft = SinglePromptDraft.prepare(service, "雨の街を歩く", core.H3_I2V_ID, PARAMS)
        self.addCleanup(draft.close)
        self.assertTrue(draft.text_only and draft.official)
        self.comfy.submit.assert_not_called()
        changed = hp.section_text(fields("A woman in a blue coat walks."), False)
        draft.set_english({"positive_prompt": changed})
        before = copy.deepcopy(draft.parameters)
        with self.assertRaises(core.OrchestratorError):
            draft.set_english({"positive_prompt": hp.section_text(fields("Copy <Picture 1>."), False)})
        self.assertEqual(draft.parameters, before)
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio.LMStudio, "interpret", side_effect=AssertionError("unexpected LLM")), \
                patch.object(service, "finish", side_effect=lambda result, *a, **kw: (result, [], None)):
            result, _, _ = draft.generate()
        self.assertEqual(result["parameters"]["positive_prompt"], changed)
        self.assertEqual(result["parameters"]["seed"], 11)
        self.assertTrue(result["parameters"]["text_only_h3"])
        self.assert_text_graph(self.comfy.submit.call_args.args[0])

    def test_replay_same_and_new_seed_retains_explicit_mode(self):
        params = {**PARAMS, "positive_prompt": hp.compile_prompt(fields(), False, text_only=True),
                  "text_only_h3": True}
        video = self.history.outputs / "result.mp4"
        video.write_bytes(b"video")
        entry = self.history.record(prompt_id="existing", workflow_id=core.H3_I2V_ID,
                                    kind="i2v", request_text="雨の街を歩く", parameters=params,
                                    images=[video])
        service = GenerationController(self.config, CONFIG, self.root, self.history, self.journal)
        self.assertTrue(history_can_replay([entry], self.config["workflows"], working=False))
        self.assertIn("T2VA", history_summary(entry))
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio.LMStudio, "interpret", side_effect=AssertionError("unexpected LLM")), \
                patch.object(core.secrets, "randbits", return_value=22), \
                patch.object(service, "finish", side_effect=lambda result, *a, **kw: (result, [], None)):
            first = service.replay(entry)[0]
            second = service.replay(entry, new_seed=True)[0]
        self.assertEqual(first["parameters"], params)
        self.assertEqual(second["parameters"], {**params, "seed": 22})
        self.comfy.upload_image.assert_not_called()
        for call in self.comfy.submit.call_args_list:
            self.assert_text_graph(call.args[0])
        # Old I2VA history without an image cannot be reinterpreted as T2VA.
        old = SimpleNamespace(**{**entry.__dict__, "parameters": {k: v for k, v in params.items()
                                                                 if k != "text_only_h3"}})
        self.assertFalse(history_can_replay([old], self.config["workflows"], working=False))

    def test_text_only_cache_never_reuses_image_conditioned_prompt(self):
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", return_value=reply(fields())) as req:
            first = self.execute(dry_run=True, prompt_cache=self.cache)
            second = self.execute(dry_run=True, prompt_cache=self.cache)
            req.assert_called_once()
            source = self.root / "image.png"
            source.write_bytes(b"image")
            self.config["llm"].update(h3_prompt_format=hp.FORMAT, h3_reference_vision=False)
            third = self.execute(image=source, dry_run=True, prompt_cache=self.cache)
            self.assertEqual(req.call_count, 2)
        self.assertTrue(first["parameters"]["text_only_h3"])
        self.assertEqual(first, second)
        self.assertNotIn("text_only_h3", third["parameters"])
        self.assertTrue(third["parameters"]["positive_prompt"].startswith(hp.I2VA_HEADER))

    def test_model_conversion_and_missing_inputs_fail_before_inference(self):
        hybrid = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors", reference_only=True)
        pure = core.h3_ref2va_model_key("minimax_h3_ref2va_int8.safetensors")
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", return_value=reply(fields())) as req:
            result = self.execute(dry_run=True, overrides={**PARAMS, "h3_model": hybrid, "h3_turbo": "off"})
            self.assertTrue(result["parameters"]["h3_model"].startswith("hybrid_i2v:"))
            for wf in (core.WAN_I2V_ID, core.HUNYUAN_I2V_ID):
                with self.assertRaises(core.OrchestratorError):
                    core.execute(self.config, CONFIG, "動く", selected_workflow=wf, dry_run=True)
            with self.assertRaises(core.OrchestratorError):
                self.execute(dry_run=True, overrides={**PARAMS, "h3_model": pure})
            with self.assertRaises(core.OrchestratorError):
                core.execute(self.config, CONFIG, "", selected_workflow=core.H3_I2V_ID, dry_run=True)
            req.assert_called_once()

    def test_saved_mode_marker_cannot_override_real_inputs_or_other_workflows(self):
        params = {**PARAMS, "positive_prompt": hp.compile_prompt(fields(), False, text_only=True)}
        source = self.root / "image.png"
        source.write_bytes(b"image")
        with patch.object(core, "ComfyUI", return_value=self.comfy) as factory:
            for options in (params, {**params, "text_only_h3": False}):
                with self.assertRaises(core.OrchestratorError):
                    core.execute_saved(self.config, CONFIG, core.H3_I2V_ID, options)
            with self.assertRaises(core.OrchestratorError):
                core.execute_saved(self.config, CONFIG, core.H3_I2V_ID,
                                   {**params, "text_only_h3": True}, reference_image=source)
            with self.assertRaises(core.OrchestratorError):
                core.execute_saved(self.config, CONFIG, "wai_t2i_basic",
                                   {"positive_prompt": "tree", "seed": 1, "text_only_h3": True})
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
