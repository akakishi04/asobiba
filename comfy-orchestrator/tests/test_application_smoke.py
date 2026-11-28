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
                    self.assertEqual(app.image_reasoning.get(), "OFF")
                    self.assertEqual(tuple(app.image_reasoning_box.cget("values")), ("OFF", "ON", "自動"))
                    app.image_reasoning.set("ON")
                    self.assertEqual(app._collect_config()["llm"]["image_reasoning"], "on")
                    app.image_reasoning.set("OFF")
                    app._open_model_comparison()
                    self.assertIsNotNone(app.comparison_window)
                    self.assertGreaterEqual(len(app.comparison_window.choices), 2)
                    app._close_model_comparison()
                    self.assertIsNone(app.comparison_window)
                    for mode in ("video", "continuous", "image"):
                        app.generation_mode.set(mode)
                        app._on_generation_mode_choice()
                        root.update_idletasks()
                        self.assertEqual(app.generation_mode.get(), mode)
                    # Real Tk manager: registration is explicit, persistent and routes
                    # an otherwise unknown filename to the selected image adapter.
                    from comfy_orchestrator.model_registry import load_registrations, image_key, PROFILES
                    from comfy_orchestrator.model_profiles import ANIMA_ID
                    custom_file = "custom-weight.safetensors"
                    app.generation_inventory = {"UNETLoader": [custom_file],
                                                "CheckpointLoaderSimple": [core.DEFAULT_SDXL_CHECKPOINT]}
                    app._apply_generation_model_choices()
                    app._open_model_manager()
                    manager = app.model_manager
                    manager.profile.set(PROFILES["anima"].label)
                    manager._change_profile()
                    self.assertEqual(str(manager.save_button.cget("state")), "disabled")
                    manager.filename.set(custom_file)
                    manager.steps.set("25")
                    manager.cfg.set("3.25")
                    manager._sync_file_choice()
                    manager._register()
                    self.assertEqual(load_registrations(app._registry_path)[0].filename, custom_file)
                    key = image_key("anima", custom_file)
                    label = next(label for label, choice in app._image_choices.items() if choice.filename == key)
                    app.workflow_choice.set(label)
                    app._on_workflow_choice()
                    self.assertEqual(app._active_workflow(), ANIMA_ID)
                    self.assertEqual(app.anima_model.get(), key)
                    self.assertEqual((app.steps.get(), app.cfg.get()), ("25", "3.25"))
                    manager.destroy()
                    app.workflow_choice.set("SDXL · " + core.DEFAULT_SDXL_CHECKPOINT)
                    app._on_workflow_choice()
                    self.assertEqual(app._active_workflow(), "wai_t2i_basic")

                    from comfy_orchestrator.h3_model_picker import OPENING, REFERENCE, TEXT_ONLY
                    filename = "10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_HQ.safetensors"
                    base = core.h3_hybrid_model_key(filename, reference_only=False)
                    ref = core.h3_hybrid_model_key(filename, reference_only=True)
                    app.generation_inventory = {"UNETLoader": [filename, "s3_ref2va_w4a8.safetensors"]}
                    app.generation_mode.set("video")
                    app.workflow.set(core.H3_I2V_ID)
                    app._on_generation_mode_choice()
                    app.h3_model.set(core.h3_model_label(ref))
                    app._apply_generation_model_choices()
                    self.assertEqual(app.h3_model_display.get(), "10Eros Max · Learned HQ")
                    self.assertEqual(app.h3_input_mode.get(), TEXT_ONLY)
                    self.assertEqual(str(app.h3_input_mode_box.cget("state")), "disabled")
                    self.assertEqual(app._h3_choices()["h3_model"], ref)
                    self.assertEqual(tuple(app.h3_model_box.cget("values")).count("10Eros Max · Learned HQ"), 1)
                    app.reference_image.set(str(local / "reference.png"))
                    self.assertEqual(app.h3_input_mode.get(), REFERENCE)
                    self.assertEqual(str(app.h3_input_mode_box.cget("state")), "readonly")
                    app.h3_input_mode.set(OPENING)
                    app._on_h3_input_mode_choice()
                    self.assertEqual(app._h3_choices()["h3_model"], base)
                    app.reference_image.set("")
                    self.assertEqual(app.h3_input_mode.get(), TEXT_ONLY)
                    app.generation_mode.set("continuous")
                    app._on_generation_mode_choice()
                    app.generation_mode.set("video")
                    app._on_generation_mode_choice()
                    self.assertEqual(app._h3_choices()["h3_model"], base)
                    self.assertEqual(app.h3_model_display.get(), "10Eros Max · Learned HQ")
                    app.generation_mode.set("image")
                    app._on_generation_mode_choice()
                    app.review.begin(request_text="first", profile="test")
                    app._set_busy("test")
                    self.assertTrue(app.working)
                    self.assertEqual(str(app.run_button.cget("state")), "disabled")
                    output = app.history_store.outputs / "sample.png"
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

                    # The library's DB-wide query and metadata changes also use
                    # the same real history widgets.
                    from comfy_orchestrator.history import HistoryQuery
                    entry = app.history_store.record(prompt_id="smoke-history", workflow_id="wai_t2i_basic",
                        kind="t2i", request_text="library test", parameters={"positive_prompt": "tree"},
                        images=[output])
                    app.history_panel.apply_page(app.history_store.query_entries(app.history_panel.query()),
                                                 entry.id)
                    self.assertEqual(app.history_panel.selected_entries()[0].id, entry.id)
                    app.history_panel.thumbnail_mode.set(True)
                    app.history_panel._toggle_thumbnails()
                    self.assertEqual(str(app.history_panel.history_table.cget("style")), "HistoryThumb.Treeview")
                    app.history_panel.thumbnail_mode.set(False)
                    app.history_panel._toggle_thumbnails()
                    self.assertEqual(str(app.history_panel.history_table.cget("style")), "Treeview")
                    app.history_store.set_flags([entry.id], favorite=True)
                    app.history_panel.favorite_filter.set(True)
                    page = app.history_store.query_entries(app.history_panel.query())
                    app.history_panel.apply_page(page, entry.id)
                    self.assertEqual(app.history_panel.selected_entries()[0].favorite, True)
                    app.history_store.set_flags([entry.id], archived=True)
                    app.history_panel.apply_page(app.history_store.query_entries(app.history_panel.query()))
                    self.assertEqual(app.history_panel.selected_entries(), [])
                    app.history_panel.archive_filter.set(True)
                    app.history_panel.apply_page(app.history_store.query_entries(app.history_panel.query()), entry.id)
                    self.assertTrue(app.history_panel.selected_entries()[0].archived)
                    self.assertTrue(output.is_file())
                    app.history_panel.favorite_filter.set(False)
                    app.history_panel.archive_filter.set(False)

                    # Transfer changes only explicitly selected fields and never
                    # executes a generation or silently restores the old project.
                    from comfy_orchestrator.material_transfer import Material, Transfer
                    material = Material("test", output.resolve())
                    original_text = app.prompt.get("1.0", "end-1c")
                    app._apply_material_transfer(Transfer(material, "video", None, {}), output)
                    self.assertEqual(app.generation_mode.get(), "video")
                    self.assertEqual(app.reference_image.get(), str(output))
                    self.assertEqual(app.prompt.get("1.0", "end-1c"), original_text)
                    app._apply_material_transfer(Transfer(material, "continuous", "new scene",
                        {"h3_steps": "8", "seed": "77"}), output)
                    self.assertEqual(app.generation_mode.get(), "continuous")
                    self.assertIsNone(app.project_workspace.draft)
                    self.assertEqual(app.prompt.get("1.0", "end-1c"), "new scene")
                    self.assertEqual(app.seed.get(), "77")
                    self.assertEqual(app.tabs.select(), str(app.project_workspace))
                    app.generation_mode.set("image")
                    app._on_generation_mode_choice()
                    root.update_idletasks()
                    self.assertFalse(callback_errors, callback_errors)

                    # Open a real refinement window and run its prepared plan.
                    from comfy_orchestrator.generation_controller import GenerationController
                    from comfy_orchestrator.image_adjust import I2I
                    image_entry = app.history_store.record(
                        prompt_id="adjust-source", workflow_id="wai_t2i_basic", kind="t2i",
                        request_text="tree", parameters={"positive_prompt": "tree", "seed": 19},
                        images=[output])
                    app._open_adjust(image_entry.id)
                    while True:
                        kind, data = app.messages.get(timeout=5)
                        app.event_router.dispatch(kind, data)
                        if kind == "idle":
                            break
                    window = app.adjust_window
                    self.assertIsNotNone(window)
                    self.assertEqual(str(window.generate_button.cget("state")), "normal")
                    window.editors["positive_prompt"].delete("1.0", "end")
                    window.editors["positive_prompt"].insert("1.0", "green tree")
                    window.numeric["steps"].set("12")
                    derived = app.history_store.outputs / "adjusted.png"
                    image.write(str(derived), format="png")
                    def prepared(controller, request, workflow, params, **kwargs):
                        self.assertEqual(workflow, "wai_t2i_basic")
                        self.assertEqual(params["positive_prompt"], "green tree")
                        self.assertEqual(params["steps"], 12)
                        self.assertEqual(params["seed"], 19)
                        self.assertIsNone(kwargs["image"])
                        return {"status": "completed", "workflow_id": workflow,
                                "parameters": params}, [derived], "adjusted-history"
                    with patch.object(GenerationController, "generate_prepared", prepared):
                        window._act("generate")
                        self.assertTrue(app.working)
                        while True:
                            kind, data = app.messages.get(timeout=5)
                            app.event_router.dispatch(kind, data)
                            if kind == "idle":
                                break
                    self.assertIs(app.adjust_window, window)
                    self.assertEqual(window.selected_result(), derived)
                    self.assertEqual(str(window.generate_button.cget("state")), "normal")
                    window._act("adopt")
                    self.assertEqual(app.adjust_draft.base_image.read_bytes(), derived.read_bytes())
                    self.assertIsNone(app.adjust_draft.assets["image"])
                    with patch.object(gui.messagebox, "askyesno", return_value=True):
                        window._act("i2i")
                    self.assertEqual(app.adjust_draft.workflow_id, I2I)
                    self.assertEqual(app.adjust_draft.assets["image"], app.adjust_draft.base_image)
                    self.assertNotIn("width", window.numeric)
                    self.assertIn("denoise", window.numeric)
                    adjust_folder = Path(app.adjust_draft._temporary.name)
                    app._close_adjust()
                    self.assertFalse(adjust_folder.exists())
                    self.assertTrue(derived.is_file())
                    self.assertFalse(callback_errors, callback_errors)

                    # Usage is captured at the real transport boundary in a worker,
                    # and the operations panel renders persisted totals without an API.
                    from comfy_orchestrator import lmstudio
                    from comfy_orchestrator.operations_ui import OperationsWindow
                    with patch.object(lmstudio, "_open_json", return_value={
                            "usage": {"prompt_tokens": 123, "completion_tokens": 45}}):
                        app._set_busy("usage test")
                        def measured():
                            lmstudio._request(config["llm"], "/v1/chat/completions", {"model": "test"})
                            return "usage test finished"
                        app._launch_generation(measured, done_event="progress",
                                               usage={"action": "review", "workflow": "wai_t2i_basic"})
                        while True:
                            kind, data = app.messages.get(timeout=5)
                            app.event_router.dispatch(kind, data)
                            if kind == "idle":
                                break
                    usage = app.llm_usage.report()
                    self.assertEqual((usage["total"]["input_tokens"], usage["total"]["output_tokens"]), (123, 45))
                    self.assertIn("IN 123 / OUT 45", app.log.get("1.0", "end"))
                    panel = OperationsWindow(root, local, on_refresh=lambda: None,
                                             on_clear_cache=lambda: None, on_export_usage=lambda: None)
                    try:
                        panel.update_usage(usage)
                        self.assertIn("IN 123 / OUT 45", panel.usage_summary.get())
                        self.assertEqual(len(panel.usage_operations.get_children()), 2)
                        self.assertEqual(len(panel.usage_purposes.get_children()), 1)
                    finally:
                        panel.window.destroy()

                    # The new review modal uses real Tk controls but no service.
                    from comfy_orchestrator.single_prompt import SinglePromptDraft
                    from unittest.mock import Mock
                    temporary = tempfile.TemporaryDirectory()
                    controller = Mock(config=config, cancel_event=app.stop_event)
                    draft = SinglePromptDraft(controller, {
                        "workflow_id": "wai_t2i_basic",
                        "parameters": {"positive_prompt": "tree", "negative_prompt": "", "seed": 9},
                    }, "tree", {}, {"prompt_profile": None, "character_traits": None,
                                     "character_analysis": None, "character_references": ()}, temporary)
                    try:
                        root.deiconify()
                        root.update_idletasks()
                        app._set_busy("review")
                        app.event_router.dispatch("single_prompt_ready", draft)
                        app.event_router.dispatch("idle", None)
                        root.update_idletasks()
                        window = app.single_window
                        self.assertIsNotNone(window)
                        self.assertEqual(window.language.get(), "英語")
                        window.editors["positive_prompt"].delete("1.0", "end")
                        window.editors["positive_prompt"].insert("1.0", "edited tree")
                        window._read()
                        self.assertEqual(draft.parameters["positive_prompt"], "edited tree")
                        app._close_single_prompt()
                        self.assertIsNone(app.single_window)
                        self.assertFalse(Path(temporary.name).exists())
                        self.assertFalse(callback_errors, callback_errors)
                    finally:
                        draft.close()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
