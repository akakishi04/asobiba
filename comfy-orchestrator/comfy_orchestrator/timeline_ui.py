"""Modal editor for the exact prompts submitted to continuous H3."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .parameters import OrchestratorError
from .timeline import FPS, segment_windows, validate_prompt_plan


def edit_prompt_plan(parent, plan, frames, seconds, *, preview_only=False):
    """Return a validated edited copy, or None on cancel. Tk main thread only."""
    windows = segment_windows(frames, seconds)
    draft = validate_prompt_plan(plan, len(windows))
    result = None
    dialog = tk.Toplevel(parent)
    dialog.title("連続動画 · プロンプト計画")
    dialog.transient(parent)
    dialog.geometry(f"{min(780, parent.winfo_screenwidth() - 60)}x"
                    f"{min(620, parent.winfo_screenheight() - 100)}")
    dialog.minsize(440, 350)
    outer = ttk.Frame(dialog, padding=12)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text=f"共通プロンプト ＋ {len(windows)}区間 / {seconds}秒",
              font=("Meiryo UI", 11, "bold")).pack(anchor="w")
    ttk.Label(outer, text="共通欄には維持する特徴、区間欄にはその区間の動作を記述します。"
              "\n以下の文が実際にH3へ送信されます（英語の自然文を推奨）。",
              wraplength=650).pack(anchor="w", pady=(4, 6))
    ttk.Label(outer, text="共通プロンプト").pack(anchor="w")
    common = scrolledtext.ScrolledText(outer, height=4, wrap="word", undo=True,
                                      font=("Meiryo UI", 10))
    common.pack(fill="x", pady=(2, 8))
    common.insert("1.0", draft["common"])

    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True)
    left = ttk.Frame(body)
    left.pack(side="left", fill="y", padx=(0, 8))
    scroll = ttk.Scrollbar(left, orient="vertical")
    scroll.pack(side="right", fill="y")
    entries = tk.Listbox(left, width=25, exportselection=False, yscrollcommand=scroll.set,
                         font=("Meiryo UI", 10))
    entries.pack(side="left", fill="y", expand=True)
    scroll.configure(command=entries.yview)
    for window in windows:
        entries.insert("end", f'{window["index"]:02d}  '
                       f'{window["start_frame"]/FPS:6.2f}–{window["end_frame"]/FPS:6.2f}s')
    right = ttk.Frame(body)
    right.pack(side="left", fill="both", expand=True)
    label = ttk.Label(right)
    label.pack(anchor="w")
    segment = scrolledtext.ScrolledText(right, height=8, wrap="word", undo=True,
                                       font=("Meiryo UI", 10))
    segment.pack(fill="both", expand=True, pady=(2, 0))
    active = None

    def save_active():
        if active is not None:
            draft["segments"][active] = segment.get("1.0", "end-1c")

    def select(_event=None):
        nonlocal active
        selection = entries.curselection()
        if not selection or selection[0] == active:
            return
        save_active()
        active = selection[0]
        window = windows[active]
        label.configure(text=f"区間 {active + 1} / {len(windows)}"
                        f" · {window['generation_frames']}フレーム生成")
        segment.delete("1.0", "end")
        segment.insert("1.0", draft["segments"][active])
        segment.edit_reset()

    def accept():
        nonlocal result
        save_active()
        draft["common"] = common.get("1.0", "end-1c")
        try:
            result = validate_prompt_plan(draft, len(windows))
        except OrchestratorError as exc:
            messagebox.showerror("長尺プロンプト計画", str(exc), parent=dialog)
            return
        dialog.destroy()

    entries.bind("<<ListboxSelect>>", select)
    entries.selection_set(0)
    select()
    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="計画を保持" if preview_only else "確定して生成",
               command=accept).pack(side="right", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result
