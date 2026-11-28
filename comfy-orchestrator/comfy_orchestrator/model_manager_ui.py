"""Independent model registration dialog; no model loading or graph editing."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .model_registry import PROFILES, safe_filename, registration
from .parameters import OrchestratorError


class ModelManagerWindow(tk.Toplevel):
    def __init__(self, parent, values, inventory, *, on_save, on_refresh):
        super().__init__(parent)
        self.title("生成モデル管理 | Asobiba")
        self.geometry("920x560")
        self.minsize(690, 440)
        self.values = tuple(values)
        self.inventory = inventory
        self.on_save, self.on_refresh = on_save, on_refresh
        self.labels = {spec.label: key for key, spec in PROFILES.items()}
        self.profile = tk.StringVar(master=self, value=next(iter(self.labels)))
        self.filename = tk.StringVar(master=self)
        self.steps = tk.StringVar(master=self)
        self.cfg = tk.StringVar(master=self)
        self.status = tk.StringVar(master=self)

        body = ttk.Frame(self, padding=10)
        body.pack(fill="both", expand=True)
        footer = ttk.Frame(body)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, textvariable=self.status).pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="閉じる", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="登録解除", command=self._remove).pack(side="right", padx=6)
        ttk.Button(footer, text="モデル再検出", command=self._refresh).pack(side="right", padx=6)

        form = ttk.LabelFrame(body, text="登録・変更", padding=8)
        form.pack(side="bottom", fill="x", pady=(8, 8))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="互換系列").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        box = ttk.Combobox(form, textvariable=self.profile, values=tuple(self.labels), state="readonly")
        box.grid(row=0, column=1, columnspan=3, sticky="ew", pady=3)
        box.bind("<<ComboboxSelected>>", self._change_profile)
        ttk.Label(form, text="モデルファイル").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.files = ttk.Combobox(form, textvariable=self.filename, state="readonly")
        self.files.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)
        self.files.bind("<<ComboboxSelected>>", self._sync_file_choice)
        ttk.Label(form, text="既定Steps").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        self.steps_entry = ttk.Entry(form, textvariable=self.steps, width=9)
        self.steps_entry.grid(row=2, column=1, sticky="w", pady=3)
        ttk.Label(form, text="既定CFG").grid(row=2, column=2, sticky="w", padx=(8, 6), pady=3)
        self.cfg_entry = ttk.Entry(form, textvariable=self.cfg, width=9)
        self.cfg_entry.grid(row=2, column=3, sticky="w", pady=3)
        ttk.Label(form, text="空欄は系列既定。系列・入力方式は配布元の仕様を確認して指定。",
                  wraplength=650).grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.save_button = ttk.Button(form, text="登録・更新", command=self._register)
        self.save_button.grid(row=3, column=3, sticky="e", pady=(4, 0))

        top = ttk.Frame(body)
        top.pack(fill="both", expand=True)
        columns = ("file", "profile", "steps", "cfg", "status")
        self.rows = ttk.Treeview(top, columns=columns, show="headings", selectmode="browse")
        for key, title, width in (("file", "ファイル", 310), ("profile", "系列", 240),
                                  ("steps", "Steps", 65), ("cfg", "CFG", 60),
                                  ("status", "検出", 75)):
            self.rows.heading(key, text=title)
            self.rows.column(key, width=width, minwidth=45, stretch=key in ("file", "profile"))
        bar = ttk.Scrollbar(top, orient="vertical", command=self.rows.yview)
        self.rows.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.rows.pack(fill="both", expand=True)
        self.rows.bind("<<TreeviewSelect>>", self._select)
        self.update_inventory(inventory)

    def _profile_key(self):
        return self.labels.get(self.profile.get())

    def _change_profile(self, _event=None):
        key = self._profile_key()
        spec = PROFILES[key]
        options = tuple(dict.fromkeys(name for name in (self.inventory or {}).get(spec.loader, ())
                                       if safe_filename(name)))
        current = self.filename.get()
        self.files.configure(values=options, state="readonly" if options else "disabled")
        if current not in options:
            self.filename.set("")
        self.steps_entry.configure(state="normal")
        self.cfg_entry.configure(state="normal")
        if _event is not None:
            self.steps.set("")
            self.cfg.set("")
        if spec.fixed_steps is not None:
            self.steps.set(str(spec.fixed_steps))
            self.steps_entry.configure(state="readonly")
        if spec.fixed_cfg is not None:
            self.cfg.set(str(spec.fixed_cfg))
            self.cfg_entry.configure(state="readonly")
        elif not spec.image_family:
            self.cfg.set("")
            self.cfg_entry.configure(state="disabled")
        self._sync_file_choice()

    def _sync_file_choice(self, _event=None):
        spec = PROFILES[self._profile_key()]
        available = (self.inventory or {}).get(spec.loader, ())
        self.save_button.configure(state="normal" if self.filename.get() in available
                                   and safe_filename(self.filename.get()) else "disabled")

    def update_inventory(self, inventory):
        self.inventory = inventory
        self._rebuild()
        self._change_profile()
        if inventory is None:
            self.status.set("ComfyUI未確認。再検出してください。")
        else:
            count = sum(len(inventory.get(loader, ())) for loader in ("UNETLoader", "CheckpointLoaderSimple"))
            self.status.set(f"検出ファイル {count}件 / 手動登録 {len(self.values)}件")

    def _rebuild(self):
        for row in self.rows.get_children():
            self.rows.delete(row)
        for i, item in enumerate(self.values):
            status = "未確認" if self.inventory is None else (
                "あり" if item.filename in self.inventory.get(item.spec.loader, ()) else "なし")
            steps = item.steps if item.steps is not None else item.spec.fixed_steps
            cfg = item.cfg if item.cfg is not None else item.spec.fixed_cfg
            self.rows.insert("", "end", iid=str(i), values=(
                item.filename, item.spec.label, steps if steps is not None else "既定",
                cfg if cfg is not None else ("既定" if item.spec.image_family else "—"), status))

    def _selected(self):
        rows = self.rows.selection()
        return self.values[int(rows[0])] if rows else None

    def _select(self, _event=None):
        item = self._selected()
        if item is None:
            return
        self.profile.set(item.spec.label)
        self.filename.set(item.filename)
        self.steps.set("" if item.steps is None else str(item.steps))
        self.cfg.set("" if item.cfg is None else str(item.cfg))
        self._change_profile()
        # A missing registration can be removed, never accidentally replaced
        # with a different installed file by the profile's default selection.
        self.filename.set(item.filename)
        self._sync_file_choice()

    def _refresh(self):
        self.update_inventory(None)
        self.status.set("モデル一覧を取得中")
        self.on_refresh()

    def _register(self):
        try:
            key = self._profile_key()
            item = registration(key, self.filename.get(),
                                int(self.steps.get()) if self.steps.get().strip() else None,
                                float(self.cfg.get()) if self.cfg.get().strip() else None)
            if item.filename not in (self.inventory or {}).get(item.spec.loader, ()):
                raise OrchestratorError("ComfyUIで検出されたファイルを選択してください")
            existing = next((old for old in self.values if old.identity == item.identity), None)
            if existing is not None and existing.profile != item.profile:
                if not messagebox.askyesno("登録変更", "このファイルの登録系列を変更しますか？",
                                           parent=self):
                    return
            values = tuple(old for old in self.values if old.identity != item.identity) + (item,)
            if self.on_save(values):
                self.values = values
                self.update_inventory(self.inventory)
        except (ValueError, OSError, OrchestratorError) as exc:
            messagebox.showerror("モデル登録", str(exc), parent=self)

    def _remove(self):
        item = self._selected()
        if item is None:
            return
        if not messagebox.askyesno("登録解除", "登録だけを解除します。モデルファイルや生成履歴は削除しません。",
                                   parent=self):
            return
        values = tuple(old for old in self.values if old.identity != item.identity)
        if self.on_save(values):
            self.values = values
            self.update_inventory(self.inventory)
