"""Result snapshot, async history and UI-event routing regressions."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from comfy_orchestrator import gui
from comfy_orchestrator.history_refresh import HistoryRefresh
from comfy_orchestrator.result_state import ResultReviewState
from comfy_orchestrator.task_controller import EventRouter, TaskController


class ApplicationStateTests(unittest.TestCase):
    def test_failed_next_operation_cannot_replace_previous_review(self):
        state = ResultReviewState()
        state.begin(request_text="first", profile="old", character_traits="old hair")
        state.publish({"workflow_id": "wai", "parameters": {"positive_prompt": "first prompt", "seed": 4}},
                      {"wai": {"kind": "t2i"}})
        before = state.details()
        state.begin(request_text="second", profile="new", character_traits="new hair")
        self.assertEqual(state.details(), before)
        state.finish()
        self.assertEqual(state.details(), before)
        state.begin(request_text="third")
        state.publish({"workflow_id": "wai", "parameters": {"positive_prompt": "third prompt", "seed": 7}},
                      {"wai": {"kind": "t2i"}})
        self.assertEqual(state.details()["request_text"], "third")
        self.assertEqual(state.details()["positive_prompt"], "third prompt")
        self.assertIsNone(state.details()["character_traits"])

    def test_review_snapshot_is_independent_of_editable_character_evidence(self):
        state = ResultReviewState()
        evidence = {"items": ["old"]}
        state.begin(character_analysis=evidence)
        evidence["items"].append("new")
        state.publish({"parameters": {"positive_prompt": "prompt"}}, {})
        result = state.details()
        result["character_analysis"]["items"].append("other")
        self.assertEqual(state.details()["character_analysis"], {"items": ["old"]})

    def test_pending_history_requests_coalesce_and_preserve_selection(self):
        messages = queue.Queue()
        gate = threading.Event()
        calls = []
        def read(*, limit):
            calls.append(limit)
            gate.wait(3)
            return [len(calls)]
        store = SimpleNamespace(list_entries=read, import_legacy_outputs=Mock())
        service = HistoryRefresh(store, messages.put)
        service.request("first", scan_legacy=False)
        service.request("second", scan_legacy=False)
        service.request(None, scan_legacy=True)
        gate.set()
        on_entries, on_error = Mock(), Mock()
        kind, first = messages.get(timeout=5)
        self.assertEqual(kind, "history_loaded")
        service.complete(*first, on_entries=on_entries, on_error=on_error)
        on_entries.assert_not_called()
        kind, second = messages.get(timeout=5)
        service.complete(*second, on_entries=on_entries, on_error=on_error)
        on_entries.assert_called_once_with([2], "second")
        on_error.assert_not_called()
        store.import_legacy_outputs.assert_called_once_with(limit=500)
        self.assertFalse(service.running)

    def test_event_router_dispatches_known_events_without_worker_ui_dependency(self):
        handler = Mock()
        router = EventRouter({"done": handler})
        self.assertTrue(router.dispatch("done", 123))
        handler.assert_called_once_with(123)
        self.assertFalse(router.dispatch("unknown", 4))
        self.assertEqual(router.kinds, {"done"})

    def test_ui_callback_error_does_not_drop_terminal_event(self):
        tasks = TaskController()
        tasks.begin()
        tasks.messages.put(("error", "test"))
        tasks.messages.put(("idle", None))
        callback = Mock(side_effect=RuntimeError("handler"))
        app = SimpleNamespace(tasks=tasks, messages=tasks.messages, root=Mock(),
                              event_router=EventRouter({"error": callback, "idle": lambda _: tasks.finish()}),
                              _log=Mock(), _tick_timing=Mock(), working=False)
        app._consume_messages = lambda: gui.Application._consume_messages(app)
        app.root.winfo_exists.return_value = True
        app._consume_messages()
        self.assertFalse(tasks.working)
        app.root.report_callback_exception.assert_called_once()
        app.root.after.assert_called_once()


if __name__ == "__main__":
    unittest.main()
