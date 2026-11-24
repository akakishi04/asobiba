"""Optional native file drag-and-drop support for the Windows Tk GUI.

The GUI continues to work with ordinary file-picker buttons when
tkinterdnd2 (and the bundled tkdnd extension) is unavailable.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Iterable


def enable_native_dnd(root: tk.Misc) -> bool:
    """Load TkDnD into the existing Tk interpreter; never require it to start."""
    try:
        from tkinterdnd2 import TkinterDnD

        # The modern package supports existing tkinter.Tk() roots.
        # Loading once patches BaseWidget with drop_target_register/dnd_bind.
        TkinterDnD.require(root)
    except (ImportError, AttributeError, OSError, RuntimeError, tk.TclError):
        return False
    return True


def split_dropped_paths(tk_interpreter, raw_data: str) -> tuple[str, ...]:
    """Split the native Tcl path list, preserving paths with spaces/braces.

    Do NOT use str.split(): a Windows file list may contain names wrapped in
    Tcl braces, and backslashes are significant in those names.
    """
    if not isinstance(raw_data, str) or not raw_data.strip():
        return ()
    return tuple(tk_interpreter.splitlist(raw_data))


def register_file_drop(widget: tk.Misc, callback: Callable[[tuple[str, ...]], None]) -> bool:
    """Register a DND_FILES target; callbacks execute on Tk's main thread."""
    if not callable(getattr(widget, "drop_target_register", None)):
        return False
    if not callable(getattr(widget, "dnd_bind", None)):
        return False
    try:
        from tkinterdnd2 import DND_FILES

        widget.drop_target_register(DND_FILES)

        def dropped(event):
            callback(split_dropped_paths(widget.tk, event.data))
            return "copy"

        widget.dnd_bind("<<Drop>>", dropped)
    except (ImportError, AttributeError, RuntimeError, tk.TclError):
        return False
    return True
