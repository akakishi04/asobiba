"""Modal editor for the exact prompts submitted to continuous H3."""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .parameters import OrchestratorError
from .timeline import (FPS, segment_windows, validate_prompt_plan, validate_cut_frames,
                       parse_cut_seconds, format_cut_seconds, default_cut_frames)


@dataclass(frozen=True)
class CutDurationChange:
    frames: list[int]


def edit_cut_durations(parent, cut_frames):
    """Edit the desired retained duration of each cut; no model calls."""
    cuts = validate_cut_frames(cut_frames)
    result = None
    dialog = tk.Toplevel(parent)
    dialog.title("連続動画 · カット尺設定")
    dialog.transient(parent)
    dialog.geometry(f"{min(640, parent.winfo_screenwidth() - 60)}x"
                    f"{min(510, parent.winfo_screenheight() - 100)}")
    dialog.minsize(420, 320)
    outer = ttk.Frame(dialog, padding=12)
    outer.pack(fill="both", expand=True)
    summary = ttk.Label(outer, font=("Meiryo UI", 11, "bold"))
    summary.pack(anchor="w")
    ttk.Label(outer, text="各カット1～15秒・合計5分まで。24fpsの最も近いフレームに丸めます。"
              "\nH3は対応フレーム数で生成し、指定尺を超える末尾は除去します。",
              wraplength=560).pack(anchor="w", pady=(4, 8))
    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True)
    scroll = ttk.Scrollbar(body, orient="vertical")
    scroll.pack(side="right", fill="y")
    entries = tk.Listbox(body, exportselection=False, yscrollcommand=scroll.set,
                         font=("Meiryo UI", 10))
    entries.pack(side="left", fill="both", expand=True)
    scroll.configure(command=entries.yview)
    editor = ttk.Frame(outer)
    editor.pack(fill="x", pady=(8, 4))
    ttk.Label(editor, text="選択カットの秒数").pack(side="left")
    duration = tk.StringVar()
    value = ttk.Entry(editor, textvariable=duration, width=10)
    value.pack(side="left", padx=6)
    active = 0
    updating = False

    def refresh(index):
        nonlocal active, updating
        updating = True
        try:
            active = min(max(index, 0), len(cuts) - 1)
            entries.delete(0, "end")
            start = 0
            for i, count in enumerate(cuts):
                end = start + count
                generated = max(107, 5 + 17 * ((count + int(i > 0) - 5 + 16) // 17))
                entries.insert("end", f"{i + 1:02d}   {start/FPS:7.2f}–{end/FPS:7.2f}s"
                               f"   {format_cut_seconds(count)}秒   (生成 {generated}f)")
                start = end
            entries.selection_set(active)
            entries.see(active)
            duration.set(format_cut_seconds(cuts[active]))
            summary.configure(text=f"{len(cuts)}カット / 合計 {format_cut_seconds(sum(cuts))}秒")
        finally:
            updating = False

    def apply(index=None):
        try:
            cuts[active] = parse_cut_seconds(duration.get())
        except OrchestratorError as exc:
            messagebox.showerror("カット尺設定", str(exc), parent=dialog)
            return False
        refresh(active if index is None else index)
        return True

    def selected(_event=None):
        if updating:
            return
        selected_items = entries.curselection()
        if selected_items and selected_items[0] != active:
            if not apply(selected_items[0]):
                entries.selection_clear(0, "end")
                entries.selection_set(active)

    def add():
        if not apply():
            return
        if len(cuts) >= 300:
            messagebox.showerror("カット尺設定", "最大300カットです", parent=dialog)
            return
        cuts.insert(active + 1, 5 * FPS)
        refresh(active + 1)

    def delete():
        if len(cuts) <= 2:
            messagebox.showerror("カット尺設定", "2カット以上必要です", parent=dialog)
            return
        cuts.pop(active)
        refresh(active)

    def accept():
        nonlocal result
        if not apply():
            return
        try:
            result = validate_cut_frames(cuts)
        except OrchestratorError as exc:
            messagebox.showerror("カット尺設定", str(exc), parent=dialog)
            return
        dialog.destroy()

    value.bind("<Return>", lambda _event: apply())
    entries.bind("<<ListboxSelect>>", selected)
    ttk.Button(editor, text="適用", command=apply).pack(side="left")
    ttk.Button(editor, text="追加", command=add).pack(side="right")
    ttk.Button(editor, text="削除", command=delete).pack(side="right", padx=4)
    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(8, 0))
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="尺を確定", command=accept).pack(side="right", padx=(0, 8))
    refresh(0)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def edit_prompt_plan(parent, plan, frames, seconds, *, cut_frames=None, preview_only=False):
    """Return a validated edited copy, or None on cancel. Tk main thread only."""
    windows = segment_windows(frames, seconds, cut_frames=cut_frames)
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
    ttk.Label(outer, text=f"共通プロンプト ＋ {len(windows)}区間 / {format_cut_seconds(sum(w['output_frames'] for w in windows))}秒",
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
    entries = tk.Listbox(left, width=35, exportselection=False, yscrollcommand=scroll.set,
                         font=("Meiryo UI", 10))
    entries.pack(side="left", fill="y", expand=True)
    scroll.configure(command=entries.yview)
    for window in windows:
        entries.insert("end", f'{window["index"]:02d}  '
                       f'{window["start_frame"]/FPS:6.2f}–{window["end_frame"]/FPS:6.2f}s  '
                       f'({format_cut_seconds(window["output_frames"])}秒)')
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
                        f" · {format_cut_seconds(window['output_frames'])}秒"
                        f" / {window['generation_frames']}フレーム生成")
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

    def change_lengths():
        nonlocal result
        original = [w["output_frames"] for w in windows]
        try:
            editable = validate_cut_frames(original)
        except OrchestratorError:
            editable = default_cut_frames(int(seconds), max(frames))
        changed = edit_cut_durations(dialog, editable)
        dialog.grab_set()
        if changed is None or changed == original:
            return
        if not messagebox.askyesno("カット尺変更",
                                   "元の自然文から新しいカット尺で再分割します。"
                                   "\n編集中の区間プロンプトは置き換えられます。続けますか？",
                                   parent=dialog):
            return
        result = CutDurationChange(changed)
        dialog.destroy()

    entries.bind("<<ListboxSelect>>", select)
    entries.selection_set(0)
    select()
    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="尺変更・再分割", command=change_lengths).pack(side="left")
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="計画を保持" if preview_only else "確定して生成",
               command=accept).pack(side="right", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result
