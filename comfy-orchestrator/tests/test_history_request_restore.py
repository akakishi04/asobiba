"""Prompt-only history restoration must leave the active generation form intact."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from comfy_orchestrator import gui


class HistoryRequestRestoreTests(unittest.TestCase):
    def entry(self, text="髪を揺らす。\nカメラ固定。", legacy=False):
        return SimpleNamespace(legacy=legacy, request_text=text,
                               workflow_id="removed-workflow",
                               parameters={"positive_prompt": "Generated prompt.", "seed": 7})

    def app(self, entry, *, working=False, text="現在の指示"):
        prompt = Mock()
        prompt.get.return_value = text
        return SimpleNamespace(
            working=working, _one_history=lambda: entry, prompt=prompt,
            status=Mock(), form_canvas=Mock(), workflow=Mock(), reference_image=Mock(),
            seed=Mock(), h3_model=Mock(), h3_turbo=Mock(), h3_size=Mock(), model=Mock(),
            _update_generation_controls=Mock(), _save_settings=Mock(), _start=Mock(),
        )

    def test_restores_only_original_request_even_if_workflow_no_longer_exists(self):
        entry = self.entry()
        app = self.app(entry)
        gui.Application._restore_selected_history_request(app)
        app.prompt.replace.assert_called_once_with("1.0", "end-1c", entry.request_text)
        self.assertEqual(app.prompt.edit_separator.call_count, 2)
        app.prompt.focus_set.assert_called_once()
        app.form_canvas.yview_moveto.assert_called_once_with(0)
        for name in ("workflow", "reference_image", "seed", "h3_model", "h3_turbo",
                     "h3_size", "model", "_update_generation_controls", "_save_settings", "_start"):
            self.assertEqual(getattr(app, name).mock_calls, [], name)

    def test_no_selection_legacy_blank_or_busy_does_not_modify_editor(self):
        for entry, working in ((None, False), (self.entry(legacy=True), False),
                               (self.entry(""), False), (self.entry("  "), False),
                               (self.entry(), True)):
            with self.subTest(entry=entry, working=working):
                app = self.app(entry, working=working)
                gui.Application._restore_selected_history_request(app)
                app.prompt.replace.assert_not_called()
                app.prompt.edit_separator.assert_not_called()

    def test_identical_request_does_not_create_undo_edit(self):
        entry = self.entry()
        app = self.app(entry, text=entry.request_text)
        gui.Application._restore_selected_history_request(app)
        app.prompt.replace.assert_not_called()
        app.prompt.edit_separator.assert_not_called()

    def test_text_is_preserved_verbatim(self):
        entry = self.entry("  原文\n二行目\n")
        self.assertEqual(gui.history_request_text(entry), entry.request_text)


if __name__ == "__main__":
    unittest.main()
