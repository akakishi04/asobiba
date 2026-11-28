"""Persistent project revisions, offline joining and batched planning."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    LongVideoStore, edit_project, project_cut_lengths, first_changed_cut,
    run_long_video, manifest_schedule,
)
from comfy_orchestrator.timeline import plan_long_prompts, generation_frames_for_cuts


class ProjectTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / "ref.png"
        self.source.write_bytes(b"source")
        self.store = LongVideoStore(self.root / "projects")
        self.journal = JobJournal(self.root / "jobs")
        self.backend = "http://localhost:8188"
        self.params = {"width": 864, "height": 480, "fps": 24, "frames": 124,
                       "steps": 8, "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}
        self.cuts = [72, 120, 192]
        self.plan = {"common": "same character", "segments": ["Stand.", "Walk.", "Look."]}
        self.manifest = self.store.create(self.backend, "walk", self.source, self.params, 16,
                                         prompt_plan=self.plan, cut_frames=self.cuts, draft=True)

    def add_saved(self, count):
        folder = self.store.folder(self.manifest["run_id"])
        for i in range(count):
            path = folder / f"segment_{i:03d}" / "clip.mp4"
            path.parent.mkdir()
            path.write_bytes(f"clip{i}".encode())
            params = {**self.params, "frames": self.manifest["plan"][i],
                      "positive_prompt": self.plan["segments"][i], "seed": 11 + i}
            self.manifest["segments"].append({"file": path.relative_to(folder).as_posix(),
                "job_id": f"job{i}", "prompt_id": f"prompt{i}", "parameters": params,
                "frames": params["frames"]})
            if i == 0:
                self.manifest["first_parameters"] = params
        self.store.save(self.manifest)

    def test_draft_survives_restart_and_noop_keeps_run_id(self):
        loaded = self.store.projects()[0]
        self.assertEqual(loaded["state"], "draft")
        self.assertEqual(loaded["prompt_plan"], self.plan)
        self.assertEqual(project_cut_lengths(loaded), self.cuts)
        self.assertEqual(edit_project(self.store, loaded, self.journal, self.plan, self.cuts)["run_id"],
                         loaded["run_id"])

    def test_edit_invalidates_suffix_and_preserves_old_project(self):
        self.add_saved(3)
        approved = {"common": self.plan["common"], "segments": ["Stand.", "Run.", "Look."]}
        cuts = [72, 144, 192]
        self.assertEqual(first_changed_cut(self.manifest, approved, cuts), 1)
        revised = edit_project(self.store, self.manifest, self.journal, approved, cuts)
        self.assertNotEqual(revised["run_id"], self.manifest["run_id"])
        self.assertEqual(revised["parent_run_id"], self.manifest["run_id"])
        self.assertEqual(len(revised["segments"]), 1)
        self.assertEqual(revised["first_parameters"], self.manifest["first_parameters"])
        self.assertEqual(self.store.asset(revised, revised["segments"][0]["file"]).read_bytes(), b"clip0")
        self.assertEqual(len(self.store.load(self.store.folder(self.manifest["run_id"]) / "manifest.json")["segments"]), 3)
        self.assertEqual(manifest_schedule(revised)[2], sum(cuts))
        self.assertEqual(len(self.store.projects()), 2)

    def test_common_change_invalidates_all_and_regeneration_changes_seed(self):
        self.add_saved(2)
        common_edit = {"common": "new character", "segments": self.plan["segments"]}
        with patch("comfy_orchestrator.project_store.secrets.randbits", return_value=99):
            revised = edit_project(self.store, self.manifest, self.journal,
                                   common_edit, self.cuts, regenerate_from=1)
        self.assertEqual(revised["segments"], [])
        self.assertIsNone(revised["first_parameters"])
        self.assertEqual(revised["cut_seeds"], [11, 99, 99])

    def test_unresolved_remote_job_blocks_revision(self):
        row = self.journal.create(self.backend, core.H3_I2V_ID, "i2v", {}, {},
                                  {"long_run_id": self.manifest["run_id"], "long_segment": 0})
        self.journal.update(row["job_id"], state="unknown")
        with self.assertRaisesRegex(core.OrchestratorError, "未確定"):
            edit_project(self.store, self.manifest, self.journal, self.plan, self.cuts, regenerate_from=0)
        self.assertEqual(len(self.store.projects()), 1)

    def test_revision_generates_only_suffix_and_never_reuses_old_job(self):
        self.add_saved(3)
        old = self.journal.create(self.backend, core.H3_I2V_ID, "i2v", {}, {},
                                  {"long_run_id": self.manifest["run_id"], "long_segment": 1})
        self.journal.update(old["job_id"], state="completed", outputs={})
        approved = {"common": self.plan["common"], "segments": ["Stand.", "Run.", "Look."]}
        revised = edit_project(self.store, self.manifest, self.journal, approved, self.cuts,
                               regenerate_from=1)
        media = Mock()
        counts = {self.store.asset(revised, x["file"]): x["frames"] for x in revised["segments"]}
        media.probe.side_effect = lambda path, event: {"frames": counts[path], "fps": 24,
                                                        "width": 864, "height": 480, "audio": True}
        media.last_frame.side_effect = lambda clip, frames, target, event: target.write_bytes(b"anchor")
        seen = []

        def execute(cfg, path, workflow, params, **kw):
            i = kw["job_context"]["long_segment"]
            seen.append((i, params["positive_prompt"], params["seed"]))
            row = self.journal.create(self.backend, workflow, "i2v", params, {}, kw["job_context"])
            self.journal.update(row["job_id"], state="completed", outputs={})
            return {"job_id": row["job_id"], "prompt_id": row["prompt_id"], "parameters": params, "outputs": {}}

        def download(result, directory):
            path = directory / "new.mp4"
            path.write_bytes(b"new")
            counts[path.resolve()] = result["parameters"]["frames"]
            return path

        with patch.object(core, "ComfyUI", return_value=Mock(base=self.backend)), \
                patch.object(core, "execute_saved", side_effect=execute):
            run_long_video(self.store, revised, {"comfyui": {"base_url": self.backend}},
                           self.root / "config.json", self.journal, self.root, download,
                           media=media, auto_join=False)
        self.assertEqual([i for i, _, _ in seen], [1, 2])
        self.assertIn("Run.", seen[0][1])
        self.assertEqual([seed for _, _, seed in seen], revised["cut_seeds"][1:])
        self.assertEqual(self.store.asset(revised, revised["segments"][0]["file"]).read_bytes(), b"clip0")
        self.assertEqual(self.journal.read(old["job_id"])["state"], "completed")

    def test_join_only_never_calls_backend(self):
        self.add_saved(3)
        media = Mock()
        counts = {self.store.asset(self.manifest, x["file"]): x["frames"] for x in self.manifest["segments"]}
        media.probe.side_effect = lambda path, event: {"frames": counts[path], "fps": 24,
                                                        "width": 864, "height": 480, "audio": True}
        media.join.side_effect = lambda clips, count, path, event, progress, **kw: path.write_bytes(b"joined")
        config = {"comfyui": {"base_url": "http://other:8188"}}
        with patch.object(core, "ComfyUI") as comfy, patch.object(core, "execute_saved") as execute:
            result, out = run_long_video(self.store, self.manifest, config, self.root / "config.json",
                                        self.journal, self.root, Mock(), media=media, join_only=True)
        comfy.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(out.read_bytes(), b"joined")
        self.assertEqual(result["parameters"]["long_prompt_plan"], self.plan)
        self.assertEqual(media.join.call_args.kwargs["keep_frames"], self.cuts)

    def test_join_rejects_incomplete_project(self):
        with patch.object(core, "ComfyUI") as comfy:
            with self.assertRaisesRegex(core.OrchestratorError, "全カット"):
                run_long_video(self.store, self.manifest, {"comfyui": {"base_url": self.backend}},
                               self.root / "config.json", self.journal, self.root, Mock(),
                               media=Mock(), join_only=True)
        comfy.assert_not_called()

    def test_generate_without_join_uses_saved_prefix(self):
        self.add_saved(3)
        media = Mock()
        counts = {self.store.asset(self.manifest, x["file"]): x["frames"] for x in self.manifest["segments"]}
        media.probe.side_effect = lambda path, event: {"frames": counts[path], "fps": 24,
                                                        "width": 864, "height": 480, "audio": True}
        with patch.object(core, "ComfyUI"), patch.object(core, "execute_saved") as execute:
            result = run_long_video(self.store, self.manifest, {"comfyui": {"base_url": self.backend}},
                                    self.root / "config.json", self.journal, self.root, Mock(),
                                    media=media, auto_join=False)
        self.assertEqual(result, (None, None))
        self.assertEqual(self.manifest["state"], "ready_to_join")
        execute.assert_not_called()
        media.join.assert_not_called()


class BatchPlanningTests(unittest.TestCase):
    def test_outline_and_detail_batches_share_one_model_session(self):
        cuts = [24] * 25
        frames = generation_frames_for_cuts(cuts)
        cfg = {"llm": {"model": "test", "max_tokens": 4096, "context_length": 8192},
               "comfyui": {"free_before_llm": False},
               "workflows": {core.H3_I2V_ID: {"kind": "i2v"}}}
        calls = []
        def respond(settings, route, body):
            calls.append(route)
            if route == "/api/v1/models/unload":
                return {"instance_id": "instance"}
            self.assertNotIn("max_tokens", body)
            data = json.loads(body["messages"][1]["content"])
            name = body["response_format"]["json_schema"]["name"]
            if name == "continuous_outline":
                reply = {"common": "Same scene.", "segments": ["Stage."] * len(data["timeline_groups"])}
            else:
                self.assertEqual(data["common"], "Same scene.")
                reply = {"segments": [f'Action {w["index"]}.' for w in data["timeline"]]}
            return {"choices": [{"message": {"content": json.dumps(reply)}}]}
        with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="instance") as load, \
                patch.object(lmstudio, "_request", side_effect=respond):
            plan = plan_long_prompts(cfg, "walk", frames, 25, cut_frames=cuts)
        load.assert_called_once()
        self.assertEqual(calls.count("/api/v1/models/unload"), 1)
        self.assertEqual(calls.count("/v1/chat/completions"), 4)
        self.assertEqual(plan["segments"], [f"Action {i}." for i in range(1, 26)])


if __name__ == "__main__":
    unittest.main()
