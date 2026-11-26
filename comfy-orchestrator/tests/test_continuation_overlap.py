"""Lead-in continuity, exact retained durations and safe legacy revisions."""
import array
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    FFmpeg, LongVideoPaused, LongVideoStore, continuation_anchor_count, edit_project,
    manifest_schedule, manifest_windows, project_cut_lengths, restore_project_plan,
    run_long_video, schedule_windows, segment_plan,
)
from comfy_orchestrator.timeline import generation_frames_for_cuts, plan_long_prompts


BACKEND = "http://localhost:8188"
CUTS = [72, 96, 120, 146]
PARAMS = {"width": 864, "height": 480, "fps": 24, "frames": 124,
          "steps": 8, "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}
PROMPTS = {"common": "Same subject.", "segments": ["A.", "B.", "C.", "D."]}


class OverlapTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.source = self.root / "ref.png"
        self.source.write_bytes(b"image")
        self.store = LongVideoStore(self.root / "projects")
        self.journal = JobJournal(self.root / "jobs")

    def create(self, *, overlap=12):
        return self.store.create(BACKEND, "walk", self.source, PARAMS, sum(CUTS) / 24,
                                 prompt_plan=PROMPTS, cut_frames=CUTS, draft=True,
                                 overlap_frames=overlap)

    def test_schedule_exact_duration_and_grid(self):
        windows = schedule_windows(sum(CUTS) / 24, 124, CUTS, overlap_frames=12)
        self.assertEqual([w["output_frames"] for w in windows], CUTS)
        self.assertEqual([w["trim_start_frames"] for w in windows], [0, 12, 12, 12])
        self.assertEqual([w["generation_frames"] for w in windows], [107, 124, 141, 158])
        self.assertEqual([continuation_anchor_count(windows[i-1], windows[i])
                          for i in range(1, 4)], [61, 97, 121])
        self.assertEqual(windows[-1]["end_frame"], 434)
        manifest = self.create()
        self.assertEqual(project_cut_lengths(manifest), CUTS)
        self.assertEqual(manifest_schedule(manifest)[2], 434)
        path = self.store.folder(manifest["run_id"]) / "manifest.json"
        self.assertEqual(self.store.load(path)["overlap_frames"], 12)
        bad = {**manifest, "plan": generation_frames_for_cuts(CUTS)}
        with self.assertRaises(core.OrchestratorError):
            manifest_schedule(bad)

    def test_preset_durations_and_maximum_frame_ceiling(self):
        for seconds in (30, 60, 120, 180, 300):
            for nominal in (107, 124, 192, 243, 294, 362):
                old = schedule_windows(seconds, nominal)
                new = schedule_windows(seconds, nominal, overlap_frames=12)
                self.assertEqual([w["output_frames"] for w in old], [w["output_frames"] for w in new])
                self.assertEqual(sum(w["output_frames"] for w in new), seconds * 24)
                for w in new:
                    n = w["generation_frames"]
                    self.assertTrue(107 <= n <= 362 and (n - 5) % 17 == 0)
                    self.assertLessEqual(w["output_frames"] + w["trim_start_frames"], n)
        maximum = schedule_windows(30, 362, [360, 360], overlap_frames=12)
        self.assertEqual([w["trim_start_frames"] for w in maximum], [0, 2])
        self.assertEqual([w["generation_frames"] for w in maximum], [362, 362])
        with self.assertRaises(core.OrchestratorError):
            schedule_windows(30, 124, overlap_frames=True)

    def test_legacy_and_revision_preserve_first_cut_and_seeds(self):
        old = self.create(overlap=0)
        folder = self.store.folder(old["run_id"])
        old["first_parameters"] = {**PARAMS, "frames": old["plan"][0], "positive_prompt": "Same subject. A."}
        for i in range(4):
            path = folder / f"segment_{i:03d}" / "clip.mp4"
            path.parent.mkdir()
            path.write_bytes(f"clip{i}".encode())
            old["segments"].append({"file": path.relative_to(folder).as_posix(),
                                    "parameters": {**PARAMS, "seed": 11 + i, "frames": old["plan"][i]}})
        old["state"] = "completed"
        self.store.save(old)
        new = edit_project(self.store, old, self.journal, PROMPTS, CUTS, overlap_frames=12)
        self.assertEqual(new["overlap_frames"], 12)
        self.assertEqual(new["changed_from"], 1)
        self.assertEqual(len(new["segments"]), 1)
        self.assertEqual(new["cut_seeds"], [11, 12, 13, 14])
        self.assertEqual(self.store.asset(new, new["segments"][0]["file"]).read_bytes(), b"clip0")
        self.assertEqual(self.store.load(folder / "manifest.json"), old)
        self.assertNotIn("overlap_frames", old)
        self.assertEqual([w["trim_start_frames"] for w in manifest_windows(old)], [0, 1, 1, 1])

    def test_new_plan_resume_and_join_trim_both_streams(self):
        manifest = self.create()
        path = self.store.folder(manifest["run_id"]) / "manifest.json"
        media = Mock()
        anchors, sent = [], []
        info = {}
        stopped = False

        def anchor(clip, count, target, event):
            anchors.append(count)
            target.write_bytes(b"anchor")

        def execute(cfg, config_path, workflow, params, **kw):
            nonlocal stopped
            i = kw["job_context"]["long_segment"]
            if i == 1 and not stopped:
                stopped = True
                raise LongVideoPaused("stop")
            sent.append((i, params))
            row = self.journal.create(BACKEND, workflow, "i2v", params, {}, kw["job_context"])
            self.journal.update(row["job_id"], state="completed", outputs={})
            return {"parameters": params, "prompt_id": row["prompt_id"], "job_id": row["job_id"], "outputs": {}}

        def download(result, directory):
            clip = directory / "clip.mp4"
            clip.write_bytes(b"video")
            info[clip.resolve()] = {"frames": result["parameters"]["frames"],
                                    "width": 864, "height": 480, "fps": 24, "audio": True}
            return clip

        media.last_frame.side_effect = anchor
        media.probe.side_effect = lambda path, event: info[path.resolve()]
        media.join.side_effect = lambda clips, count, output, event, progress, **kw: output.write_bytes(b"joined")
        cfg = {"comfyui": {"base_url": BACKEND}}
        with patch.object(core, "ComfyUI", return_value=Mock(base=BACKEND)), \
                patch.object(core, "execute_saved", side_effect=execute), \
                patch.object(core, "execute") as interpret:
            with self.assertRaises(LongVideoPaused):
                run_long_video(self.store, manifest, cfg, self.root / "config.json", self.journal,
                               self.root, download, media=media)
            loaded = self.store.load(path)
            result, out = run_long_video(self.store, loaded, cfg, self.root / "config.json", self.journal,
                                         self.root, download, media=media)
            interpret.assert_not_called()
        self.assertEqual([p["frames"] for _, p in sent], [107, 124, 141, 158])
        self.assertEqual(anchors, [61, 61, 97, 121])
        self.assertNotIn("0.500 seconds", sent[0][1]["positive_prompt"])
        self.assertIn("0.500 seconds", sent[1][1]["positive_prompt"])
        self.assertEqual(media.join.call_args.args[1], 434)
        self.assertEqual(media.join.call_args.kwargs["keep_frames"], CUTS)
        self.assertEqual(media.join.call_args.kwargs["trim_start_frames"], [0, 12, 12, 12])
        self.assertEqual(result["parameters"]["long_overlap_frames"], 12)
        self.assertEqual(result["parameters"]["frames"], 434)
        entry = SimpleNamespace(parameters=result["parameters"], reference_image=self.source,
                                request_text="walk", prompt_profile=None)
        restored = restore_project_plan(self.store, entry, BACKEND)
        self.assertEqual(restored["overlap_frames"], 12)
        self.assertEqual(restored["plan"], loaded["plan"])

    def test_llm_receives_retained_timing_and_lead_in(self):
        cfg = {"llm": {"model": "test", "unload_after_inference": False},
               "comfyui": {"free_before_llm": False},
               "workflows": {core.H3_I2V_ID: {"kind": "i2v"}}}
        response = {"choices": [{"message": {"content": json.dumps(PROMPTS)}}]}
        with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="instance"), \
                patch.object(lmstudio, "_request", return_value=response) as req:
            plan = plan_long_prompts(cfg, "walk", generation_frames_for_cuts(CUTS),
                                     sum(CUTS)/24, cut_frames=CUTS, overlap_frames=12)
        payload = json.loads(req.call_args.args[2]["messages"][1]["content"])
        self.assertEqual(plan, PROMPTS)
        self.assertEqual([w["output_frames"] for w in payload["timeline"]], CUTS)
        self.assertEqual([w["trim_start_frames"] for w in payload["timeline"]], [0, 12, 12, 12])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_ffmpeg_discards_lead_in_video_and_audio_exactly(self):
        media = FFmpeg()
        clips = []
        for i, color in enumerate(("green", "blue")):
            folder = self.root / f"segment_{i}"
            folder.mkdir()
            clip = folder / "clip.mp4"
            args = [media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s=64x64:r=24", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000"]
            if i:
                args += ["-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=red:t=fill:enable=lt(n\\,12)",
                         "-af", "volume=0:enable=lt(t\\,0.5)"]
            else:
                args += ["-af", "volume=0"]
            args += ["-t", "1.6666667", "-frames:v", "40", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                     "-c:a", "aac", clip]
            media._run(args)
            clips.append((clip, media.probe(clip)))
        output = self.root / "joined.mp4"
        media.join(clips, 48, output, keep_frames=[24, 24], trim_start_frames=[0, 12])
        self.assertEqual(media.probe(output)["frames"], 48)
        pixel = media._run([media.ffmpeg, "-v", "error", "-i", output, "-vf",
                            "select=eq(n\\,24),scale=1:1", "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        self.assertGreater(pixel[2], pixel[0])
        audio = media._run([media.ffmpeg, "-v", "error", "-i", output, "-ss", "1.12",
                            "-t", "0.15", "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"])
        samples = array.array("h", audio)
        self.assertGreater(max(abs(s) for s in samples), 500)
        with self.assertRaises(core.OrchestratorError):
            media.join(clips, 48, output, keep_frames=[24, 24], trim_start_frames=[0, 17])


if __name__ == "__main__":
    unittest.main()
