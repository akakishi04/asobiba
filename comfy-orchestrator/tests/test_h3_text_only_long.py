"""Text-only first cut: native H3 T2VA, persisted plan and guided continuation."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, h3_prompt as hp, lmstudio, generation_runtime
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    LongVideoStore, LongVideoPaused, long_generation_model, planned_segment_parameters,
    project_generation_inputs, restore_project_plan, run_long_video, edit_project,
)
from comfy_orchestrator.timeline import generation_frames_for_cuts, plan_long_prompts
from comfy_orchestrator.prompt_edit import cut_context
from comfy_orchestrator.prompt_cache import PromptCache

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
BACKEND = "http://localhost:8188"
CUTS = [72, 96, 120]
PARAMS = {"width": 864, "height": 480, "fps": 24, "frames": 124, "steps": 8,
          "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}


def base(text):
    return {"integrated_multimodal_description": "[Shot 1] " + text,
            "overall_soundscape": "Soft rain.", "non_diegetic_music": "N/A"}


PLAN = {"format": hp.FORMAT, "common": "A woman with a pink umbrella.",
        "segments": [hp.section_text(base(text), False) for text in (
            "A painted city street. A woman walks under an open pink umbrella.",
            "She stops and lowers the umbrella.",
            "She closes the same umbrella.")]}


class TextOnlyLongTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.store = LongVideoStore(self.root / "projects")
        self.journal = JobJournal(self.root / "jobs")
        self.config = core.load_config(CONFIG)
        self.config["llm"].update(model="test", unload_after_inference=False)
        self.config["comfyui"].update(base_url=BACKEND, free_before_llm=False)

    def project(self, params=None):
        return self.store.create(BACKEND, "雨の街を歩く", None, params or PARAMS,
                                 sum(CUTS)/24, prompt_plan=PLAN, cut_frames=CUTS,
                                 overlap_frames=22, draft=True)

    def test_native_text_graph_without_upload_and_saved_image_requirement_unchanged(self):
        prompt = hp.compile_prompt(base("A woman walks through rain."), False, text_only=True)
        params = {**PARAMS, "positive_prompt": prompt}
        comfy = Mock(base=BACKEND)
        comfy.submit.side_effect = lambda graph, prompt_id: prompt_id
        comfy.wait.return_value = {"outputs": {}}
        with patch.object(core, "ComfyUI", return_value=comfy):
            with self.assertRaises(core.OrchestratorError):
                core.execute_saved(self.config, CONFIG, core.H3_I2V_ID, params)
            result = core.execute_saved(self.config, CONFIG, core.H3_I2V_ID, params,
                                        text_only_h3=True, job_journal=self.journal)
        graph = comfy.submit.call_args.args[0]
        comfy.upload_image.assert_not_called()
        self.assertNotIn("114", graph)
        self.assertEqual(graph["104"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertNotIn("first_frame", graph["104"]["inputs"])
        self.assertNotIn("last_frame", graph["104"]["inputs"])
        self.assertEqual(graph["104"]["inputs"]["prompt"], prompt)
        self.assertEqual(graph["14"]["inputs"]["latent_image"], ["104", 1])
        self.assertEqual(graph["91"]["inputs"]["audio"], ["23", 0])
        row = self.journal.read(result["job_id"])
        self.assertTrue(row["context"]["text_only_h3"])
        self.assertIsNone(row["context"]["reference_image"])

    def test_t2va_format_and_no_fake_picture_markers(self):
        text = hp.compile_prompt(base("A woman walks through rain."), False, text_only=True)
        self.assertTrue(text.startswith("integrated_multimodal_description: [Shot 1]"))
        self.assertNotIn(hp.I2VA_HEADER, text)
        self.assertNotIn("<Picture 1>", text)
        with self.assertRaises(core.OrchestratorError):
            hp.compile_prompt(base("A woman from <Picture 1> walks."), False, text_only=True)
        first = planned_segment_parameters(PARAMS, PLAN, 0, 107, text_only=True, kept_frames=72)
        second = planned_segment_parameters(PARAMS, PLAN, 1, 124, guide_frames=22,
                                            lead_in_frames=22, kept_frames=96)
        self.assertNotIn(hp.I2VA_HEADER, first["positive_prompt"])
        self.assertIn("preceding retained video guide", second["positive_prompt"])

    def test_hybrid_base_switch_and_preflight(self):
        model = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors",
                                        reference_only=True)
        p = {**PARAMS, "h3_model": model, "h3_turbo": "off"}
        manifest = self.project(p)
        expected = long_generation_model(p, text_only=True)
        self.assertEqual(manifest["overrides"], expected)
        self.assertTrue(expected["h3_model"].startswith("hybrid_i2v:"))
        with patch.object(generation_runtime, "ComfyUI") as factory:
            generation_runtime.preflight_long(self.config, CONFIG, expected,
                manifest["plan"], text_only_h3=True, guide_frame_count=22)
        graphs = [c.args[0] for c in factory.return_value.ensure_video_dependencies.call_args_list]
        self.assertEqual(len(graphs), 3)
        self.assertTrue(any("114" not in g and "first_frame" not in g["104"]["inputs"] for g in graphs))
        self.assertTrue(any(n["class_type"] == "MiniMaxH3AddGuide" for g in graphs for n in g.values()))

    def test_plan_text_only_has_distinct_mode_cache_and_no_vision(self):
        fields = [hp.parse_sections(part)[0] for part in PLAN["segments"]]
        answer = {"common": PLAN["common"], "segments": {f"cut_{i+1}": part for i, part in enumerate(fields)}}
        response = {"choices": [{"message": {"content": json.dumps(answer)}}]}
        catalog = [{"key": "test", "capabilities": {"vision": True}, "loaded_instances": [{"id": "instance"}]}]
        cache = PromptCache(self.root / "cache.sqlite3")
        frames = generation_frames_for_cuts(CUTS)
        with patch.object(lmstudio, "list_models", return_value=catalog), \
                patch.object(lmstudio, "_request", return_value=response) as req:
            result = plan_long_prompts(self.config, "雨の街を歩く", frames, sum(CUTS)/24,
                                       cut_frames=CUTS, overlap_frames=22, text_only=True,
                                       prompt_cache=cache)
            self.assertEqual(result, PLAN)
            payload = json.loads(req.call_args.args[2]["messages"][1]["content"])
            self.assertEqual(payload["first_reference_mode"], "T2VA")
            self.assertEqual([w["mode"] for w in payload["timeline"]], ["T2VA", "I2VA/base", "I2VA/base"])
            self.assertIsNone(payload["reference_observations"])
            self.assertIn("no source image", req.call_args.args[2]["messages"][0]["content"])
            plan_long_prompts(self.config, "雨の街を歩く", frames, sum(CUTS)/24,
                              cut_frames=CUTS, overlap_frames=22, text_only=True, prompt_cache=cache)
            req.assert_called_once()
            # The earlier I2VA API permits planning without a physical image;
            # that still has different prompt conditioning and a different key.
            plan_long_prompts(self.config, "雨の街を歩く", frames, sum(CUTS)/24,
                              cut_frames=CUTS, overlap_frames=22, prompt_cache=cache)
            self.assertEqual(req.call_count, 2)
        with self.assertRaises(core.OrchestratorError):
            plan_long_prompts(self.config, "", frames, sum(CUTS)/24, cut_frames=CUTS, text_only=True)

    def test_optional_source_persistence_and_revision(self):
        manifest = self.project()
        loaded = self.store.load(self.store.folder(manifest["run_id"]) / "manifest.json")
        self.assertIsNone(loaded["source"])
        self.assertIsNone(self.store.source_asset(loaded))
        self.assertTrue(cut_context(loaded, PLAN, CUTS, 0)["text_only"])
        self.assertFalse(cut_context(loaded, PLAN, CUTS, 1)["text_only"])
        self.assertEqual(project_generation_inputs(self.store, loaded, overrides=PARAMS),
                         (PARAMS, None, False))
        source = self.root / "image.png"
        source.write_bytes(b"reference")
        with self.assertRaises(core.OrchestratorError):
            project_generation_inputs(self.store, loaded, source=source)
        revised = edit_project(self.store, loaded, self.journal, PLAN, CUTS, regenerate_from=1)
        self.assertIsNone(revised["source"])
        self.assertEqual(revised["changed_from"], 1)
        with self.assertRaises(core.OrchestratorError):
            self.store.create(BACKEND, "", None, PARAMS, sum(CUTS)/24,
                              prompt_plan=PLAN, cut_frames=CUTS)

    def test_pause_resume_guides_and_history_restore_with_no_source(self):
        manifest = self.project()
        media = Mock()
        info, sent = {}, []
        interrupted = False

        def extract(clip, start, count, folder, event):
            frames = tuple(folder / f"frame_{i:03d}.png" for i in range(count))
            for image in frames:
                image.write_bytes(b"guide")
            return frames

        def execute(cfg, config_path, workflow, params, **kw):
            nonlocal interrupted
            i = kw["job_context"]["long_segment"]
            if i == 1 and not interrupted:
                interrupted = True
                raise LongVideoPaused("pause")
            sent.append((i, kw.get("text_only_h3", False),
                         kw["reference_image"] is None, len(kw.get("guide_images", ()))))
            row = self.journal.create(BACKEND, workflow, "i2v", params, {}, kw["job_context"])
            self.journal.update(row["job_id"], state="completed", outputs={})
            return {"parameters": params, "prompt_id": row["prompt_id"],
                    "job_id": row["job_id"], "outputs": {}}

        def download(result, directory):
            clip = directory / "clip.mp4"
            clip.write_bytes(b"video")
            info[clip.resolve()] = {"frames": result["parameters"]["frames"],
                                    "width": 864, "height": 480, "fps": 24, "audio": True}
            return clip

        media.extract_guide_frames.side_effect = extract
        media.probe.side_effect = lambda path, event: info[path.resolve()]
        media.join.side_effect = lambda clips, count, output, event, progress, **kw: output.write_bytes(b"joined")
        with patch.object(core, "ComfyUI", return_value=Mock(base=BACKEND)), \
                patch.object(core, "execute_saved", side_effect=execute), \
                patch.object(core, "execute") as interpret:
            with self.assertRaises(LongVideoPaused):
                run_long_video(self.store, manifest, self.config, CONFIG, self.journal,
                               self.root, download, media=media)
            loaded = self.store.load(self.store.folder(manifest["run_id"]) / "manifest.json")
            result, output = run_long_video(self.store, loaded, self.config, CONFIG, self.journal,
                                             self.root, download, media=media)
            interpret.assert_not_called()
        self.assertEqual(sent, [(0, True, True, 0), (1, False, False, 21), (2, False, False, 21)])
        self.assertEqual(media.join.call_args.kwargs["trim_start_frames"], [0, 22, 22])
        self.assertTrue(output.is_file())
        self.assertTrue(result["parameters"]["long_text_only"])
        restored = restore_project_plan(self.store, SimpleNamespace(
            parameters=result["parameters"], reference_image=None, request_text=manifest["request"],
            prompt_profile=None), BACKEND)
        self.assertIsNone(restored["source"])
        self.assertEqual(restored["prompt_plan"], PLAN)
        self.assertEqual(restored["cut_seeds"], [11, 12, 13])

    def test_request_error_reports_stage_without_retry(self):
        client = SimpleNamespace(settings={"max_tokens": 4096})
        with patch.object(lmstudio, "_request", side_effect=core.OrchestratorError("timeout")) as req:
            with self.assertRaisesRegex(core.OrchestratorError, "h3_japanese_review.*4096.*timeout"):
                hp._reply(client, "instance", "system", "text", {}, "h3_japanese_review", lambda v: v)
            req.assert_called_once()


if __name__ == "__main__":
    unittest.main()
