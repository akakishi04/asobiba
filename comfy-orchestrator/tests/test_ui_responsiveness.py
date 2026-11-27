"""Regression tests for redundant Tk updates and nonblocking history reads."""
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.generation_view import GenerationView
from comfy_orchestrator.history_refresh import HistoryRefresh
from comfy_orchestrator.output_views import HistoryView

ROOT = Path(__file__).resolve().parents[1]


class Var:
    def __init__(self, value=""):
        self.value = value
        self.writes = 0

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self.writes += 1


class Widget:
    def __init__(self, manager=""):
        self.manager = manager
        self.changes = 0

    def winfo_manager(self):
        return self.manager

    def grid(self):
        self.manager = "grid"
        self.changes += 1

    def grid_remove(self):
        self.manager = ""
        self.changes += 1


class ResponsivenessTests(unittest.TestCase):
    def test_grid_changes_only_when_visibility_changes(self):
        widget = Widget()
        for _ in range(100):
            gui.set_grid_visible(widget, False)
        self.assertEqual(widget.changes, 0)
        for _ in range(100):
            gui.set_grid_visible(widget, True)
        self.assertEqual(widget.changes, 1)
        for _ in range(100):
            gui.set_grid_visible(widget, False)
        self.assertEqual(widget.changes, 2)

    def test_repeated_canvas_events_do_not_write_same_geometry(self):
        canvas = Mock()
        canvas.bbox.return_value = (0, 0, 400, 600)
        app = SimpleNamespace(form_canvas=canvas, form_window="inner")
        app._sync_form_scrollregion = lambda: GenerationView._sync_form_scrollregion(app)
        for _ in range(100):
            GenerationView._size_form_to_canvas(app, 400)
        canvas.itemconfigure.assert_called_once_with("inner", width=400)
        canvas.configure.assert_called_once_with(scrollregion=(0, 0, 400, 600))
        GenerationView._size_form_to_canvas(app, 410)
        self.assertEqual(canvas.itemconfigure.call_count, 2)
        self.assertEqual(canvas.configure.call_count, 1)

    def test_reference_path_changes_do_not_reconfigure_identical_ui(self):
        cfg = core.load_config(ROOT / "config.example.json")
        app = SimpleNamespace(
            config=cfg, workflow=Var("wai_i2i_basic"),
            reference_image=Var("a"), mask_image=Var(), pose_image=Var(), composition_image=Var(),
            width_entry=Mock(), height_entry=Mock(), resolution_box=Mock(), denoise_entry=Mock(),
            cfg_entry=Mock(), run_button=Mock(), _active_workflow=lambda: "wai_i2i_basic",
        )
        for i in range(100):
            app.reference_image.set("a" * (i + 1))
            gui.Application._update_generation_controls(app)
        app.width_entry.configure.assert_called_once()
        app.run_button.configure.assert_called_once()
        app.reference_image.set("")
        app._active_workflow = lambda: "wai_t2i_basic"
        gui.Application._update_generation_controls(app)
        self.assertEqual(app.width_entry.configure.call_count, 2)

    def test_history_read_runs_on_worker_and_completion_does_not_rescan(self):
        main = threading.get_ident()
        seen = []
        def read(*, limit):
            seen.append(threading.get_ident())
            return []
        store = SimpleNamespace(list_entries=read, import_legacy_outputs=Mock())
        messages = queue.Queue()
        refresh = HistoryRefresh(store, messages.put)
        refresh.request("new", scan_legacy=False)
        self.assertEqual(messages.get(timeout=5), ("history_loaded", ([], "new", None)))
        self.assertNotEqual(seen[0], main)
        store.import_legacy_outputs.assert_not_called()

    def test_hidden_history_tab_never_loads_preview(self):
        view = SimpleNamespace(selected_entries=Mock())
        HistoryView.refresh_selection(view, {}, working=False, visible=False)
        view.selected_entries.assert_not_called()

    def test_identical_history_snapshot_does_not_rebuild_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HistoryStore(Path(folder))
            image = store.outputs / "a.png"
            image.write_bytes(b"image")
            entry = store.record(prompt_id="test", workflow_id="wai_t2i_basic",
                                 kind="t2i", request_text="test", parameters={"positive_prompt": "test"},
                                 images=[image])
            table = Mock()
            table.selection.return_value = (entry.id,)
            table.get_children.return_value = (entry.id,)
            view = SimpleNamespace(history_table=table, history_entries={entry.id: entry},
                                   on_selection=Mock(), history_details=Mock())
            HistoryView.apply_entries(view, [store.get(entry.id)])
            table.delete.assert_not_called()
            table.insert.assert_not_called()
            table.item.assert_not_called()
            table.set_children.assert_not_called()
            table.selection_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
