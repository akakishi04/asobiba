"""Material provenance, exact frame selection, and compatibility guards."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

from comfy_orchestrator import core
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.history_presentation import history_action_state, history_summary
from comfy_orchestrator.material_transfer import available_materials, transfer_settings, source_stamp, extract_material
from comfy_orchestrator.video_media import FFmpeg

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"


class MaterialTransferTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.history = HistoryStore(self.root)
        self.config = core.load_config(CONFIG)
        self.video = self.history.outputs / "clip.mp4"
        self.video.write_bytes(b"video")
        self.image = self.history.outputs / "image.png"
        self.image.write_bytes(b"image")

    def test_all_outputs_and_original_reference_are_available(self):
        ref = self.root / "reference.jpg"
        ref.write_bytes(b"reference")
        candidates = available_materials([self.video, self.image, self.image, self.root / "missing.png"], ref)
        self.assertEqual([c.path for c in candidates], [self.video, self.image, ref])
        self.assertTrue(candidates[-1].label.startswith("元の参照"))

    def test_cross_family_settings_are_not_copied(self):
        p = {"steps": 8, "cfg": 1, "seed": 5, "positive_prompt": "private"}
        self.assertEqual(transfer_settings(core.H3_I2V_ID, p, None, "image"), {})
        self.assertEqual(transfer_settings("wai_t2i_basic", p, None, "video"), {})
        actual = transfer_settings("wai_t2i_basic", p, None, "image")
        self.assertEqual(actual, {"steps": "8", "cfg": "1", "seed": "5"})

    def test_h3_settings_use_cut_length_not_joined_length(self):
        params = {"width": 864, "height": 480, "fps": 24, "frames": 124,
                  "steps": 8, "seed": 7, "h3_model": "w4a8", "h3_turbo": "turbo8"}
        long = {**params, "frames": 720, "long_base_overrides": params, "long_prompt_plan": {}}
        result = transfer_settings("minimax_h3_long_video", long, None, "video")
        self.assertEqual(result["h3_size"], "864 × 480")
        self.assertIn("124f", result["h3_duration"])
        self.assertEqual(result["h3_model"], core.h3_model_label("w4a8"))
        self.assertEqual(result["seed"], "7")
        self.assertNotIn("long_prompt_plan", result)
        ref = core.h3_ref2va_model_key("s3_ref2va_w4a8.safetensors")
        self.assertEqual(transfer_settings(core.H3_I2V_ID, {**params, "h3_model": ref}, None, "continuous"), {})

    def test_derived_frame_is_reusable_but_not_replayable(self):
        media = Mock()
        media.extract_frame.side_effect = lambda source, frame, target, cancel: target.write_bytes(b"frame")
        entry = extract_material(self.history, self.video, 42, stamp=source_stamp(self.video),
                                 source_history_id="source-id", media=media)
        self.assertTrue(entry.legacy)
        self.assertEqual(entry.kind, "frame")
        self.assertEqual(entry.parameters, {"material_source": "clip.mp4", "material_frame": 42,
                                            "material_source_history_id": "source-id"})
        self.assertEqual(entry.first_image.read_bytes(), b"frame")
        self.assertTrue(entry.first_image.is_relative_to(self.history.outputs / "materials"))
        self.assertEqual(self.history.get(entry.id), entry)
        self.assertIn("42f", history_summary(entry))
        state = history_action_state([entry], self.config["workflows"], working=False)
        self.assertTrue(state["use_as_source"])
        self.assertFalse(state["restore"] or state["prompt"] or state["request"])
        self.assertEqual(self.video.read_bytes(), b"video")

    def test_changed_source_and_cancel_do_not_publish_frame(self):
        media = Mock()
        stamp = source_stamp(self.video)
        self.video.write_bytes(b"changed content")
        with self.assertRaisesRegex(core.OrchestratorError, "変更"):
            extract_material(self.history, self.video, 1, stamp=stamp, media=media)
        media.extract_frame.assert_not_called()
        cancel = threading.Event()
        def stop(source, frame, target, event):
            target.write_bytes(b"frame")
            cancel.set()
        media.extract_frame.side_effect = stop
        with self.assertRaises(core.OrchestratorError):
            extract_material(self.history, self.video, 1, stamp=source_stamp(self.video), media=media,
                             cancel_event=cancel)
        self.assertEqual(self.history.list_entries(), [])
        self.assertFalse((self.history.outputs / "materials").exists())

    def test_ffmpeg_extracts_exact_frame_number(self):
        try:
            media = FFmpeg()
        except core.OrchestratorError as exc:
            self.skipTest(str(exc))
        media._run([media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=s=64x64:r=24", "-frames:v", "24", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", self.video])
        first = self.root / "first.png"
        last = self.root / "last.png"
        media.extract_frame(self.video, 1, first)
        media.extract_frame(self.video, 24, last)
        self.assertNotEqual(first.read_bytes(), last.read_bytes())
        derived = extract_material(self.history, self.video, 24, stamp=source_stamp(self.video), media=media)
        self.assertEqual(derived.first_image.read_bytes(), last.read_bytes())
        with self.assertRaises(core.OrchestratorError):
            media.extract_frame(self.video, 25, self.root / "bad.png")


if __name__ == "__main__":
    unittest.main()
