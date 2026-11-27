"""Foreground task lifecycle and event/estimate regressions without a display."""
import threading
import unittest
from comfy_orchestrator.jobs import JobCancellationRequested
from comfy_orchestrator.long_video_plan import LongVideoPaused
from comfy_orchestrator.task_controller import TaskController, worker_events
from comfy_orchestrator.timing import Estimate, report_estimate


class TaskControllerTests(unittest.TestCase):
    def test_success_is_delivered_off_ui_thread_and_ends_with_idle(self):
        owner = threading.get_ident()
        tasks = TaskController()
        tasks.begin()
        def operation():
            self.assertNotEqual(threading.get_ident(), owner)
            report_estimate(Estimate(12, 2))
            return 7
        thread = tasks.launch(operation, done_event="plan")
        thread.join(3)
        self.assertFalse(thread.is_alive())
        events = list(tasks.drain())
        self.assertEqual([kind for kind, _ in events], ["timing", "plan", "idle"])
        self.assertEqual(events[1], ("plan", 7))
        self.assertTrue(tasks.working)
        tasks.finish()
        self.assertFalse(tasks.working)

    def test_cancel_errors_and_long_pause_keep_terminal_contract(self):
        for exc, kwargs, expected in (
            (JobCancellationRequested("cancel"), {}, ("cancel_requested", "cancel")),
            (JobCancellationRequested("cancel"), {"cancel_as_progress": True}, ("progress", "cancel")),
            (LongVideoPaused("pause"), {}, ("progress", "pause / 長尺再開から続行できます")),
            (ValueError("error"), {}, ("error", "error")),
        ):
            with self.subTest(exc=exc, kwargs=kwargs):
                events = []
                def fail():
                    raise exc
                worker_events(fail, events.append, **kwargs)
                self.assertEqual(events, [expected, ("idle", None)])

    def test_one_active_task_and_cancellation_state(self):
        tasks = TaskController()
        with self.assertRaises(RuntimeError):
            tasks.launch(lambda: None)
        tasks.begin()
        with self.assertRaises(RuntimeError):
            tasks.begin()
        tasks.cancel()
        self.assertTrue(tasks.stop_event.is_set())
        tasks.launch(lambda: None).join(3)
        with self.assertRaises(RuntimeError):
            tasks.launch(lambda: None)
        tasks.finish()
        tasks.begin()
        self.assertFalse(tasks.stop_event.is_set())

    def test_bounded_drain_keeps_remaining_fifo_order(self):
        tasks = TaskController()
        for i in range(30):
            tasks.messages.put(("progress", i))
        self.assertEqual(list(tasks.drain()), [("progress", i) for i in range(24)])
        self.assertEqual(list(tasks.drain()), [("progress", i) for i in range(24, 30)])

    def test_timing_is_throttled_and_estimate_is_not_an_execution_deadline(self):
        now = [100.0]
        tasks = TaskController(clock=lambda: now[0])
        self.assertIsNone(tasks.timing_text())
        tasks.begin()
        self.assertEqual(tasks.timing_text(), "経過 00:00")
        now[0] = 100.2
        self.assertIsNone(tasks.timing_text())
        tasks.update_estimate({"estimate": Estimate(5, 3, True), "label": "生成待ち", "at": 100.0})
        now[0] = 102.0
        self.assertEqual(tasks.timing_text(), "経過 00:02 / 生成待ち 約00:03 (実測3件・尺換算)")
        now[0] = 108.0
        self.assertIn("推定超過", tasks.timing_text())
        self.assertTrue(tasks.working)
        self.assertFalse(tasks.stop_event.is_set())
        self.assertEqual(tasks.timing_text(finished=True), "処理時間 00:08")
        tasks.finish()
        self.assertIsNone(tasks.timing_text())


if __name__ == "__main__":
    unittest.main()
