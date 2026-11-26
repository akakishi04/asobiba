"""Persistent long-video project picker and cut editor (Tk main thread only)."""
from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, messagebox, scrolledtext

from .long_video import project_cut_lengths, first_changed_cut
from .parameters import OrchestratorError
from .timeline import FPS, format_cut_seconds, parse_cut_seconds, validate_cut_frames, validate_prompt_plan


@dataclass(frozen=True)
class ProjectAction:
    action: str
    prompt_plan: dict
    cut_frames: list[int]
    regenerate_from: int | None = None


def choose_project(parent, projects, preferred=None):
    if not projects:
        messagebox.showinfo("長尺プロジェクト", "保存済みの長尺プロジェクトはありません", parent=parent)
        return None
    dialog = tk.Toplevel(parent)
    dialog.title("長尺プロジェクト")
    dialog.transient(parent)
    dialog.geometry("720x420")
    outer = ttk.Frame(dialog, padding=10)
    outer.pack(fill="both", expand=True)
    tree = ttk.Treeview(outer, columns=("progress", "seconds", "state"), show="tree headings", selectmode="browse")
    tree.heading("#0", text="プロジェクト / 自然文")
    tree.heading("progress", text="生成済み")
    tree.heading("seconds", text="秒")
    tree.heading("state", text="状態")
    tree.column("#0", width=360)
    tree.column("progress", width=85, anchor="center")
    tree.column("seconds", width=70, anchor="center")
    tree.column("state", width=110)
    scroll = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    states = {"draft": "計画保存", "generating": "途中", "ready_to_join": "結合待ち", "completed": "完成"}
    by_id = {p["run_id"]: p for p in projects}
    for p in projects:
        title = " ".join(p["request"].split())[:55] or "参照画像のみ"
        if p.get("revision"):
            title = f"改訂{p['revision']} · {title}"
        tree.insert("", "end", iid=p["run_id"], text=title,
                    values=(f"{len(p['segments'])}/{len(p['plan'])}", f"{p['seconds']:.2f}",
                            states.get(p["state"], p["state"])))
    selected = preferred if preferred in by_id else projects[0]["run_id"]
    tree.selection_set(selected)
    tree.see(selected)
    result = None
    def accept(_event=None):
        nonlocal result
        if tree.selection():
            result = by_id[tree.selection()[0]]
            dialog.destroy()
    bar = ttk.Frame(outer)
    bar.pack(fill="x", pady=(8, 0))
    ttk.Button(bar, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(bar, text="開く", command=accept).pack(side="right", padx=6)
    tree.bind("<Double-1>", accept)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def edit_long_project(parent, store, manifest, *, preview_only=False):
    """Edit local text/durations and choose a saved-project operation."""
    original = manifest.get("prompt_plan")
    if original is None:
        raise OrchestratorError("計画のない旧形式は従来の再開のみ対応します")
    original_cuts = project_cut_lengths(manifest)
    cuts = list(original_cuts)
    parts = list(original["segments"])
    result = None
    dialog = tk.Toplevel(parent)
    dialog.title("連続動画 · プロジェクト")
    dialog.transient(parent)
    dialog.geometry(f"{min(960, parent.winfo_screenwidth() - 60)}x"
                    f"{min(710, parent.winfo_screenheight() - 100)}")
    dialog.minsize(570, 450)
    outer = ttk.Frame(dialog, padding=12)
    outer.pack(fill="both", expand=True)
    title = ttk.Label(outer, font=("Meiryo UI", 11, "bold"))
    title.pack(anchor="w")
    ttk.Label(outer, text="共通プロンプト").pack(anchor="w", pady=(6, 0))
    common = scrolledtext.ScrolledText(outer, height=3, wrap="word", undo=True, font=("Meiryo UI", 10))
    common.pack(fill="x")
    common.insert("1.0", original["common"])
    body = ttk.Frame(outer)
    body.pack(fill="both", expand=True, pady=(8, 0))
    left = ttk.Frame(body)
    left.pack(side="left", fill="y", padx=(0, 10))
    scroll = ttk.Scrollbar(left, orient="vertical")
    scroll.pack(side="right", fill="y")
    entries = tk.Listbox(left, width=35, exportselection=False, yscrollcommand=scroll.set,
                         font=("Meiryo UI", 10))
    entries.pack(side="left", fill="both", expand=True)
    scroll.configure(command=entries.yview)
    right = ttk.Frame(body)
    right.pack(side="left", fill="both", expand=True)
    label = ttk.Label(right)
    label.pack(anchor="w")
    timebar = ttk.Frame(right)
    timebar.pack(fill="x", pady=4)
    ttk.Label(timebar, text="秒数").pack(side="left")
    duration = tk.StringVar()
    value = ttk.Entry(timebar, width=10, textvariable=duration)
    value.pack(side="left", padx=4)
    segment = scrolledtext.ScrolledText(right, height=8, wrap="word", undo=True, font=("Meiryo UI", 10))
    segment.pack(fill="both", expand=True)
    controls = ttk.Frame(right)
    controls.pack(fill="x", pady=5)
    current = 0
    updating = False

    def current_plan():
        return {"common": common.get("1.0", "end-1c").strip(), "segments": list(parts)}

    def first_change():
        return first_changed_cut(manifest, current_plan(), cuts)

    def save_active():
        try:
            raw = duration.get().strip()
            # Preserve a pre-existing preset's sub-second tail unless changed.
            if raw != format_cut_seconds(cuts[current]):
                cuts[current] = parse_cut_seconds(raw)
            parts[current] = segment.get("1.0", "end-1c").strip()
            return True
        except OrchestratorError as exc:
            messagebox.showerror("カット設定", str(exc), parent=dialog)
            return False

    def refresh(index):
        nonlocal current, updating
        updating = True
        try:
            current = max(0, min(index, len(parts) - 1))
            entries.delete(0, "end")
            changed = first_change()
            start = 0
            for i, count in enumerate(cuts):
                status = "未生成"
                if i < len(manifest["segments"]):
                    status = "生成済" if changed is None or i < changed else "要再生成"
                    if status == "生成済" and not store.asset(manifest, manifest["segments"][i]["file"]).is_file():
                        status = "ファイルなし"
                entries.insert("end", f"{i+1:02d}  {start/FPS:6.2f}–{(start+count)/FPS:6.2f}s  {status}")
                start += count
            entries.selection_set(current)
            entries.see(current)
            label.configure(text=f"カット {current+1} / {len(parts)}")
            duration.set(format_cut_seconds(cuts[current]))
            segment.delete("1.0", "end")
            segment.insert("1.0", parts[current])
            segment.edit_reset()
            valid_prefix = min(len(manifest["segments"]), changed if changed is not None else len(parts))
            title.configure(text=f"{len(parts)}カット / {format_cut_seconds(sum(cuts))}秒 / 有効生成 {valid_prefix}件")
            preview.configure(state="normal" if current < len(manifest["segments"]) else "disabled")
            join.configure(state="normal" if valid_prefix == len(parts) else "disabled")
        finally:
            updating = False

    def select(_event=None):
        if updating:
            return
        selection = entries.curselection()
        if selection and selection[0] != current:
            if save_active():
                refresh(selection[0])
            else:
                entries.selection_clear(0, "end")
                entries.selection_set(current)

    def apply(_event=None):
        if save_active():
            refresh(current)

    def add():
        if save_active() and len(parts) < 300:
            cuts.insert(current + 1, 5 * FPS)
            parts.insert(current + 1, "")
            refresh(current + 1)

    def delete():
        if len(parts) <= 2:
            messagebox.showinfo("カット削除", "2カット以上必要です", parent=dialog)
            return
        if save_active():
            cuts.pop(current)
            parts.pop(current)
            refresh(current)

    def open_clip():
        try:
            path = store.asset(manifest, manifest["segments"][current]["file"])
            if not path.is_file():
                raise OSError("生成動画が見つかりません")
            if os.name != "nt":
                raise OSError("動画を開く機能はWindows専用です")
            os.startfile(str(path))
        except (OSError, IndexError, OrchestratorError) as exc:
            messagebox.showerror("動画確認", str(exc), parent=dialog)

    def accept(action, regenerate=False):
        nonlocal result
        if not save_active():
            return
        try:
            approved = validate_prompt_plan(current_plan(), len(cuts))
            if cuts != original_cuts:
                validate_cut_frames(cuts)
            changed = first_changed_cut(manifest, approved, cuts)
            start = current if regenerate else None
            affected = start if changed is None else changed if start is None else min(start, changed)
            if action == "join" and (affected is not None or len(manifest["segments"]) != len(parts)):
                raise OrchestratorError("変更のない全生成済みカットだけを結合できます")
            if affected is not None and affected < len(manifest["segments"]):
                if not messagebox.askyesno("改訂版を作成",
                    f"カット{affected + 1}以降を再生成対象にします。元のプロジェクトと動画は保持します。続けますか？",
                    parent=dialog):
                    return
            result = ProjectAction(action, approved, list(cuts), start)
        except OrchestratorError as exc:
            messagebox.showerror("長尺プロジェクト", str(exc), parent=dialog)
            return
        dialog.destroy()

    ttk.Button(timebar, text="反映", command=apply).pack(side="left")
    value.bind("<Return>", apply)
    entries.bind("<<ListboxSelect>>", select)
    ttk.Button(controls, text="カット追加", command=add).pack(side="left")
    ttk.Button(controls, text="削除", command=delete).pack(side="left", padx=4)
    preview = ttk.Button(controls, text="元の生成クリップを開く", command=open_clip)
    preview.pack(side="right")
    actions = ttk.Frame(outer)
    actions.pack(fill="x", pady=(8, 0))
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="計画保存", command=lambda: accept("save")).pack(side="left")
    ttk.Button(actions, text="選択以降再生成", command=lambda: accept("generate", True)).pack(side="left", padx=4)
    ttk.Button(actions, text="カット生成", command=lambda: accept("generate")).pack(side="left", padx=4)
    join = ttk.Button(actions, text="結合のみ", command=lambda: accept("join"))
    join.pack(side="left", padx=4)
    ttk.Button(actions, text="生成・結合", command=lambda: accept("generate_join")).pack(side="right", padx=4)
    ttk.Label(outer, text="生成クリップの確認はトリミング前の元動画です。変更したカット以降は改訂版で生成します。").pack(anchor="w", pady=(4, 0))
    refresh(0)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result
