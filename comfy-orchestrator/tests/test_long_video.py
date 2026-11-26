import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core
from comfy_orchestrator.long_video import (
    FFmpeg, LongVideoPaused, LongVideoStore, segment_plan, continuation_parameters,
    run_long_video,
)
from comfy_orchestrator.jobs import JobJournal


class LongVideoTests(unittest.TestCase):
    def test_plan_grid_and_target(self):
        for seconds in (30, 60, 120, 180, 300):
            for limit in (107, 124, 192, 243, 294, 362):
                plan = segment_plan(seconds, limit)
                self.assertTrue(all(107 <= f <= limit and (f - 5) % 17 == 0 for f in plan))
                self.assertGreaterEqual(sum(plan) - len(plan) + 1, seconds * 24)
                self.assertLess(sum(plan) - len(plan) + 1 - seconds * 24, 107)

    def test_continuation_seed_and_prompt(self):
        first = {"seed": 123, "frames": 124, "positive_prompt": "A tree sways.",
                 "h3_model": "w4a8"}
        next_p = continuation_parameters(first, 2, 107)
        self.assertEqual(next_p["seed"], 125)
        self.assertEqual(next_p["frames"], 107)
        self.assertIn("Continue", next_p["positive_prompt"])
        self.assertEqual(first["positive_prompt"], "A tree sways.")

    def test_resume_skips_saved_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "a.png"
            source.write_bytes(b"image")
            store = LongVideoStore(root / "long")
            journal = JobJournal(root / "jobs")
            params = {"width": 864, "height": 480, "frames": 124, "fps": 24,
                      "steps": 8, "seed": 7, "h3_model": "w4a8", "h3_turbo": "turbo8"}
            manifest = store.create("http://localhost:8188", "tree", source, params, 30)
            config = {"comfyui": {"base_url": "http://localhost:8188"}}
            stop = threading.Event()
            media = Mock()
            media.last_frame.side_effect = lambda clip, frames, target, event: target.write_bytes(b"frame")
            frame_info = {}
            media.probe.side_effect = lambda path, event: frame_info[path.resolve()]
            media.join.side_effect = lambda clips, count, output, event, progress: output.write_bytes(b"joined")
            comfy = Mock(base=config["comfyui"]["base_url"])
            def make_result(parameters, context):
                record = journal.create(comfy.base, core.H3_I2V_ID, "i2v", parameters, {}, context)
                journal.update(record["job_id"], state="completed", outputs={})
                return {"parameters": parameters, "prompt_id": record["prompt_id"],
                        "job_id": record["job_id"], "outputs": {}}
            def first(cfg, path, prompt, **kw):
                return make_result({**kw["overrides"], "positive_prompt": "A tree sways."}, kw["job_context"])
            def later(cfg, path, wf, parameters, **kw):
                if kw["job_context"]["long_segment"] == 1 and not interrupted[0]:
                    interrupted[0] = True
                    stop.set()
                    raise LongVideoPaused("stopped")
                return make_result(parameters, kw["job_context"])
            interrupted = [False]
            def download(result, directory):
                clip = directory / "clip.mp4"
                clip.write_bytes(b"video")
                frame_info[clip.resolve()] = {"frames": result["parameters"]["frames"], "fps": 24,
                                               "width": 864, "height": 480, "audio": True}
                return clip
            with patch.object(core, "ComfyUI", return_value=comfy), \
                    patch.object(core, "execute", side_effect=first) as start, \
                    patch.object(core, "execute_saved", side_effect=later):
                with self.assertRaises(LongVideoPaused):
                    run_long_video(store, manifest, config, root / "config.json", journal, root,
                                   download, cancel_event=stop, media=media)
                self.assertEqual(len(manifest["segments"]), 1)
                stop.clear()
                loaded = store.load(store.folder(manifest["run_id"]) / "manifest.json")
                result, output = run_long_video(store, loaded, config, root / "config.json", journal, root,
                                                download, cancel_event=stop, media=media)
                self.assertEqual(start.call_count, 1)
                self.assertEqual(result["parameters"]["frames"], 720)
                self.assertTrue(output.exists())
                self.assertEqual(len(loaded["segments"]), len(loaded["plan"]))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_ffmpeg_exact_frame_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = FFmpeg()
            clips = []
            for i in range(2):
                folder = root / f"segment_{i:03d}"
                folder.mkdir()
                clip = folder / "clip.mp4"
                media._run([media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                            "color=c=blue:s=64x64:r=24", "-frames:v", "25",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", clip])
                clips.append((clip, media.probe(clip)))
            output = root / "out.mp4"
            media.join(clips, 48, output)
            info = media.probe(output)
            self.assertEqual(info["frames"], 48)
            self.assertTrue(info["audio"])
