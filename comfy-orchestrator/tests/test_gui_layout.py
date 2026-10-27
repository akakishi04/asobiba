"""No-display layout regressions for low-height Windows desktop screens.

The actual user-visible Tk layout is verified separately on Windows; these
tests cover the geometry and the scrolling / pinned-controls structure.
"""

from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace

from comfy_orchestrator import gui


class InitialGeometryTests(unittest.TestCase):
    def test_startup_fits_common_displays_including_768p_and_scaled_desktops(self):
        for width, height in (
            (1920, 1080),
            (1600, 900),
            (1366, 768),
            (1280, 720),
            (1024, 600),
            (800, 600),
        ):
            with self.subTest(screen=(width, height)):
                w, h, x, y, min_w, min_h = gui.initial_window_bounds(width, height)
                self.assertLessEqual(w + x, width)
                self.assertLessEqual(h + y + 40, height)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(min_w, w)
                self.assertLessEqual(min_h, h)

    def test_minimum_window_height_does_not_exceed_display(self):
        _, h, _, _, _, minimum = gui.initial_window_bounds(1366, 768)
        self.assertLessEqual(h, 650)
        self.assertLessEqual(minimum, h)

    def test_preview_subsampling_fits_available_space(self):
        samples = [
            (1024, 1024, 320, 210, 400),
            (768, 1024, 200, 90, 400),
            (512, 512, 1, 1, 220),
        ]
        for width, height, view_w, view_h, cap in samples:
            with self.subTest(source=(width, height), viewport=(view_w, view_h)):
                factor = gui.preview_subsample(width, height, view_w, view_h, cap)
                self.assertGreaterEqual(factor, 1)
                allowed_w = max(80, min(cap, view_w if view_w >= 40 else cap))
                allowed_h = max(80, min(cap, view_h if view_h >= 40 else cap))
                self.assertLessEqual((width + factor - 1) // factor, allowed_w)
                self.assertLessEqual((height + factor - 1) // factor, allowed_h)

    def test_gui_reserves_footer_and_action_controls_before_expanding_content(self):
        source = inspect.getsource(gui.Application._build)
        self.assertLess(
            source.index('footer.pack(side="bottom", fill="x")'),
            source.index('main = ttk.Panedwindow(layout, orient="horizontal")'),
        )
        self.assertLess(
            source.index('action_row.pack(side="bottom", fill="x"'),
            source.index('form_holder = ttk.Frame(prompt_panel)'),
        )
        self.assertLess(
            source.index('history_actions.pack(side="bottom"'),
            source.index('self.history_table = ttk.Treeview('),
        )
        self.assertLess(
            source.index('preview_actions.pack(side="bottom"'),
            source.index('self.image_label = ttk.Label('),
        )
        self.assertIn('self.form_canvas.create_window(', source)
        self.assertIn('self.form_canvas.configure(yscrollcommand=', source)
        self.assertNotIn('self.logs_panel.pack(fill="x")', source)


class ScrollingTests(unittest.TestCase):
    class Canvas:
        def __init__(self, first=0.2, last=0.7):
            self.first = first
            self.last = last
            self.scrolled = []
            self.items = []
            self.configured = []

        def yview(self):
            return self.first, self.last

        def yview_scroll(self, amount, unit):
            self.scrolled.append((amount, unit))

        def itemconfigure(self, window, **kwargs):
            self.items.append((window, kwargs))

        def bbox(self, item):
            return (0, 0, 350, 890)

        def configure(self, **kwargs):
            self.configured.append(kwargs)

    def test_scroll_only_when_pointer_is_over_the_form(self):
        form = object()
        child = SimpleNamespace(master=SimpleNamespace(master=form))
        canvas = self.Canvas()
        fake = SimpleNamespace(options_form=form, form_canvas=canvas)

        event = SimpleNamespace(widget=child, num=None, delta=-120)
        self.assertEqual(gui.Application._on_form_mousewheel(fake, event), "break")
        self.assertEqual(canvas.scrolled, [(3, "units")])

        event.widget = SimpleNamespace(master=None)
        self.assertIsNone(gui.Application._on_form_mousewheel(fake, event))
        self.assertEqual(len(canvas.scrolled), 1)

    def test_scroll_fallback_for_linux_mouse_wheel(self):
        form = object()
        child = SimpleNamespace(master=form)
        canvas = self.Canvas()
        fake = SimpleNamespace(options_form=form, form_canvas=canvas)
        event = SimpleNamespace(widget=child, num=4, delta=0)
        self.assertEqual(gui.Application._on_form_mousewheel(fake, event), "break")
        self.assertEqual(canvas.scrolled, [(-3, "units")])

    def test_no_scroll_when_all_settings_already_fit(self):
        form = object()
        child = SimpleNamespace(master=form)
        canvas = self.Canvas(0.0, 1.0)
        fake = SimpleNamespace(options_form=form, form_canvas=canvas)
        self.assertIsNone(
            gui.Application._on_form_mousewheel(
                fake, SimpleNamespace(widget=child, delta=-120, num=None),
            )
        )
        self.assertFalse(canvas.scrolled)

    def test_resize_sets_inner_frame_width_and_scroll_bounds(self):
        canvas = self.Canvas()
        fake = SimpleNamespace(
            form_canvas=canvas, form_window="inner", _sync_form_scrollregion=lambda: None,
        )
        gui.Application._size_form_to_canvas(fake, 450)
        self.assertEqual(canvas.items, [("inner", {"width": 450})])
        gui.Application._sync_form_scrollregion(fake)
        self.assertEqual(canvas.configured, [{"scrollregion": (0, 0, 350, 890)}])

    def test_log_panel_is_hidden_on_start_and_can_be_shown(self):
        class Panel:
            def __init__(self):
                self.last = None
            def pack(self, **kwargs):
                self.last = ("shown", kwargs)
            def pack_forget(self):
                self.last = ("hidden", {})
        class Toggle:
            def __init__(self):
                self.last = None
            def configure(self, **kwargs):
                self.last = kwargs
        fake = SimpleNamespace(
            logs_visible=False, logs_panel=Panel(), log_toggle=Toggle(),
        )
        gui.Application._toggle_logs(fake)
        self.assertTrue(fake.logs_visible)
        self.assertEqual(fake.log_toggle.last["text"], "ログを隠す")
        gui.Application._toggle_logs(fake)
        self.assertFalse(fake.logs_visible)
        self.assertEqual(fake.logs_panel.last[0], "hidden")


if __name__ == "__main__":
    unittest.main()
