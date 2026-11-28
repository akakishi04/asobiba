"""Camera intent, model routing, projection, cache separation and exact replay."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import camera_spec as camera, camera_preview, core, image_prompts, lmstudio
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.history_presentation import history_prompt_details
from comfy_orchestrator.image_adjust import ImageAdjustDraft
from comfy_orchestrator.model_comparison import prepare_targets, project_prompt_pair
from comfy_orchestrator.model_profiles import ANIMA_ID, WAI_ID, QWEN_ID, ImageModelChoice
from comfy_orchestrator.prompt_cache import PromptCache

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"
TAGS = {"positive_prompt": "1girl, blue jacket, gold buttons", "negative_prompt": "blurry"}
NATURAL = {"positive_prompt": "A woman wears a blue jacket.", "negative_prompt": "Avoid blur."}
SPEC = {"azimuth": "front_left", "elevation": "low", "shot_size": "full", "lens": "wide", "roll": "level"}


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()

    def test_spec_is_sparse_validated_and_deterministic(self):
        self.assertEqual(camera.normalize(None), {})
        self.assertEqual(camera.normalize(SPEC), SPEC)
        self.assertIn("from below", camera.clauses(SPEC, "tags"))
        for invalid in ({"lens": "unknown"}, {"roll": []}, {"pitch": "low"}, [], False):
            with self.assertRaises(core.OrchestratorError):
                camera.normalize(invalid)
        with self.assertRaises(core.OrchestratorError):
            camera.split({camera.KEY: SPEC}, {core.H3_I2V_ID})
        tags = camera.apply_pair(TAGS, SPEC, "tags")
        self.assertEqual(camera.apply_pair(tags, SPEC, "tags"), tags)
        self.assertEqual(tags["negative_prompt"], TAGS["negative_prompt"])
        self.assertEqual(camera.apply_pair(TAGS, {}, "tags"), TAGS)
        light = {"positive_prompt": "1girl, lighting from below", "negative_prompt": ""}
        self.assertTrue(camera.apply_pair(light, {"elevation":"low"}, "tags")["positive_prompt"].endswith(", from below"))

    def test_replacing_explicit_angle_removes_old_host_term_not_lighting(self):
        old = {"elevation":"low"}
        new = {"elevation":"high"}
        values = {"positive_prompt": "1girl, lighting from below, from below, jacket", "negative_prompt": ""}
        updated = camera.remove_superseded(values, old, new, "tags")
        self.assertEqual(updated["positive_prompt"], "1girl, lighting from below, jacket")
        self.assertIn("from above", camera.apply_pair(updated, new, "tags")["positive_prompt"])
        natural = camera.apply_pair(NATURAL, old, "natural")
        clean = camera.remove_superseded(natural, old, new, "natural")
        self.assertEqual(clean, NATURAL)

    def test_projection_changes_by_camera_and_all_presets_are_clipped(self):
        base = camera_preview.segments({}, 320, 420)
        self.assertTrue(base)
        for field, choices in camera.OPTIONS.items():
            for key in choices:
                spec = {field: key}
                lines = camera_preview.segments(spec, 320, 420)
                self.assertTrue(lines, (field,key))
                for kind,x,y,u,v in lines:
                    self.assertIn(kind, {"grid","body","front"})
                    self.assertTrue(-1e-7 <= min(x,u) <= max(x,u) <= 320+1e-7)
                    self.assertTrue(-1e-7 <= min(y,v) <= max(y,v) <= 420+1e-7)
        for spec in ({"azimuth":"left"},{"elevation":"high"},{"shot_size":"bust"},
                     {"lens":"wide"},{"roll":"right"}):
            self.assertNotEqual(camera_preview.segments(spec,320,420),base)

    def test_core_compiles_both_formats_and_exact_replay(self):
        plan = {"workflow_id": ANIMA_ID, "parameters": TAGS, image_prompts.ALT: NATURAL}
        settings_seen = []
        def interpret(client, *args, **kwargs):
            settings_seen.append(client.settings)
            return plan
        with patch.object(lmstudio.LMStudio, "interpret", autospec=True, side_effect=interpret) as infer, \
                patch.object(core, "ComfyUI") as factory:
            comfy = factory.return_value
            comfy.submit.return_value = "id"
            comfy.wait.return_value = {"outputs": {}}
            result = core.execute(self.config, CONFIG, "窓際の人物", selected_workflow=ANIMA_ID,
                                  overrides={camera.KEY: SPEC, "seed": 12})
            params = result["parameters"]
            self.assertEqual(settings_seen[0]["_camera_spec"], SPEC)
            self.assertEqual(params[camera.KEY], SPEC)
            for fmt, pair in params[image_prompts.KEY]["prompts"].items():
                for term in camera.clauses(SPEC, fmt):
                    self.assertIn(term, pair["positive_prompt"])
            graph = comfy.submit.call_args.args[0]
            self.assertEqual(graph["6"]["inputs"]["text"], params["positive_prompt"])
            replay = core.execute_saved(self.config, CONFIG, ANIMA_ID, params)
            self.assertEqual(replay["parameters"], params)
            self.assertEqual(comfy.submit.call_args.args[0], graph)
            infer.assert_called_once()
        history = HistoryStore(self.root)
        image = history.outputs / "camera.png"
        image.write_bytes(b"test")
        entry = history.record(prompt_id="camera", workflow_id=ANIMA_ID, kind="t2i",
                               request_text="窓際の人物", parameters=params, images=[image])
        self.assertEqual(history_prompt_details(entry)[camera.KEY], SPEC)

    def test_camera_cache_is_separate_and_prompt_is_not_duplicated(self):
        plan = {"workflow_id": WAI_ID, "parameters": TAGS, image_prompts.ALT: NATURAL}
        cache = PromptCache(self.root / "plans.sqlite3")
        with patch.object(lmstudio.LMStudio, "interpret", return_value=plan) as infer, \
                patch.object(core, "ComfyUI"):
            def generate(spec, seed):
                return core.execute(self.config, CONFIG, "test", selected_workflow=WAI_ID, dry_run=True,
                                    overrides={camera.KEY: spec, "seed": seed}, prompt_cache=cache)["parameters"]
            a = generate(SPEC,1)
            b = generate(SPEC,2)
            c = generate({"elevation":"high"},1)
        self.assertEqual(infer.call_count,2)
        self.assertEqual(a["positive_prompt"], b["positive_prompt"])
        self.assertNotEqual(a["positive_prompt"], c["positive_prompt"])
        self.assertEqual(a["positive_prompt"].count("from below"),1)

    def test_comparison_reuses_camera_and_checks_matching_intent(self):
        workflows = self.config["workflows"]
        choices = (ImageModelChoice("WAI",WAI_ID,core.DEFAULT_SDXL_CHECKPOINT),
                   ImageModelChoice("Anima",ANIMA_ID,"anima-base-v1.0.safetensors"),
                   ImageModelChoice("Qwen",QWEN_ID))
        targets = prepare_targets(workflows,choices,(),width=1024,height=768,seed=12,camera=SPEC)
        tags = camera.apply_pair(TAGS,SPEC,"tags")
        natural = camera.apply_pair(NATURAL,SPEC,"natural")
        source = {"workflow_id":ANIMA_ID,
                  "parameters":image_prompts.bind_bundle(ANIMA_ID,{**tags,camera.KEY:SPEC},natural)}
        prepared = project_prompt_pair(source,targets,workflows)
        for t,p in zip(targets,prepared):
            self.assertEqual(p[camera.KEY],SPEC)
            self.assertEqual(p[image_prompts.KEY]["prompts"],{"tags":tags,"natural":natural})
        targets[0]["overrides"][camera.KEY]={"roll":"right"}
        with self.assertRaises(core.OrchestratorError):
            project_prompt_pair(source,targets,workflows)

    def test_adjustment_keeps_camera_on_model_switch_and_invalidates_manual_edit(self):
        store = HistoryStore(self.root)
        image = store.outputs / "source.png"
        image.write_bytes(b"image")
        tags = camera.apply_pair(TAGS,SPEC,"tags")
        natural = camera.apply_pair(NATURAL,SPEC,"natural")
        params = image_prompts.bind_bundle(WAI_ID,{**tags,camera.KEY:SPEC,"seed":12},natural)
        entry = store.record(prompt_id="source",workflow_id=WAI_ID,kind="t2i",
                             request_text="人物",parameters=params,images=[image])
        draft = ImageAdjustDraft.from_history(Mock(config=self.config,cancel_event=None),entry)
        self.addCleanup(draft.close)
        draft.switch_t2i(QWEN_ID)
        self.assertEqual(draft.parameters[camera.KEY],SPEC)
        self.assertEqual(draft.english(),natural)
        numeric = {k:str(draft.parameters[k]) for k in draft.numeric_fields}
        draft.apply_edits(draft.english(),numeric)
        self.assertEqual(draft.parameters[camera.KEY],SPEC)
        draft.apply_edits({**draft.english(),"positive_prompt":"new view"},numeric)
        self.assertNotIn(camera.KEY,draft.parameters)

    def test_camera_only_change_is_atomic_and_removes_old_clauses(self):
        store = HistoryStore(self.root)
        image = store.outputs / "source.png"
        image.write_bytes(b"image")
        old = {"elevation":"low"}
        new = {"elevation":"high"}
        tags = camera.apply_pair(TAGS,old,"tags")
        natural = camera.apply_pair(NATURAL,old,"natural")
        params = image_prompts.bind_bundle(WAI_ID,{**tags,camera.KEY:old,"seed":12},natural)
        entry = store.record(prompt_id="source",workflow_id=WAI_ID,kind="t2i",
                             request_text="人物",parameters=params,images=[image])
        draft = ImageAdjustDraft.from_history(Mock(config=self.config,cancel_event=None),entry)
        self.addCleanup(draft.close)
        def reply(client, instance, system, payload, schema, name, validate, *args, **kwargs):
            self.assertIn("CAMERA-ONLY CHANGE",system)
            return validate({"edits":[]})
        with patch.object(draft,"_session",side_effect=lambda action:action(None,None)), \
                patch.object(image_prompts,"request_validated",side_effect=reply):
            draft.revise_camera(new)
        self.assertEqual(draft.parameters[camera.KEY],new)
        self.assertIn("blue jacket",draft.parameters["positive_prompt"])
        self.assertIn("from above",draft.parameters["positive_prompt"])
        self.assertNotIn("from below",draft.parameters["positive_prompt"])
        before = draft.parameters["positive_prompt"]
        draft.revise_camera({})
        self.assertNotIn(camera.KEY,draft.parameters)
        self.assertEqual(draft.parameters["positive_prompt"],before)


if __name__ == "__main__":
    unittest.main()
