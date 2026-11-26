"""Explicit duration, trim-boundary, planning and resume tests."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    FFmpeg, LongVideoPaused, LongVideoStore, manifest_schedule, run_long_video,
)
from comfy_orchestrator.timeline import (
    default_cut_frames, format_cut_seconds, generation_frames_for_cuts, parse_cut_seconds,
    plan_long_prompts, segment_windows, validate_cut_frames,
)


class CutDurationTests(unittest.TestCase):
    def test_frames_and_windows(self):
        cuts = [72, 192, 120]
        frames = generation_frames_for_cuts(cuts)
        self.assertEqual(frames, [107, 209, 124])
        windows = segment_windows(frames, 16, cut_frames=cuts)
        self.assertEqual([(w["start_frame"], w["end_frame"]) for w in windows],
                         [(0, 72), (72, 264), (264, 384)])
        self.assertEqual([w["output_frames"] for w in windows], cuts)
        self.assertEqual(generation_frames_for_cuts([360, 360]), [362, 362])

    def test_validation_and_rounding(self):
        self.assertEqual(parse_cut_seconds("2.5"), 60)
        self.assertEqual(parse_cut_seconds("1.02"), 24)
        for frames in range(24, 361):
            self.assertEqual(parse_cut_seconds(format_cut_seconds(frames)), frames)
        for bad in ("0.9", "15.1", "NaN", "inf", "", "abc"):
            with self.assertRaises(core.OrchestratorError):
                parse_cut_seconds(bad)
        for bad in ([24], [23, 24], [24, 361], [360] * 21, [True, 24]):
            with self.assertRaises(core.OrchestratorError):
                validate_cut_frames(bad)
        for seconds in (30, 60, 120, 180, 300):
            for nominal in (107, 124, 192, 243, 294, 362):
                cuts = default_cut_frames(seconds, nominal)
                self.assertEqual(sum(cuts), seconds * 24)
                self.assertEqual(validate_cut_frames(cuts), cuts)

    def test_llm_receives_explicit_durations(self):
        cuts = [72, 192, 120]
        frames = generation_frames_for_cuts(cuts)
        config = {"llm": {"model": "test", "unload_after_inference": False},
                  "comfyui": {"free_before_llm": False},
                  "workflows": {core.H3_I2V_ID: {"kind": "i2v"}}}
        plan = {"common": "Same style.", "segments": ["A.", "B.", "C."]}
        response = {"choices": [{"message": {"content": json.dumps(plan)}}]}
        with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="instance"), \
                patch.object(lmstudio, "_request", return_value=response) as req:
            self.assertEqual(plan_long_prompts(config, "動く", frames, 16, cut_frames=cuts), plan)
        payload = json.loads(req.call_args.args[2]["messages"][1]["content"])
        self.assertEqual([w["duration_seconds"] for w in payload["timeline"]], [3, 8, 5])
        self.assertEqual([w["generation_frames"] for w in payload["timeline"]], frames)
        self.assertEqual(req.call_count, 1)

    def test_resume_anchors_at_retained_last_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            source.write_bytes(b"image")
            store = LongVideoStore(root / "long")
            journal = JobJournal(root / "jobs")
            cuts = [72, 192, 120]
            expected = generation_frames_for_cuts(cuts)
            backend = "http://localhost:8188"
            params = {"width": 864, "height": 480, "frames": 124, "fps": 24,
                      "steps": 8, "seed": 7, "h3_model": "w4a8", "h3_turbo": "turbo8"}
            plan = {"common": "Same subject.", "segments": ["A.", "B.", "C."]}
            manifest = store.create(backend, "original", source, params, 16,
                                    prompt_plan=plan, cut_frames=cuts)
            path = store.folder(manifest["run_id"]) / "manifest.json"
            self.assertEqual(manifest_schedule(store.load(path)), (expected, cuts, 384))
            broken = dict(manifest, seconds=17)
            with self.assertRaises(core.OrchestratorError):
                manifest_schedule(broken)
            media = Mock()
            info = {}
            anchors = []
            sent = []
            interrupted = False

            def anchor(clip, count, target, event):
                anchors.append(count)
                target.write_bytes(b"frame")

            def download(result, directory):
                clip = directory / "clip.mp4"
                clip.write_bytes(b"video")
                info[clip.resolve()] = {"frames": result["parameters"]["frames"],
                                        "width": 864, "height": 480, "fps": 24, "audio": True}
                return clip

            def execute(cfg, path, workflow, parameters, **kw):
                nonlocal interrupted
                index = kw["job_context"]["long_segment"]
                if index == 1 and not interrupted:
                    interrupted = True
                    raise LongVideoPaused("stop")
                sent.append((index, parameters["frames"]))
                record = journal.create(backend, workflow, "i2v", parameters, {}, kw["job_context"])
                journal.update(record["job_id"], state="completed", outputs={})
                return {"parameters": parameters, "prompt_id": record["prompt_id"],
                        "job_id": record["job_id"], "outputs": {}}

            media.last_frame.side_effect = anchor
            media.probe.side_effect = lambda path, event: info[path.resolve()]
            media.join.side_effect = lambda clips, count, output, event, progress, **kw: output.write_bytes(b"joined")
            config = {"comfyui": {"base_url": backend}}
            with patch.object(core, "ComfyUI", return_value=Mock(base=backend)), \
                    patch.object(core, "execute") as interpret, \
                    patch.object(core, "execute_saved", side_effect=execute):
                with self.assertRaises(LongVideoPaused):
                    run_long_video(store, manifest, config, root / "config.json", journal,
                                   root, download, media=media)
                loaded = store.load(path)
                result, output = run_long_video(store, loaded, config, root / "config.json", journal,
                                                root, download, media=media)
                interpret.assert_not_called()
            self.assertEqual(sent, list(enumerate(expected)))
            self.assertEqual(anchors, [72, 72, 193])
            self.assertEqual(media.join.call_args.kwargs["keep_frames"], cuts)
            self.assertEqual(media.join.call_args.args[1], 384)
            self.assertEqual(result["parameters"]["long_cut_frames"], cuts)
            self.assertEqual(result["parameters"]["frames"], 384)
            self.assertTrue(output.exists())

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_ffmpeg_per_cut_trim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = FFmpeg()
            clips = []
            for i, color in enumerate(("red", "blue")):
                folder = root / f"segment_{i}"
                folder.mkdir()
                clip = folder / "clip.mp4"
                media._run([media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"color=c={color}:s=64x64:r=24", "-frames:v", "40",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", clip])
                clips.append((clip, media.probe(clip)))
            output = root / "out.mp4"
            media.join(clips, 48, output, keep_frames=[24, 24])
            self.assertEqual(media.probe(output)["frames"], 48)
            # The frame immediately after the first retained cut must be blue,
            # not an extra red frame from the discarded first tail.
            pixel = media._run([media.ffmpeg, "-v", "error", "-i", output, "-vf",
                                "select=eq(n\\,24),scale=1:1", "-frames:v", "1",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            self.assertGreater(pixel[2], pixel[0])


if __name__ == "__main__":
    unittest.main()
