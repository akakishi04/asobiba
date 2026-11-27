"""Compact read-only local operations panel; scan results arrive from a worker."""
from __future__ import annotations

import os
from tkinter import ttk, Toplevel, messagebox, StringVar
from pathlib import Path

from .storage_report import format_bytes
from .llm_usage import ACTIONS, MODES, format_count, format_summary


class OperationsWindow:
    def __init__(self, parent, root, *, on_refresh, on_clear_cache, on_export_usage):
        self.root = Path(root)
        self.window = Toplevel(parent)
        self.window.title("運用情報")
        self.window.geometry("700x470")
        self.window.minsize(560, 410)
        self.window.transient(parent)
        tabs = ttk.Notebook(self.window)
        tabs.pack(fill="both", expand=True, padx=8, pady=8)
        outer = ttk.Frame(tabs, padding=8)
        tabs.add(outer, text="保存・運用")
        usage = ttk.Frame(tabs, padding=8)
        tabs.add(usage, text="LLM使用量")
        self._build_usage(usage, on_refresh, on_export_usage)
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

    def _build_usage(self, outer, on_refresh, on_export_usage):
        self.usage_summary = StringVar(master=self.window, value="計測中…")
        self.usage_status = StringVar(master=self.window, value="")
        ttk.Label(outer, textvariable=self.usage_summary, wraplength=620).pack(fill="x", pady=(0, 6))
        controls = ttk.Frame(outer)
        controls.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(controls, text="CSV出力", command=on_export_usage).pack(side="left")
        ttk.Button(controls, text="更新", command=on_refresh).pack(side="right")
        ttk.Label(outer, textvariable=self.usage_status, wraplength=620).pack(side="bottom", fill="x")
        views = ttk.Notebook(outer)
        views.pack(fill="both", expand=True)

        def table(title, columns):
            pane = ttk.Frame(views)
            views.add(pane, text=title)
            tree = ttk.Treeview(pane, columns=tuple(key for key, _, _ in columns), show="tree headings")
            tree.heading("#0", text="操作" if title == "操作別" else "LLM / 用途")
            tree.column("#0", width=190, minwidth=120, stretch=True)
            for key, label, width in columns:
                tree.heading(key, text=label)
                tree.column(key, width=width, minwidth=48, anchor="e")
            scroll = ttk.Scrollbar(pane, orient="vertical", command=tree.yview)
            scroll.pack(side="right", fill="y")
            tree.configure(yscrollcommand=scroll.set)
            tree.pack(fill="both", expand=True)
            return tree

        self.usage_operations = table("操作別", (
            ("time", "日時", 105), ("frames", "フレーム", 80), ("calls", "回数", 48),
            ("input", "Input", 77), ("output", "Output", 77), ("missing", "未計測", 58),
        ))
        self.usage_purposes = table("モデル・用途別", (
            ("calls", "回数", 52), ("input", "Input", 85), ("output", "Output", 85),
            ("reasoning", "思考", 75), ("missing", "未計測", 60),
        ))

    def update_usage(self, report):
        if report is None:
            self.usage_summary.set("LLM使用量を取得できません")
            for tree in (self.usage_operations, self.usage_purposes):
                tree.delete(*tree.get_children())
            return
        total = report["total"]
        self.usage_summary.set(f"累計 {total['operations']:,}操作 · " + format_summary(total))
        self.usage_status.set("直近100操作。≥ は計測分の下限、— は取得不可。CSVには全リクエストを出力。")
        tree = self.usage_operations
        tree.delete(*tree.get_children())
        for row in report["operations"]:
            when = row["started_at"]
            try:
                from datetime import datetime
                when = datetime.fromisoformat(when).astimezone().strftime("%m/%d %H:%M:%S")
            except (ValueError, OverflowError):
                pass
            mode = MODES.get(row["mode"], row["mode"])
            label = ACTIONS.get(row["action"], row["action"])
            status = {"running": " (未完了)", "interrupted": " (中断)"}.get(row["operation_status"], "")
            if row["recording_errors"]:
                status += " (記録失敗)"
            duration = f"{row['frames']}f" if row["frames"] is not None else ""
            if row["cuts"] is not None:
                duration += f"/{row['cuts']}cut"
            tree.insert("", "end", text=f"{mode} {label}{status}".strip(), values=(
                when, duration, row["calls"], format_count(row, "input_tokens"),
                format_count(row, "output_tokens"), row["missing"],
            ))
        tree = self.usage_purposes
        tree.delete(*tree.get_children())
        models = {}
        for row in report["purposes"]:
            model = row["model"]
            parent = models.get(model)
            if parent is None:
                parent = tree.insert("", "end", text=model, open=True)
                models[model] = parent
            tree.insert(parent, "end", text=row["purpose"], values=(
                row["calls"], format_count(row, "input_tokens"), format_count(row, "output_tokens"),
                format_count(row, "reasoning_tokens"), row["missing"],
            ))

    def is_open(self):
        return bool(self.window.winfo_exists())

    def _open(self, path):
        try:
            if os.name != "nt" or not path.is_dir():
                raise OSError("保存先が見つかりません")
            os.startfile(str(path))
        except OSError as exc:
            messagebox.showerror("保存先", str(exc), parent=self.window)

    def update(self, report, cache, models, usage=None):
        self.update_usage(usage)
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
