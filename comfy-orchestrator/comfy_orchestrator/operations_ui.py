"""Compact read-only local operations panel; scan results arrive from a worker."""
from __future__ import annotations

import os
from tkinter import ttk, Toplevel, messagebox, StringVar
from pathlib import Path

from .storage_report import format_bytes


class OperationsWindow:
    def __init__(self, parent, root, *, on_refresh, on_clear_cache):
        self.root = Path(root)
        self.window = Toplevel(parent)
        self.window.title("運用情報")
        self.window.geometry("700x470")
        self.window.minsize(560, 410)
        self.window.transient(parent)
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        self.summary = StringVar(value="保存データを計測中…")
        ttk.Label(outer, textvariable=self.summary, wraplength=640).pack(fill="x", pady=(0, 6))
        controls = ttk.Frame(outer)
        controls.pack(side="bottom", fill="x", pady=(8, 0))
        for label, path in (("出力", self.root / "outputs"), ("長尺", self.root / "data" / "long_videos"),
                            ("履歴データ", self.root / "data")):
            ttk.Button(controls, text=label + "を開く", command=lambda p=path: self._open(p)).pack(side="left", padx=(0, 4))
        ttk.Button(controls, text="更新", command=on_refresh).pack(side="right")
        ttk.Button(controls, text="解釈キャッシュ削除", command=on_clear_cache).pack(side="right", padx=4)
        self.stats = StringVar(value="")
        ttk.Label(outer, textvariable=self.stats, wraplength=650, justify="left").pack(side="bottom", fill="x", pady=(8, 0))
        self.table = ttk.Treeview(outer, columns=("files", "logical", "unique"), show="tree headings", height=6)
        self.table.heading("#0", text="保存区分")
        self.table.column("#0", width=155)
        for key, label, width in (("files", "ファイル数", 85), ("logical", "論理容量", 115), ("unique", "区分内重複除外", 135)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, anchor="e")
        self.table.pack(fill="both", expand=True)

    def is_open(self):
        return bool(self.window.winfo_exists())

    def _open(self, path):
        try:
            if os.name != "nt" or not path.is_dir():
                raise OSError("保存先が見つかりません")
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror("保存先", str(exc), parent=self.window)

    def update(self, report, cache, models):
        self.table.delete(*self.table.get_children())
        for row in report["rows"]:
            self.table.insert("", "end", text=row["name"],
                              values=(row["files"], format_bytes(row["logical_bytes"]),
                                      format_bytes(row["unique_bytes"])))
        self.summary.set("保存データ（重複除外） " + format_bytes(report["unique_bytes"])
                         + " / 論理容量 " + format_bytes(report["logical_bytes"])
                         + "\nハードリンクによる重複除外 " + format_bytes(report["shared_bytes"])
                         + " / ドライブ空き " + format_bytes(report["disk_free_bytes"]))
        if cache is None:
            cache_text = "解釈キャッシュ: 計測不可"
        else:
            cache_text = (f"解釈キャッシュ {cache['entries']}/{cache['limit']}件"
                          f" · 今回の起動中 検索ヒット {cache['hits']} / ミス {cache['misses']}"
                          f" / 保存 {cache['writes']}")
        self.stats.set(cache_text + "\n"
                       f"LM Studio 新規ロード {models['llm_loads']} / 既存インスタンス使用 {models['llm_reuses']}"
                       f" / 解放確認 {models['llm_unloads']}\n"
                       f"ComfyUI 解放要求成功 {models['comfy_release_requests']} / 明示解放を省略 {models['comfy_preserve_jobs']}\n"
                       "起動中の回数。ComfyUI内部のGPUキャッシュ命中率ではありません。\n"
                       "容量はファイルサイズの概算です。生成データは自動削除しません。")
