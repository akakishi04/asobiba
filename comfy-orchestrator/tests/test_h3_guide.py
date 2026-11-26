"""Native H3 video-guide scheduling, graph wiring, media and recovery."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, generation_runtime
from comfy_orchestrator.h3_guide import prepare_guide_workflow
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import (
    FFmpeg, LongVideoPaused, LongVideoStore, connection_changed_from,
    continuation_anchor_count, edit_project, manifest_windows, run_long_video,
    schedule_windows,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
BACKEND = "http://localhost:8188"
CUTS = [72, 96, 120, 146]
PARAMS = {"width": 864, "height": 480, "fps": 24, "frames": 124,
          "steps": 8, "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}
PROMPTS = {"common": "Same subject.", "segments": ["A.", "B.", "C.", "D."]}


def graph_images(graph, link):
    node = graph[link[0]]
    if node["class_type"] == "LoadImage":
        return [node["inputs"]["image"]]
    if node["class_type"] == "ImageBatch":
        return graph_images(graph, node["inputs"]["image1"]) + graph_images(graph, node["inputs"]["image2"])
    raise AssertionError(node)


class H3GuideTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.source = self.root / "source.png"
        self.source.write_bytes(b"reference")
        self.store = LongVideoStore(self.root / "projects")
        self.journal = JobJournal(self.root / "jobs")
        self.config = core.load_config(CONFIG)
        self.template = json.loads((ROOT / "workflows" / "minimax_h3_i2v.api.json").read_text(encoding="utf-8"))

    def create(self, *, overlap=22):
        return self.store.create(BACKEND, "walk", self.source, PARAMS, sum(CUTS) / 24,
                                 prompt_plan=PROMPTS, cut_frames=CUTS, draft=True,
                                 overlap_frames=overlap)

    def test_guide_schedule_keeps_exact_output_and_falls_back_to_legal_lengths(self):
        windows = schedule_windows(sum(CUTS) / 24, 124, CUTS, overlap_frames=22)
        self.assertEqual([w["output_frames"] for w in windows], CUTS)
        self.assertEqual([w["guide_frames"] for w in windows], [0, 22, 22, 22])
        self.assertEqual([w["trim_start_frames"] for w in windows], [0, 22, 22, 22])
        self.assertEqual([w["generation_frames"] for w in windows], [107, 124, 158, 175])
        self.assertEqual([continuation_anchor_count(windows[i-1], windows[i])-1
                          for i in range(1, 4)], [50, 96, 120])
        self.assertEqual(windows[-1]["end_frame"], 434)
        cuts = [24, 341, 358, 360]
        short = schedule_windows(sum(cuts)/24, 362, cuts, overlap_frames=22)
        self.assertEqual([w["guide_frames"] for w in short], [0, 5, 0, 0])
        self.assertEqual([w["trim_start_frames"] for w in short], [0, 5, 1, 1])
        for seconds in (30, 60, 120, 180, 300):
            for nominal in (107, 124, 192, 243, 294, 362):
                w = schedule_windows(seconds, nominal, overlap_frames=22)
                self.assertEqual(sum(x["output_frames"] for x in w), seconds * 24)
                self.assertTrue(all(x["generation_frames"] <= 362 and
                                    (x["generation_frames"]-5) % 17 == 0 and
                                    x["trim_start_frames"] + x["output_frames"] <= x["generation_frames"]
                                    for x in w))

    def test_native_graph_preserves_frame_order_and_replaces_the_still_anchor(self):
        for count in (5, 22):
            names = [f"frame_{i:03d}.png" for i in range(1, count)]
            graph = prepare_guide_workflow(self.template, names)
            guide = graph[graph["16"]["inputs"]["conditioning"][0]]
            self.assertEqual(guide["class_type"], "MiniMaxH3AddGuide")
            self.assertEqual(guide["inputs"]["positive"], ["104", 0])
            self.assertEqual(guide["inputs"]["latent"], ["104", 1])
            self.assertEqual(guide["inputs"]["vae"], ["11", 0])
            self.assertEqual(guide["inputs"]["frame_idx"], 0)
            self.assertEqual(graph_images(graph, guide["inputs"]["image"]), ["reference.png"] + names)
            self.assertNotIn("first_frame", graph["104"]["inputs"])
            self.assertEqual(graph["14"], self.template["14"])
            self.assertEqual(graph["9"], self.template["9"])
            self.assertIn("first_frame", self.template["104"]["inputs"])
        with self.assertRaises(core.OrchestratorError):
            prepare_guide_workflow(self.template, ["too_short.png"])
        with self.assertRaises(core.OrchestratorError):
            prepare_guide_workflow({**self.template, "104": {"class_type": "MiniMaxH3ReferenceToVideo",
                                                              "inputs": {}}}, ["x.png"]*4)

    def test_hybrid_preflight_checks_guide_nodes_before_generation(self):
        model = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors",
                                        reference_only=True)
        with patch.object(core, "ComfyUI") as factory:
            generation_runtime.preflight_long(self.config, CONFIG,
                {**PARAMS, "h3_model": model, "h3_turbo": "off"}, [107, 124], guide_frame_count=22)
        checks = [c.args[0] for c in factory.return_value.ensure_video_dependencies.call_args_list]
        self.assertEqual(len(checks), 3)
        self.assertEqual(checks[0]["104"]["class_type"], "MiniMaxH3ReferenceToVideo")
        self.assertEqual(checks[1]["104"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertIn("MiniMaxH3AddGuide", {node["class_type"] for node in checks[2].values()})
        self.assertIn("ImageBatch", {node["class_type"] for node in checks[2].values()})

    def test_saved_execution_uploads_and_journals_all_guide_frames(self):
        frames = []
        for i in range(22):
            path = self.root / f"frame_{i:03d}.png"
            path.write_bytes(f"frame{i}".encode())
            frames.append(path)
        comfy = Mock(base=BACKEND)
        comfy.upload_image.side_effect = lambda path: path.read_bytes().decode() + ".png"
        comfy.submit.side_effect = lambda graph, prompt_id: prompt_id
        comfy.wait.return_value = {"outputs": {}}
        with patch.object(core, "ComfyUI", return_value=comfy):
            result = core.execute_saved(self.config, CONFIG, core.H3_I2V_ID,
                {**PARAMS, "positive_prompt": "Continue the clip."},
                reference_image=frames[0], guide_images=frames[1:], job_journal=self.journal,
                job_context={"long_run_id": "test", "long_segment": 1})
        self.assertEqual(comfy.upload_image.call_count, 22)
        record = self.journal.read(result["job_id"])
        graph = record["graph"]
        self.assertEqual(graph, comfy.submit.call_args.args[0])
        guide = graph[graph["16"]["inputs"]["conditioning"][0]]
        self.assertEqual(graph_images(graph, guide["inputs"]["image"]), [f"frame{i}.png" for i in range(22)])
        for path in frames:
            path.unlink()
        context = self.journal.context_for_history(record)
        self.assertEqual([p.read_bytes() for p in (context["reference_image"], *context["guide_images"])],
                         [f"frame{i}".encode() for i in range(22)])
        self.assertEqual(record["state"], "completed")

    def test_switching_to_guided_mode_invalidates_equal_trim_single_image_cuts(self):
        cuts = [72, 357]
        prompts = {"common": "Scene.", "segments": ["A.", "B."]}
        old = self.store.create(BACKEND, "walk", self.source, PARAMS, sum(cuts)/24,
                                prompt_plan=prompts, cut_frames=cuts, overlap_frames=12)
        windows = manifest_windows(old)
        self.assertEqual(windows[1]["trim_start_frames"], 5)
        self.assertEqual(connection_changed_from(old, cuts, 22), 1)
        folder = self.store.folder(old["run_id"])
        clip = folder / "first.mp4"
        clip.write_bytes(b"first")
        old["segments"].append({"file": clip.name, "parameters": {**PARAMS, "seed": 11}})
        old["first_parameters"] = {**PARAMS, "positive_prompt": "Scene. A."}
        self.store.save(old)
        revised = edit_project(self.store, old, self.journal, prompts, cuts, overlap_frames=22)
        self.assertEqual(revised["changed_from"], 1)
        self.assertEqual(len(revised["segments"]), 1)
        self.assertEqual(revised["cut_seeds"], [11, 12])
        self.assertEqual(manifest_windows(revised)[1]["guide_frames"], 5)

    def test_guided_resume_extracts_retained_tail_and_joins_without_repeating_it(self):
        manifest = self.create()
        media = Mock()
        anchors, sent = [], []
        info = {}
        interrupted = False

        def extract(clip, start, count, folder, event):
            anchors.append((start, count))
            paths = tuple(folder / f"frame_{i:03d}.png" for i in range(count))
            for n, path in enumerate(paths):
                path.write_bytes(str(start+n).encode())
            return paths

        def execute(cfg, path, workflow, params, **kw):
            nonlocal interrupted
            i = kw["job_context"]["long_segment"]
            if i == 1 and not interrupted:
                interrupted = True
                raise LongVideoPaused("stop")
            extra = kw.get("guide_images", ())
            sent.append((i, params["frames"], len(extra)))
            if i:
                self.assertEqual(len(extra), 21)
                first = int(kw["reference_image"].read_bytes())
                self.assertEqual([int(p.read_bytes()) for p in extra], list(range(first+1, first+22)))
                self.assertIn("anchored video clip", params["positive_prompt"])
            row = self.journal.create(BACKEND, workflow, "i2v", params, {}, kw["job_context"])
            self.journal.update(row["job_id"], state="completed", outputs={})
            return {"parameters": params, "prompt_id": row["prompt_id"], "job_id": row["job_id"], "outputs": {}}

        def download(result, directory):
            clip = directory / "clip.mp4"
            clip.write_bytes(b"video")
            info[clip.resolve()] = {"frames": result["parameters"]["frames"],
                                    "width": 864, "height": 480, "fps": 24, "audio": True}
            return clip

        media.extract_guide_frames.side_effect = extract
        media.probe.side_effect = lambda path, event: info[path.resolve()]
        media.join.side_effect = lambda clips, count, output, event, progress, **kw: output.write_bytes(b"joined")
        cfg = {"comfyui": {"base_url": BACKEND}}
        with patch.object(core, "ComfyUI", return_value=Mock(base=BACKEND)), \
                patch.object(core, "execute_saved", side_effect=execute), \
                patch.object(core, "execute") as interpret:
            with self.assertRaises(LongVideoPaused):
                run_long_video(self.store, manifest, cfg, CONFIG, self.journal, self.root, download, media=media)
            loaded = self.store.load(self.store.folder(manifest["run_id"]) / "manifest.json")
            result, output = run_long_video(self.store, loaded, cfg, CONFIG, self.journal, self.root, download, media=media)
            interpret.assert_not_called()
        self.assertEqual(anchors, [(50, 22), (50, 22), (96, 22), (120, 22)])
        self.assertEqual(sent, [(0, 107, 0), (1, 124, 21), (2, 158, 21), (3, 175, 21)])
        media.last_frame.assert_not_called()
        self.assertEqual(media.join.call_args.kwargs["keep_frames"], CUTS)
        self.assertEqual(media.join.call_args.kwargs["trim_start_frames"], [0, 22, 22, 22])
        self.assertEqual(result["parameters"]["frames"], 434)
        self.assertEqual(result["parameters"]["long_overlap_frames"], 22)
        self.assertTrue(output.exists())
        self.assertFalse(list(self.store.folder(manifest["run_id"]).glob("guide-*")))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
    def test_ffmpeg_extracts_exact_contiguous_frames(self):
        media = FFmpeg()
        clip = self.root / "clip.mp4"
        media._run([media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=s=64x64:r=24", "-frames:v", "60", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", clip])
        folder = self.root / "guide"
        folder.mkdir()
        frames = media.extract_guide_frames(clip, 17, 22, folder)
        self.assertEqual(len(frames), 22)
        for i in (0, 10, 21):
            expected = self.root / f"expected_{i}.png"
            media.last_frame(clip, 18+i, expected)
            self.assertEqual(expected.read_bytes(), frames[i].read_bytes())
        bad = self.root / "too_short"
        bad.mkdir()
        with self.assertRaises(core.OrchestratorError):
            media.extract_guide_frames(clip, 50, 22, bad)


if __name__ == "__main__":
    unittest.main()
