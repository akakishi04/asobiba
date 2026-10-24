"""Best-effort Windows IME composition font correction for Tk text widgets.

On Windows/Tk, uncommitted Japanese text can be drawn by the OS IME at a
larger default font size, independently of the widget's font= option.
Use IMM32's ImmSetCompositionFontW to align the conversion text's logical font.
This does not resize or intercept the separate IME candidate list window.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
import tkinter as tk
from tkinter import font as tkfont


IME_KEYCODE = 229  # VK_PROCESSKEY delivered during IME composition on Windows.
LOGPIXELSY = 90
LF_FACESIZE = 32


class LOGFONTW(ctypes.Structure):
    """Windows LOGFONTW layout (the native calls are Windows-only)."""

    _fields_ = [
        ("lfHeight", wintypes.LONG),
        ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG),
        ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG),
        ("lfItalic", ctypes.c_ubyte),
        ("lfUnderline", ctypes.c_ubyte),
        ("lfStrikeOut", ctypes.c_ubyte),
        ("lfCharSet", ctypes.c_ubyte),
        ("lfOutPrecision", ctypes.c_ubyte),
        ("lfClipPrecision", ctypes.c_ubyte),
        ("lfQuality", ctypes.c_ubyte),
        ("lfPitchAndFamily", ctypes.c_ubyte),
        ("lfFaceName", ctypes.c_wchar * LF_FACESIZE),
    ]


def logical_font(family: str, size: int, dpi: int, bold: bool = False) -> LOGFONTW:
    """Translate Tk points (or negative pixel size) into a Windows LOGFONTW."""
    face = (family or "Meiryo UI").strip()
    if not isinstance(size, int) or not size or not isinstance(dpi, int) or dpi <= 0:
        raise ValueError("Invalid Tk font size or DPI")
    if len(face) >= LF_FACESIZE:
        face = face[: LF_FACESIZE - 1]
    face_size = -max(1, round(size * dpi / 72)) if size > 0 else size
    result = LOGFONTW()
    result.lfHeight = face_size
    result.lfWeight = 700 if bold else 400
    result.lfCharSet = 128  # SHIFTJIS_CHARSET for Japanese Windows fonts
    result.lfFaceName = face
    return result


def _native_api():
    """Initialize 64-bit-safe Win32 prototypes on demand."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    imm32 = ctypes.WinDLL("imm32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    user32.GetFocus.argtypes = []
    user32.GetFocus.restype = wintypes.HWND
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    gdi32.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi32.GetDeviceCaps.restype = ctypes.c_int

    imm32.ImmGetContext.argtypes = [wintypes.HWND]
    imm32.ImmGetContext.restype = wintypes.HANDLE
    imm32.ImmSetCompositionFontW.argtypes = [wintypes.HANDLE, ctypes.POINTER(LOGFONTW)]
    imm32.ImmSetCompositionFontW.restype = wintypes.BOOL
    imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    imm32.ImmReleaseContext.restype = wintypes.BOOL
    return user32, imm32, gdi32


def _is_windows() -> bool:
    return os.name == "nt"


def sync_native_ime_font(widget) -> bool:
    """Use the text widget's actual font for uncommitted IME text.

    Returns False if an IME context is unavailable. Failures never block input.
    Called on the Tk main/UI thread, not on a background worker.
    """
    if not _is_windows():
        return False
    try:
        if widget.focus_get() is not widget:
            return False
        # Resolve named, tuple, or Tcl font specifications, including DPI scaling.
        spec = tkfont.Font(root=widget, font=widget.cget("font"))
        actual = spec.actual()
        user32, imm32, gdi32 = _native_api()
        focused = user32.GetFocus()
        widget_handle = int(widget.winfo_id())
        top_handle = int(widget.winfo_toplevel().winfo_id())
        candidates = list(dict.fromkeys(h for h in (focused, widget_handle, top_handle) if h))
        for handle in candidates:
            h_imc = imm32.ImmGetContext(handle)
            if not h_imc:
                continue
            try:
                h_dc = user32.GetDC(handle)
                try:
                    dpi = gdi32.GetDeviceCaps(h_dc, LOGPIXELSY) if h_dc else 96
                finally:
                    if h_dc:
                        user32.ReleaseDC(handle, h_dc)
                new_font = logical_font(
                    str(actual["family"]), int(actual["size"]), max(1, dpi),
                    bold=actual.get("weight") == "bold",
                )
                if imm32.ImmSetCompositionFontW(h_imc, ctypes.byref(new_font)):
                    return True
            finally:
                imm32.ImmReleaseContext(handle, h_imc)
    except (tk.TclError, AttributeError, OSError, RuntimeError, ValueError, TypeError):
        # Windows/Tk IME support varies; leave the normal input path untouched.
        return False
    return False


def install_native_ime_font(widget) -> None:
    """Refresh composition font when focusing the editor or starting IME text."""
    if not _is_windows():
        return

    def on_focus(_event):
        # The WM_SETFOCUS processing must finish before querying IMM context.
        widget.after_idle(lambda: sync_native_ime_font(widget))

    def on_key(event):
        if getattr(event, "keycode", None) == IME_KEYCODE:
            sync_native_ime_font(widget)

    widget.bind("<FocusIn>", on_focus, add="+")
    widget.bind("<KeyPress>", on_key, add="+")
