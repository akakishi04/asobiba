"""Continuous prompt planning and durable execution regressions."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    LongVideoPaused, LongVideoStore, planned_segment_parameters, run_long_video, segment_plan,
)
from comfy_orchestrator.timeline import (
    plan_long_prompts, prompt_for_segment, segment_windows, validate_prompt_plan,
)


class TimelineTests(unittest.TestCase):
    def test_windows_exclude_overlap_and_tail(self):
        for seconds in (30, 60, 300):
            frames = segment_plan(seconds, 124)
            windows = segment_windows(frames, seconds)
            self.assertEqual(windows[0]["start_frame"], 0)
            self.assertEqual(windows[-1]["end_frame"], seconds * 24)
            for i, w in enumerate(windows):
                self.assertLessEqual(w["end_frame"] - w["start_frame"], frames[i] - int(i > 0))
                if i:
                    self.assertEqual(w["start_frame"], windows[i - 1]["end_frame"])

    def test_validation_and_per_segment_prompt(self):
        plan = validate_prompt_plan({"common": "Same person.", "segments": ["Stand.", "Walk."]}, 2)
        self.assertEqual(prompt_for_segment(plan, 0), "Same person. Stand.")
        self.assertIn("Same person. Walk.", prompt_for_segment(plan, 1))
        self.assertNotIn("Stand.", prompt_for_segment(plan, 1))
        for bad in ({"common": "", "segments": ["one"]},
                    {"common": "", "segments": ["one", ""]},
                    {"common": "", "segments": ["one", "two"], "extra": 1}):
            with self.assertRaises(core.OrchestratorError):
                validate_prompt_plan(bad, 2)

    def test_hybrid_marker_only_on_first_and_seed_boundary(self):
        model = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors",
                                        reference_only=True)
        base = {"h3_model": model, "seed": core.PARAMS["seed"][2]}
        plan = {"common": "Same character.", "segments": ["Stand.", "Walk."]}
        first = planned_segment_parameters(base, plan, 0, 124)
        later = planned_segment_parameters(base, plan, 1, 107)
        self.assertIn("<Picture 1>", first["positive_prompt"])
        self.assertNotIn("<Picture 1>", later["positive_prompt"])
        self.assertTrue(later["h3_model"].startswith("hybrid_i2v:"))
        self.assertEqual(later["seed"], 0)

    def test_one_llm_request_and_no_visual_input(self):
        frames = segment_plan(30, 124)
        config = {"llm": {"model": "test", "send_reference_to_llm": True},
                  "comfyui": {"free_before_llm": False},
                  "workflows": {core.H3_I2V_ID: {"kind": "i2v"}}}
        plan = {"common": "Same style.", "segments": ["Move."] * len(frames)}
        response = {"choices": [{"message": {"content": json.dumps(plan)}}]}
        with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="instance"), \
                patch.object(lmstudio, "_request", side_effect=[response, {"instance_id": "instance"}]) as req:
            result = plan_long_prompts(config, "動く", frames, 30)
        self.assertEqual(result, plan)
        self.assertEqual([c.args[1] for c in req.call_args_list],
                         ["/v1/chat/completions", "/api/v1/models/unload"])
        self.assertFalse(req.call_args_list[0].args[0]["send_reference_to_llm"])
        self.assertIsInstance(req.call_args_list[0].args[2]["messages"][1]["content"], str)

    def test_empty_request_needs_no_llm(self):
        frames = segment_plan(30, 124)
        with patch.object(lmstudio.LMStudio, "_ensure_loaded") as load:
            result = plan_long_prompts({}, "", frames, 30)
        self.assertEqual(len(result["segments"]), len(frames))
        load.assert_not_called()

    def test_approved_plan_persists_and_resume_uses_only_approved_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"image")
            store = LongVideoStore(root / "long")
            journal = JobJournal(root / "jobs")
            params = {"width": 864, "height": 480, "frames": 124, "fps": 24,
                      "steps": 8, "seed": 7, "h3_model": "w4a8", "h3_turbo": "turbo8"}
            frames = segment_plan(30, 124)
            plan = {"common": "Same person.", "segments": [f"Action {i}." for i in range(len(frames))]}
            backend = "http://localhost:8188"
            manifest = store.create(backend, "original", source, params, 30, prompt_plan=plan)
            plan["segments"][0] = "not approved"
            config = {"comfyui": {"base_url": backend}}
            media = Mock()
            info = {}
            media.last_frame.side_effect = lambda clip, count, target, event: target.write_bytes(b"frame")
            media.probe.side_effect = lambda path, event: info[path.resolve()]
            media.join.side_effect = lambda clips, count, output, event, progress: output.write_bytes(b"joined")
            stop = threading.Event()
            sent = []
            interrupted = False

            def execute(cfg, path, workflow, parameters, **kw):
                nonlocal interrupted
                index = kw["job_context"]["long_segment"]
                if index == 1 and not interrupted:
                    interrupted = True
                    raise LongVideoPaused("stop")
                sent.append((index, parameters.copy()))
                record = journal.create(backend, workflow, "i2v", parameters, {}, kw["job_context"])
                journal.update(record["job_id"], state="completed", outputs={})
                return {"parameters": parameters, "prompt_id": record["prompt_id"],
                        "job_id": record["job_id"], "outputs": {}}

            def download(result, directory):
                clip = directory / "clip.mp4"
                clip.write_bytes(b"video")
                info[clip.resolve()] = {"frames": result["parameters"]["frames"],
                                        "width": 864, "height": 480, "fps": 24, "audio": True}
                return clip

            with patch.object(core, "ComfyUI", return_value=Mock(base=backend)), \
                    patch.object(core, "execute") as interpret, \
                    patch.object(core, "execute_saved", side_effect=execute):
                with self.assertRaises(LongVideoPaused):
                    run_long_video(store, manifest, config, root / "config.json", journal,
                                   root, download, cancel_event=stop, media=media)
                loaded = store.load(store.folder(manifest["run_id"]) / "manifest.json")
                result, output = run_long_video(store, loaded, config, root / "config.json", journal,
                                                root, download, cancel_event=stop, media=media)
                interpret.assert_not_called()
            self.assertTrue(output.exists())
            self.assertEqual(result["parameters"]["frames"], 720)
            self.assertEqual([i for i, _ in sent], list(range(len(frames))))
            for i, p in sent:
                self.assertIn(f"Action {i}.", p["positive_prompt"])
                self.assertEqual(p["seed"], 7 + i)
                self.assertEqual(p["frames"], frames[i])
            self.assertNotIn("not approved", sent[0][1]["positive_prompt"])


if __name__ == "__main__":
    unittest.main()
