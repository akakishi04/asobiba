"""H3 official prompt structure, capability-aware vision and continuous timing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui, h3_prompt as hp, lmstudio
from comfy_orchestrator.long_video import LongVideoStore, planned_segment_parameters, edit_project
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.timeline import plan_long_prompts, generation_frames_for_cuts, validate_prompt_plan
from comfy_orchestrator.project_ui import ProjectDraft
from comfy_orchestrator.prompt_cache import PromptCache

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
BACKEND = "http://localhost:8188"


def reply(value):
    return {"choices": [{"message": {"content": json.dumps(value, ensure_ascii=False)}}]}


def base(body="[Shot 1] A drawn character lifts her gaze. The camera holds a static shot."):
    return {"integrated_multimodal_description": body,
            "overall_soundscape": "Soft fabric movement and quiet ambience.",
            "non_diegetic_music": "N/A"}


class H3OfficialPromptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = core.load_config(CONFIG)
        self.config["llm"].update(model="test", unload_after_inference=False)
        self.source = self.root / "image.png"
        self.source.write_bytes(b"example")
        self.workflows = {core.H3_I2V_ID: self.config["workflows"][core.H3_I2V_ID]}

    def test_exact_base_and_ref_sections_and_dialogue(self):
        spoken = "もう帰ろうか。"
        fields = base(f"[Shot 1] The woman (S1) says: <d>[Japanese] {spoken}</d>")
        text = hp.compile_prompt(fields, False, kept_frames=124)
        self.assertTrue(text.startswith(hp.I2VA_HEADER + "\n\nintegrated_multimodal_description: [Shot 1]"))
        self.assertIn(f"<d>[Japanese] {spoken}</d>", text)
        self.assertTrue(text.endswith("non_diegetic_music: N/A"))
        ref = hp.compile_prompt(hp.default_sections(True), True)
        self.assertFalse(ref.startswith(hp.I2VA_HEADER))
        self.assertEqual(tuple(m.group(1) for m in hp.HEADINGS.finditer(ref)), hp.REF_FIELDS)
        self.assertIn("<Picture 1>", ref)
        self.assertIn("fully_preserved", ref)

    def test_validation_rejects_out_of_range_shots_and_fake_assets(self):
        cases = [
            base("[Shot 1] A person turns. [Shot 2] At 00:05.000, the view changes."),
            base("[Shot 1] A person turns. [Shot 3] At 00:01.000, the view changes."),
            base("[Shot 1] A person turns. [Shot 2] At 00:01.000, the view changes. [Shot 3] At 00:00.500, the view changes."),
            base("[Shot 1] A person says: <d>Hi</d>"),
            base("[Shot 1] Copy <Video 1>."),
        ]
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(core.OrchestratorError):
                hp.compile_prompt(fields, False, kept_frames=120)
        ref = hp.default_sections(True)
        ref["detailed_description"] += " <Subject 2> enters."
        with self.assertRaises(core.OrchestratorError):
            hp.compile_prompt(ref, True)

    def test_single_vision_observes_once_and_compiles_in_core(self):
        calls = []
        observation = {name: "visible blue coat" if name == "appearance" else "unknown" for name in hp.OBS_FIELDS}
        def request(settings, route, payload=None):
            calls.append((route, payload))
            if route == "/v1/chat/completions":
                name = payload["response_format"]["json_schema"]["name"]
                return reply(observation if name == "h3_visual_observation" else base())
            raise AssertionError(route)
        catalog = [{"key": "test", "capabilities": {"vision": True}, "loaded_instances": [{"id": "instance"}]}]
        with patch.object(lmstudio, "list_models", return_value=catalog), patch.object(lmstudio, "_request", side_effect=request):
            result = core.execute(self.config, CONFIG, "顔を上げる", image=self.source,
                                  selected_workflow=core.H3_I2V_ID, dry_run=True)
        self.assertEqual(len(calls), 2)
        vision, rewrite = [payload for route, payload in calls]
        self.assertEqual(vision["messages"][1]["content"][1]["type"], "image_url")
        self.assertIn("visible blue coat", rewrite["messages"][1]["content"])
        self.assertIn("ILLUSTRATION PRESERVATION", rewrite["messages"][0]["content"])
        self.assertEqual(result["parameters"]["positive_prompt"], hp.compile_prompt(base(), False))

    def test_text_model_stays_text_only_and_invalid_reply_repairs_once(self):
        calls, logs = [], []
        catalog = [{"key": "test", "capabilities": {"vision": False}, "loaded_instances": [{"id": "instance"}]}]
        def request(settings, route, payload=None):
            calls.append(payload)
            return reply({"bad": "wrong"} if len(calls) == 1 else base())
        with patch.object(lmstudio, "list_models", return_value=catalog), patch.object(lmstudio, "_request", side_effect=request):
            result = lmstudio.LMStudio(self.config["llm"]).interpret("動く", self.workflows, self.source, progress=logs.append)
        self.assertEqual(len(calls), 2)
        self.assertIn("Validation error", calls[1]["messages"][0]["content"])
        self.assertTrue(all(isinstance(p["messages"][1]["content"], str) for p in calls))
        self.assertTrue(any("自然文のみ" in line for line in logs))
        self.assertTrue(result["parameters"]["positive_prompt"].startswith(hp.I2VA_HEADER))

    def test_empty_request_never_loads_llm(self):
        with patch.object(lmstudio.LMStudio, "interpret") as interpret:
            result = core.execute(self.config, CONFIG, "", image=self.source,
                                  selected_workflow=core.H3_I2V_ID, dry_run=True)
        interpret.assert_not_called()
        self.assertEqual(result["parameters"]["positive_prompt"], hp.compile_prompt(hp.default_sections(False), False))

    def test_long_ref_then_base_guide_and_legacy_project_compatibility(self):
        cuts = [72, 96, 120]
        frames = generation_frames_for_cuts(cuts)
        first = hp.default_sections(True)
        following = base("[Shot 1] The character moves. [Shot 2] At 00:01.000, the shot cuts to a close-up.")
        answer = {"common": "Consistent painted linework.", "segments": {"cut_1": first, "cut_2": following, "cut_3": base()}}
        catalog = [{"key": "test", "capabilities": {"vision": False}, "loaded_instances": [{"id": "instance"}]}]
        with patch.object(lmstudio, "list_models", return_value=catalog), patch.object(lmstudio, "_request", return_value=reply(answer)) as req:
            plan = plan_long_prompts(self.config, "歩く", frames, sum(cuts)/24, True,
                                     cut_frames=cuts, overlap_frames=22, image=self.source, release_comfy=False)
        req.assert_called_once()
        schema = req.call_args.args[2]["response_format"]["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]["segments"]["properties"]["cut_1"]["required"]), set(hp.REF_FIELDS))
        self.assertEqual(set(schema["properties"]["segments"]["properties"]["cut_2"]["required"]), set(hp.BASE_FIELDS))
        self.assertEqual(plan["format"], hp.FORMAT)
        model = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors", reference_only=True)
        overrides = {"width": 864, "height": 480, "fps": 24, "frames": 124,
                     "steps": 8, "seed": 11, "h3_model": model, "h3_turbo": "off"}
        store = LongVideoStore(self.root / "projects")
        manifest = store.create(BACKEND, "walk", self.source, overrides, sum(cuts)/24,
                                prompt_plan=plan, cut_frames=cuts, overlap_frames=22, draft=True)
        loaded = store.load(store.folder(manifest["run_id"]) / "manifest.json")
        draft = ProjectDraft(loaded)
        self.assertEqual(draft.action("save").prompt_plan, plan)
        self.assertFalse(draft.dirty())
        first_prompt = planned_segment_parameters(overrides, plan, 0, manifest["plan"][0], kept_frames=72)["positive_prompt"]
        self.assertTrue(first_prompt.startswith("subject_definitions:"))
        second = planned_segment_parameters(overrides, plan, 1, manifest["plan"][1], kept_frames=96,
                                            lead_in_frames=22, guide_frames=22)["positive_prompt"]
        self.assertTrue(second.startswith("integrated_multimodal_description: [Shot 1]"))
        self.assertNotIn("<Picture 1>", second)
        self.assertNotIn("<Video 1>", second)
        self.assertIn("[Shot 2] At 00:01.917,", second)
        self.assertIn("Consistent painted linework.", second)
        with self.assertRaises(core.OrchestratorError):
            edit_project(store, manifest, JobJournal(self.root / "jobs"), plan, [72, 24, 120])
        legacy = {"common": "Same style.", "segments": ["Move.", "Turn."]}
        self.assertEqual(validate_prompt_plan(legacy, 2), legacy)

    def test_long_cache_uses_image_content_and_mode(self):
        cache = PromptCache(self.root / "cache.sqlite3")
        cuts = [72, 96]
        frames = generation_frames_for_cuts(cuts)
        answer = {"common": "", "segments": {"cut_1": base(), "cut_2": base()}}
        catalog = [{"key": "test", "capabilities": {"vision": False}, "loaded_instances": [{"id": "instance"}]}]
        def plan():
            return plan_long_prompts(self.config, "歩く", frames, sum(cuts)/24,
                                     cut_frames=cuts, overlap_frames=22, image=self.source,
                                     release_comfy=False, prompt_cache=cache)
        with patch.object(lmstudio, "list_models", return_value=catalog), patch.object(lmstudio, "_request", return_value=reply(answer)) as req:
            self.assertEqual(plan(), plan())
            self.assertEqual(req.call_count, 1)
            self.source.write_bytes(b"different")
            plan()
            self.assertEqual(req.call_count, 2)


if __name__ == "__main__":
    unittest.main()
