"""Independent model-comparison workspace; all generation uses the shared worker."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .comparison import ComparisonWindow, Image, ImageOps, ImageTk
from .model_comparison import POLICIES, MAX_MODELS
from .parameters import OrchestratorError
from .prompt_viewer import show_image_prompt_formats
from . import camera_spec
from .camera_ui import choose_camera

STATUS = {"pending": "未生成", "running": "生成中", "completed": "完了",
          "interrupted": "中断", "error": "停止・未確認", "preparing": "準備中",
          "generating": "生成中"}


class ModelComparisonWindow(tk.Toplevel):
    def __init__(self, parent, store, choices, *, width, height, seed, steps, cfg,
                 on_start, on_cancel, on_adjust, on_open, on_close, camera=None):
        super().__init__(parent)
        self.title("画像モデル比較 | Asobiba")
        self.geometry("1200x850")
        self.minsize(780, 580)
        self.store = store
        self.camera = camera_spec.normalize(camera)
        self.on_start, self.on_cancel = on_start, on_cancel
        self.on_adjust, self.on_open, self.on_close = on_adjust, on_open, on_close
        self.choices = ()
        self.busy = False
        self.own_task = False
        self.manifest = None
        self.photos = {}
        self._render_key = None
        self._result_widgets = []
        self.width_var = tk.StringVar(master=self, value=str(width))
        self.height_var = tk.StringVar(master=self, value=str(height))
        self.seed_var = tk.StringVar(master=self, value=str(seed))
        self.steps_var = tk.StringVar(master=self, value=str(steps))
        self.cfg_var = tk.StringVar(master=self, value=str(cfg))
        self.policy = tk.StringVar(master=self, value=POLICIES["recommended"])
        self.group_label = tk.StringVar(master=self)
        self.status = tk.StringVar(master=self, value="比較対象を2～4件選択")
        self.summary = tk.StringVar(master=self)
        self.groups = {}
        self.protocol("WM_DELETE_WINDOW", self._close)

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="比較履歴").pack(side="left")
        self.group_box = ttk.Combobox(bar, textvariable=self.group_label,
                                      state="readonly", width=50)
        self.group_box.pack(side="left", fill="x", expand=True, padx=6)
        self.group_box.bind("<<ComboboxSelected>>", self._load_selected)
        self.reload_button = ttk.Button(bar, text="履歴更新", command=self._refresh_current)
        self.reload_button.pack(side="left")
        self.close_button = ttk.Button(bar, text="閉じる", command=self._close)
        self.close_button.pack(side="right", padx=(6, 0))

        split = ttk.Panedwindow(outer, orient="horizontal")
        split.pack(fill="both", expand=True)
        controls = ttk.Frame(split, padding=(0, 0, 6, 0))
        results = ttk.Frame(split)
        split.add(controls, weight=1)
        split.add(results, weight=4)

        ttk.Label(controls, text="比較モデル (2～4件)").pack(anchor="w")
        holder = ttk.Frame(controls)
        holder.pack(fill="both", expand=True, pady=(4, 6))
        scroll = ttk.Scrollbar(holder, orient="vertical")
        self.models = tk.Listbox(holder, selectmode="multiple", exportselection=False,
                                 yscrollcommand=scroll.set, height=9, width=27)
        scroll.configure(command=self.models.yview)
        scroll.pack(side="right", fill="y")
        self.models.pack(side="left", fill="both", expand=True)
        form = ttk.LabelFrame(controls, text="比較条件", padding=7)
        form.pack(fill="x")
        self.entries = {}
        for row, (key, label, variable) in enumerate((
            ("width", "幅", self.width_var), ("height", "高さ", self.height_var),
            ("seed", "Seed", self.seed_var), ("steps", "Steps", self.steps_var),
            ("cfg", "CFG", self.cfg_var),
        )):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            widget = ttk.Entry(form, textvariable=variable, width=12)
            widget.grid(row=row, column=1, sticky="ew", padx=(6, 0), pady=3)
            self.entries[key] = widget
        form.columnconfigure(1, weight=1)
        self.policy_box = ttk.Combobox(form, textvariable=self.policy, state="readonly",
                                       values=tuple(POLICIES.values()))
        self.policy_box.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.policy_box.bind("<<ComboboxSelected>>", self._sync_state)
        self.camera_button = ttk.Button(form, text="画角…", command=self._edit_camera)
        self.camera_button.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5,0))
        ttk.Label(controls, text="メイン画面の自然文・キャラ特徴・構図参考を使用。\nSeed空欄は共通乱数。", wraplength=250,
                  justify="left").pack(anchor="w", pady=7)
        self.start_button = ttk.Button(controls, text="比較生成", command=self._start)
        self.start_button.pack(fill="x")
        self.cancel_button = ttk.Button(controls, text="中止", command=on_cancel, state="disabled")
        self.cancel_button.pack(fill="x", pady=(5, 0))
        ttk.Label(results, textvariable=self.summary, wraplength=780, justify="left").pack(fill="x", pady=(0, 6))
        self.result_frame = ttk.Frame(results)
        self.result_frame.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, wraplength=1060, justify="left").pack(fill="x", pady=(8, 0))

        self.set_choices(choices)
        self.refresh_groups()
        self.set_busy(False)

    def set_choices(self, choices):
        selected = {(self.choices[i].workflow_id, self.choices[i].filename)
                    for i in self.models.curselection() if i < len(self.choices)}
        choices = tuple(choices)
        if choices == self.choices:
            return
        self.choices = choices
        self.models.configure(state="normal")
        self.models.delete(0, "end")
        for i, choice in enumerate(self.choices):
            self.models.insert("end", choice.label)
            if (choice.workflow_id, choice.filename) in selected:
                self.models.selection_set(i)
        self._sync_state()

    def _sync_state(self, _event=None):
        state = "disabled" if self.busy else "normal"
        self.models.configure(state=state)
        self.start_button.configure(state=state if len(self.choices) >= 2 else "disabled")
        self.close_button.configure(state="disabled" if self.own_task else "normal")
        self.cancel_button.configure(state="normal" if self.busy and self.own_task else "disabled")
        self.group_box.configure(state="disabled" if self.busy else "readonly")
        self.reload_button.configure(state=state)
        self.policy_box.configure(state="disabled" if self.busy else "readonly")
        self.camera_button.configure(state=state, text="画角設定済…" if self.camera else "画角…")
        for key, widget in self.entries.items():
            enabled = not self.busy and (key not in ("steps", "cfg") or self.policy.get() == POLICIES["common"])
            widget.configure(state="normal" if enabled else "disabled")
        for button, available in self._result_widgets:
            button.configure(state="normal" if available and not self.busy else "disabled")

    def set_busy(self, busy, *, own_task=False):
        self.busy, self.own_task = busy, own_task
        self._sync_state()

    def _edit_camera(self):
        if not self.busy:
            result = choose_camera(self, self.camera, self.width_var.get(), self.height_var.get())
            if result is not None:
                self.camera = result
                self._sync_state()

    def _start(self):
        if self.busy:
            return
        try:
            chosen = tuple(self.choices[i] for i in self.models.curselection())
            if not 2 <= len(chosen) <= MAX_MODELS:
                raise OrchestratorError("比較モデルは2～4件選択してください")
            policy = next(k for k, label in POLICIES.items() if label == self.policy.get())
            common = policy == "common"
            self.on_start(chosen, width=int(self.width_var.get()), height=int(self.height_var.get()),
                          seed=int(self.seed_var.get()) if self.seed_var.get().strip() else None,
                          policy=policy, steps=int(self.steps_var.get()) if common else None,
                          cfg=float(self.cfg_var.get()) if common else None, camera=dict(self.camera))
        except (ValueError, OSError, OrchestratorError) as exc:
            messagebox.showwarning("比較生成", str(exc), parent=self)

    def refresh_groups(self):
        manifests = self.store.recent()
        self.groups = {}
        current = self.manifest["id"] if self.manifest else None
        selected = ""
        for manifest in manifests:
            label = f"{manifest.get('created_at', '')[:16].replace('T', ' ')} · {str(manifest.get('request', '')).replace(chr(10), ' ')[:54]} [{manifest['id'][:8]}]"
            self.groups[label] = manifest["id"]
            if current == manifest["id"]:
                selected = label
        self.group_box.configure(values=tuple(self.groups))
        self.group_label.set(selected)

    def _load_selected(self, _event=None):
        group_id = self.groups.get(self.group_label.get())
        if group_id and not self.busy:
            self.open_group(group_id)

    def _refresh_current(self):
        self.refresh_groups()
        if self.manifest is not None and not self.busy:
            self.open_group(self.manifest["id"])

    def open_group(self, group_id):
        try:
            self.show_manifest(self.store.resolved(self.store.read(group_id)), active=False)
            self.refresh_groups()
        except (OSError, ValueError, OrchestratorError) as exc:
            messagebox.showwarning("比較履歴", str(exc), parent=self)

    def _thumbnail(self, path, max_size):
        try:
            if Image is not None:
                with Image.open(path) as opened:
                    if opened.width * opened.height > 80_000_000:
                        raise ValueError("image too large")
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                    image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    return ImageTk.PhotoImage(image, master=self)
            photo = tk.PhotoImage(master=self, file=str(path))
            scale = max(1, (photo.width() + max_size[0] - 1) // max_size[0],
                        (photo.height() + max_size[1] - 1) // max_size[1])
            return photo.subsample(scale, scale)
        except (OSError, ValueError, tk.TclError):
            return None

    def show_manifest(self, manifest, *, active):
        self.manifest = manifest
        targets = manifest["targets"]
        count = sum(t.get("status") == "completed" for t in targets)
        status = manifest.get("status", "pending")
        if not active and status in ("preparing", "generating"):
            status_text = "前回中断・状態未確認"
        else:
            status_text = STATUS.get(status, status)
        self.status.set(f"{status_text}  {count}/{len(targets)}件  {manifest.get('message', '')}")
        params = targets[0]["overrides"]
        request = str(manifest.get("request", "")).replace("\n", " ")
        self.summary.set(f"{params.get('width')}×{params.get('height')} · Seed {params.get('seed')} · "
                         f"{POLICIES.get(manifest.get('policy'), '')}\n"
                         + ("画角: " + camera_spec.summary(params[camera_spec.KEY]) + "\n" if params.get(camera_spec.KEY) else "")
                         + request[:160])
        paths = [self.store.images_for(t) for t in targets]
        key = (manifest["id"], tuple((t.get("status"), tuple(p), t.get("history_id"),
               bool(t.get("parameters")), t.get("elapsed_seconds")) for t, p in zip(targets, paths)))
        if key == self._render_key:
            return
        self._render_key = key
        for widget in self.result_frame.winfo_children():
            widget.destroy()
        self._result_widgets = []
        previous_photos = self.photos
        self.photos = {}
        max_size = (410, 490 if len(targets) == 2 else 235)
        for col in (0, 1):
            self.result_frame.columnconfigure(col, weight=1, uniform="models")
        for row in range(2):
            self.result_frame.rowconfigure(row, weight=int(row == 0 or len(targets) > 2), uniform="models")
        complete = [(i, p[0]) for i, p in enumerate(paths) if p]
        for i, (target, outputs) in enumerate(zip(targets, paths)):
            card = ttk.LabelFrame(self.result_frame, text=target["label"], padding=5)
            card.grid(row=i//2, column=i%2, padx=3, pady=3, sticky="nsew")
            params = target.get("parameters") or target["overrides"]
            footer = ttk.Frame(card)
            footer.pack(side="bottom", fill="x")
            state = STATUS.get(target.get("status"), target.get("status", ""))
            elapsed = target.get("elapsed_seconds")
            duration = f" · {elapsed:.1f}s" if isinstance(elapsed, (int, float)) else ""
            ttk.Label(footer, text=f"{state} · {params.get('steps', '?')} Steps / CFG {params.get('cfg', '?')}{duration}").pack(anchor="w")
            buttons = ttk.Frame(footer)
            buttons.pack(fill="x")
            path = outputs[0] if outputs else None
            photo_key = (path, max_size)
            photo = previous_photos.get(photo_key) if path else None
            if path and photo is None:
                photo = self._thumbnail(path, max_size)
            self.photos[photo_key] = photo
            ttk.Label(card, image=photo if photo else "", text="" if photo else
                      ("プレビュー非対応" if path else state), anchor="center").pack(fill="both", expand=True)
            prompt = ttk.Button(buttons, text="プロンプト", command=lambda t=target: show_image_prompt_formats(
                self, t["parameters"], t["workflow_id"]))
            prompt.pack(side="left", padx=(0, 4))
            self._result_widgets.append((prompt, bool(target.get("parameters"))))
            if path:
                button = ttk.Button(buttons, text="開く", command=lambda p=path: self.on_open(p))
                button.pack(side="left", padx=(0, 4))
                self._result_widgets.append((button, True))
                other = next(((j, p) for j, p in complete if j != i), None)
                if other is not None:
                    j, other_path = other
                    button = ttk.Button(buttons, text="拡大比較", command=lambda p=path, q=other_path,
                        a=target["label"], b=targets[j]["label"]: self._compare(p, q, a, b))
                    button.pack(side="left", padx=(0, 4))
                    self._result_widgets.append((button, True))
                if target.get("history_id"):
                    button = ttk.Button(buttons, text="調整", command=lambda h=target["history_id"], p=path: self.on_adjust(h, p))
                    button.pack(side="right")
                    self._result_widgets.append((button, True))
        self._sync_state()

    def _compare(self, left, right, a, b):
        try:
            ComparisonWindow(self, left, right, a, b)
        except (ValueError, OSError, tk.TclError) as exc:
            messagebox.showwarning("画像比較", str(exc), parent=self)

    def _close(self):
        if not self.own_task:
            self.on_close()
