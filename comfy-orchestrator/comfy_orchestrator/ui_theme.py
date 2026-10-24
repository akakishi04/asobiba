"""Accessible, dependency-free color and font styles for the Tk desktop UI.

The Win32 Japanese IME candidate popup is OS-owned; theme changes do not
intercept, simulate, or attempt to reposition IME conversion windows.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


PALETTES = {
    "dark": {
        "background": "#151B26",
        "surface": "#202A38",
        "input": "#111925",
        "text": "#F1F5FB",
        "muted": "#B9C7D8",
        "border": "#52647B",
        "accent": "#4F91F4",
        "accent_hover": "#3779DF",
        "selection": "#28548C",
        "button": "#2E4056",
        "button_hover": "#405977",
        "disabled": "#8695AA",
    },
    "light": {
        "background": "#E9EFF6",
        "surface": "#F6F9FD",
        "input": "#FFFFFF",
        "text": "#142238",
        "muted": "#485A70",
        "border": "#889CAF",
        "accent": "#245FC0",
        "accent_hover": "#174A9B",
        "selection": "#B4D4FF",
        "button": "#D9E5F2",
        "button_hover": "#C5D9EE",
        "disabled": "#748599",
    },
}


def palette(dark: bool = True) -> dict[str, str]:
    """Return an independent copy; callers cannot mutate global palette data."""
    return dict(PALETTES["dark" if dark else "light"])


def apply_ttk_theme(root: tk.Tk, dark: bool = True) -> dict[str, str]:
    """Apply a readable Windows-compatible ttk style without third-party libs."""
    p = palette(dark)
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.configure(background=p["background"])
    style.configure(".", font=("Meiryo UI", 10), background=p["surface"], foreground=p["text"])
    style.configure("TFrame", background=p["surface"])
    style.configure("TPanedwindow", background=p["background"])
    style.configure("TLabel", background=p["surface"], foreground=p["text"])
    style.configure("Muted.TLabel", background=p["surface"], foreground=p["muted"])
    style.configure("Heading.TLabel", font=("Meiryo UI", 17, "bold"), background=p["surface"], foreground=p["text"])
    style.configure("TLabelframe", background=p["surface"], borderwidth=1, bordercolor=p["border"], relief="solid")
    style.configure("TLabelframe.Label", background=p["surface"], foreground=p["text"], font=("Meiryo UI", 10, "bold"))
    style.configure("Section.TLabelframe.Label", background=p["surface"], foreground=p["text"], font=("Meiryo UI", 10, "bold"))

    style.configure(
        "TEntry", padding=(7, 5), fieldbackground=p["input"], foreground=p["text"],
        background=p["surface"], bordercolor=p["border"], insertcolor=p["text"],
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", p["surface"]), ("readonly", p["input"])],
        foreground=[("disabled", p["disabled"])],
    )
    style.configure(
        "TCombobox", padding=(7, 5), fieldbackground=p["input"], foreground=p["text"],
        background=p["button"], arrowcolor=p["text"], bordercolor=p["border"],
        selectbackground=p["input"], selectforeground=p["text"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", p["input"]), ("disabled", p["surface"])],
        foreground=[("readonly", p["text"]), ("disabled", p["disabled"])],
        selectbackground=[("readonly", p["input"])],
        selectforeground=[("readonly", p["text"])],
    )
    style.configure("TCheckbutton", background=p["surface"], foreground=p["text"], padding=(0, 2))
    style.map(
        "TCheckbutton", background=[("active", p["surface"])],
        foreground=[("disabled", p["disabled"])],
    )
    style.configure(
        "TButton", font=("Meiryo UI", 10), padding=(10, 6),
        background=p["button"], foreground=p["text"], bordercolor=p["border"],
    )
    style.map(
        "TButton",
        background=[("active", p["button_hover"]), ("pressed", p["accent_hover"])],
        foreground=[("disabled", p["disabled"])],
    )
    style.configure(
        "Run.TButton", font=("Meiryo UI", 10, "bold"), padding=(14, 9),
        background=p["accent"], foreground="#FFFFFF", bordercolor=p["accent"],
    )
    style.map(
        "Run.TButton",
        background=[("active", p["accent_hover"]), ("pressed", p["accent_hover"])],
        foreground=[("disabled", p["disabled"])],
    )
    style.configure(
        "Horizontal.TProgressbar", troughcolor=p["input"],
        background=p["accent"], bordercolor=p["border"], lightcolor=p["accent"],
        darkcolor=p["accent"],
    )

    # The dropdown popup is a native Tk listbox rather than a ttk widget.
    root.option_add("*TCombobox*Listbox.background", p["input"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["selection"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["text"])
    root.option_add("*TCombobox*Listbox.font", ("Meiryo UI", 10))
    return p


def style_text_widget(widget: tk.Widget, colors: dict[str, str], *, muted: bool = False) -> None:
    """Style input, logs, and gallery lists, including cursor/selection contrast."""
    kwargs = {
        "background": colors["input"],
        "foreground": colors["muted"] if muted else colors["text"],
        "selectbackground": colors["selection"],
        "selectforeground": colors["text"],
        "highlightthickness": 1,
        "highlightbackground": colors["border"],
        "highlightcolor": colors["accent"],
        "relief": "flat",
        "borderwidth": 0,
    }
    if isinstance(widget, (tk.Text, tk.Entry)):
        kwargs["insertbackground"] = colors["text"]
    widget.configure(**kwargs)
