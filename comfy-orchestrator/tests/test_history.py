"""Offline regression tests for persistent history and exact/new-seed reruns."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import comparison, core, history


PROJECT = Path(__file__).resolve().parents[1]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = history.HistoryStore(self.root)
        self.output = self.store.outputs / "generated.png"
        self.output.write_bytes(b"png bytes")
        self.original = self.root / "source.png"
        self.original.write_bytes(b"original bytes")
        self.params = {
            "positive_prompt": "1girl, blue dress", "negative_prompt": "blurry",
            "steps": 28, "cfg": 5.5, "denoise": 0.53, "seed": 1024,
        }

    def save(self, prompt_id="unique-prompt"):
        return self.store.record(
            prompt_id=prompt_id, workflow_id="wai_i2i_basic",
            kind="i2i", request_text="服を青にする",
            parameters=self.params, images=[self.output],
            reference_image=self.original,
        )

    def test_record_and_reopen_preserves_prompts_seed_and_image(self):
        entry = self.save()
        self.assertEqual(entry.reference_image.read_bytes(), b"original bytes")
        self.assertEqual(entry.first_image, self.output.resolve())
        self.assertEqual(entry.parameters["seed"], 1024)
        self.assertEqual(entry.request_text, "服を青にする")
        reopened = history.HistoryStore(self.root)
        saved = reopened.get(entry.id)
        self.assertEqual(saved, entry)
        self.assertEqual(reopened.list_entries()[0].id, entry.id)

    def test_reference_survives_moving_original(self):
        entry = self.save()
        self.original.unlink()
        self.assertTrue(entry.reference_image.is_file())
        self.assertEqual(entry.reference_image.read_bytes(), b"original bytes")

    def test_original_source_and_output_not_modified(self):
        self.save()
        self.assertEqual(self.original.read_bytes(), b"original bytes")
        self.assertEqual(self.output.read_bytes(), b"png bytes")

    def test_multiple_outputs_are_preserved_in_order(self):
        next_image = self.store.outputs / "second.png"
        next_image.write_bytes(b"png2")
        entry = self.store.record(
            prompt_id="multi", workflow_id="wai_t2i_basic", kind="t2i",
            request_text="夜景", parameters={"positive_prompt": "sky", "seed": 8},
            images=[self.output, next_image],
        )
        self.assertEqual(entry.images, (self.output.resolve(), next_image.resolve()))
        self.assertIsNone(entry.reference_image)

    def test_duplicate_prompt_does_not_leak_reference_snapshots(self):
        self.save()
        with self.assertRaises(Exception):
            self.save()
        references = list((self.store.data / "references").glob("*"))
        self.assertEqual(len(references), 1)

    def test_paths_cannot_escape_output_folder(self):
        outside = self.root / "outside.png"
        outside.write_bytes(b"unsafe")
        with self.assertRaisesRegex(history.HistoryError, "outputs"):
            self.store.record(
                prompt_id="outside", workflow_id="t2i", kind="t2i",
                request_text="x", parameters={"positive_prompt": "x"},
                images=[outside],
            )
        with self.assertRaisesRegex(history.HistoryError, "保存領域の外"):
            self.store._child_path(self.store.outputs, "../outside.png")

    def test_empty_output_is_not_recorded(self):
        with self.assertRaises(history.HistoryError):
            self.store.record(
                prompt_id="empty", workflow_id="t2i", kind="t2i",
                request_text="x", parameters={}, images=[],
            )

    def test_legacy_outputs_are_visible_but_do_not_gain_invented_metadata(self):
        imported = self.store.import_legacy_outputs()
        self.assertEqual(imported, 1)
        entry = self.store.list_entries()[0]
        self.assertTrue(entry.legacy)
        self.assertEqual(entry.parameters, {})
        self.assertEqual(entry.first_image, self.output.resolve())
        self.assertEqual(self.store.import_legacy_outputs(), 0)

    def test_new_generation_not_reimported_as_legacy(self):
        self.save()
        self.assertEqual(self.store.import_legacy_outputs(), 0)
        self.assertFalse(self.store.list_entries()[0].legacy)


class SavedReplayTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(PROJECT / "config.example.json")

    def test_same_seed_replay_does_not_call_llm(self):
        entry = self.config["workflows"]["wai_t2i_basic"]
        params = {
            **entry["defaults"], "positive_prompt": "sunset, sea",
            "seed": 123456, "width": 768, "height": 768,
        }
        with patch.object(core, "ComfyUI") as mocked, patch.object(
            core.secrets, "randbits", side_effect=AssertionError("should not generate seed")
        ):
            runner = mocked.return_value
            runner.submit.return_value = "replay-id"
            runner.wait.return_value = {"outputs": {"13": {"images": [{"filename": "x.png"}]}}}
            result = core.execute_saved(
                self.config, PROJECT / "config.example.json",
                "wai_t2i_basic", params, new_seed=False,
            )
        self.assertEqual(result["parameters"]["seed"], 123456)
        self.assertEqual(runner.submit.call_args.args[0]["11"]["inputs"]["seed"], 123456)
        self.assertEqual(runner.submit.call_args.args[0]["8"]["inputs"]["text"], "sunset, sea")
        runner.upload_image.assert_not_called()

    def test_new_seed_replay_changes_only_seed(self):
        entry = self.config["workflows"]["wai_t2i_basic"]
        params = {**entry["defaults"], "positive_prompt": "sky", "seed": 4}
        with patch.object(core, "ComfyUI") as mocked, patch.object(
            core.secrets, "randbits", return_value=9876
        ):
            runner = mocked.return_value
            runner.submit.return_value = "replay-2"
            runner.wait.return_value = {}
            out = core.execute_saved(
                self.config, PROJECT / "config.example.json",
                "wai_t2i_basic", params, new_seed=True,
            )
        self.assertEqual(out["parameters"]["seed"], 9876)
        self.assertEqual(params["seed"], 4)
        self.assertEqual(out["parameters"]["positive_prompt"], "sky")

    def test_i2i_replay_uploads_archived_original(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(b"png")
            params = {
                "positive_prompt": "1girl", "negative_prompt": "",
                "steps": 20, "cfg": 5.5, "seed": 44, "denoise": 0.5,
            }
            with patch.object(core, "ComfyUI") as mocked:
                runner = mocked.return_value
                runner.upload_image.return_value = "uploaded.png"
                runner.submit.return_value = "i2i-replay"
                runner.wait.return_value = {}
                core.execute_saved(
                    self.config, PROJECT / "config.example.json",
                    "wai_i2i_basic", params, reference_image=source,
                )
            runner.upload_image.assert_called_once_with(source)
            self.assertEqual(
                runner.submit.call_args.args[0]["16"]["inputs"]["image"], "uploaded.png"
            )

    def test_i2i_without_reference_is_rejected(self):
        with self.assertRaisesRegex(core.OrchestratorError, "参照画像"):
            core.execute_saved(
                self.config, PROJECT / "config.example.json",
                "wai_i2i_basic", {"positive_prompt": "girl", "seed": 1},
            )

    def test_replay_rejects_unregistered_workflow(self):
        with self.assertRaisesRegex(core.OrchestratorError, "未登録"):
            core.execute_saved(
                self.config, PROJECT / "config.example.json",
                "obsolete", {"positive_prompt": "girl", "seed": 1},
            )


class HistoryGuiActionsTests(unittest.TestCase):
    def test_restoring_i2i_history_populates_prompt_and_seed(self):
        from comfy_orchestrator import gui

        class Variable:
            def __init__(self, value=""):
                self.value = value

            def set(self, value):
                self.value = value

            def get(self):
                return self.value

        class Prompt:
            def __init__(self):
                self.text = ""
                self.focused = False

            def delete(self, start, end):
                self.text = ""

            def insert(self, start, value):
                self.text = value

            def focus_set(self):
                self.focused = True

        with tempfile.TemporaryDirectory() as folder:
            store = history.HistoryStore(Path(folder))
            output = store.outputs / "output.png"
            output.write_bytes(b"image")
            reference = Path(folder) / "ref.png"
            reference.write_bytes(b"ref")
            entry = store.record(
                prompt_id="pr-1", workflow_id="wai_i2i_basic", kind="i2i",
                request_text="服を赤にして", parameters={
                    "positive_prompt": "1girl, red dress", "negative_prompt": "",
                    "steps": 25, "cfg": 5.0, "seed": 4488, "denoise": 0.45,
                },
                images=[output], reference_image=reference,
            )

            class App:
                def __init__(self):
                    self.prompt = Prompt()
                    self.workflow = Variable()
                    self.reference_image = Variable()
                    self.width = Variable("768")
                    self.height = Variable("768")
                    self.steps = Variable("20")
                    self.cfg = Variable("5.5")
                    self.seed = Variable()
                    self.denoise = Variable("0.53")
                    self.status = Variable()
                    self.config = core.load_config(PROJECT / "config.example.json")
                    self.lines = []
                    self.updated = False

                def _one_history(self):
                    return entry

                def _update_generation_controls(self):
                    self.updated = True

                def _log(self, msg):
                    self.lines.append(msg)

            fake = App()
            gui.Application._restore_selected_history(fake)
            self.assertEqual(fake.prompt.text, "服を赤にして")
            self.assertEqual(fake.workflow.get(), "wai_i2i_basic")
            self.assertEqual(fake.reference_image.get(), str(entry.reference_image))
            self.assertEqual(fake.seed.get(), "4488")
            self.assertEqual(fake.denoise.get(), "0.45")
            self.assertTrue(fake.updated)
            self.assertTrue(fake.prompt.focused)

    def test_i2i_compare_uses_original_and_result(self):
        from comfy_orchestrator import gui
        with tempfile.TemporaryDirectory() as folder:
            store = history.HistoryStore(Path(folder))
            out = store.outputs / "output.png"
            out.write_bytes(b"output")
            original = Path(folder) / "original.png"
            original.write_bytes(b"original")
            entry = store.record(
                prompt_id="123", workflow_id="wai_i2i_basic", kind="i2i",
                request_text="test", parameters={"positive_prompt": "girl", "seed": 2},
                images=[out], reference_image=original,
            )
            class FakeApp:
                root = object()
                def _selected_history(self):
                    return [entry]
            with patch.object(gui, "ComparisonWindow") as compare:
                gui.Application._compare_selected_history(FakeApp())
            args = compare.call_args.args
            self.assertEqual(args[1:3], (entry.reference_image, entry.first_image))



class ComparisonHelpersTests(unittest.TestCase):
    def test_scale_limits(self):
        self.assertEqual(comparison.clamp_zoom(0.5), 0.5)
        for bad in (0, 0.1, 3, -1):
            with self.assertRaises(ValueError):
                comparison.clamp_zoom(bad)

    def test_fit_ratio(self):
        self.assertEqual(comparison.fit_zoom(1000, 1000, 520, 600), 0.5)
        self.assertEqual(comparison.fit_zoom(400, 400, 1000, 900), 1.0)


if __name__ == "__main__":
    unittest.main()
