"""Build real Tk widgets where a display is available; no GPU or API access."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from comfy_orchestrator import gui, core


class ApplicationSmokeTests(unittest.TestCase):
    def test_window_modes_result_publication_and_idle_recovery(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        callback_errors = []
        root.report_callback_exception = lambda *args: callback_errors.append(args)
        try:
            config = core.load_config(gui.EXAMPLE)
            with tempfile.TemporaryDirectory() as folder:
                local = Path(folder)
                with patch.multiple(gui, ROOT=local, CONFIG=local / "config.json",
                                    OUTPUTS=local / "outputs"), \
                        patch.object(gui, "bootstrap_config", return_value=config), \
                        patch.object(gui.Application, "_refresh_generation_models"), \
                        patch.object(gui.Application, "_refresh_history"), \
                        patch.object(gui.Application, "_refresh_projects"):
                    app = gui.Application(root)
                    root.update_idletasks()
                    for mode in ("video", "continuous", "image"):
                        app.generation_mode.set(mode)
                        app._on_generation_mode_choice()
                        root.update_idletasks()
                        self.assertEqual(app.generation_mode.get(), mode)
                    app.review.begin(request_text="first", profile="test")
                    app._set_busy("test")
                    self.assertTrue(app.working)
                    self.assertEqual(str(app.run_button.cget("state")), "disabled")
                    output = local / "sample.png"
                    image = tk.PhotoImage(master=root, width=4, height=4)
                    image.put("#ffffff", to=(0, 0, 4, 4))
                    image.write(str(output), format="png")
                    result = {"status": "completed", "workflow_id": "wai_t2i_basic",
                              "parameters": {"positive_prompt": "first prompt", "seed": 8}}
                    self.assertTrue(app.event_router.dispatch("done", (result, [output], "history")))
                    self.assertTrue(app.event_router.dispatch("idle", None))
                    self.assertFalse(app.working)
                    self.assertEqual(str(app.run_button.cget("state")), "normal")
                    self.assertEqual(app.result_panel.selected_path(), output)
                    self.assertEqual(app.review.details()["request_text"], "first")
                    app.review.begin(request_text="failed")
                    app._set_busy("second")
                    with patch.object(gui.messagebox, "showerror"):
                        app.event_router.dispatch("error", "test error")
                    app.event_router.dispatch("idle", None)
                    self.assertFalse(app.working)
                    self.assertEqual(app.review.details()["request_text"], "first")
                    self.assertEqual(app.result_panel.selected_path(), output)
                    app.tabs.select(app.history_panel)
                    root.update_idletasks()
                    self.assertFalse(callback_errors, callback_errors)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
