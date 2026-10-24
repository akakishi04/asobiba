"""Windows desktop GUI for the fixed-workflow ComfyUI orchestrator.

Runs model inference in worker threads; Tk widgets are updated on the main thread.
No third-party GUI dependencies.
"""

from __future__ import annotations

import copy
import json
import os
import queue
import shutil
import threading
import urllib.parse
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import core
from .lmstudio import list_models


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
EXAMPLE = ROOT / "config.example.json"
OUTPUTS = ROOT / "outputs"


def bootstrap_config() -> dict:
    """Create the local settings file only if missing, preserving custom settings."""
    if not CONFIG.exists():
        shutil.copyfile(EXAMPLE, CONFIG)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if "llm" not in config:
        config["llm"] = copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8"))["llm"])
    config["llm"]["provider"] = "lmstudio"
    return config


def output_images(result: dict) -> list[dict]:
    images: list[dict] = []
    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict):
        return images
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for entry in node_output.get("images", []):
            if isinstance(entry, dict) and isinstance(entry.get("filename"), str):
                images.append({
                    "filename": entry["filename"],
                    "subfolder": str(entry.get("subfolder", "")),
                    "type": str(entry.get("type", "output")),
                })
    return images


def save_output_image(base_url: str, metadata: dict, prompt_id: str) -> Path:
    """Download only a bounded image into the ignored local output directory."""
    parameters = {
        "filename": metadata["filename"],
        "subfolder": metadata["subfolder"],
        "type": metadata["type"],
    }
    url = base_url.rstrip("/") + "/view?" + urllib.parse.urlencode(parameters)
    with urllib.request.urlopen(url, timeout=45) as response:
        payload = response.read(40 * 1024 * 1024 + 1)
    if not payload or len(payload) > 40 * 1024 * 1024:
        raise core.OrchestratorError("画像の取得に失敗しました（40MB超過または空ファイル）")
    safe_name = Path(metadata["filename"].replace("\\", "/")).name
    if not safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise core.OrchestratorError("未対応の出力画像形式です")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    destination = OUTPUTS / (prompt_id[:16] + "_" + safe_name)
    destination.write_bytes(payload)
    return destination


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Asobiba | Comfy Orchestrator")
        self.root.geometry("1150x815")
        self.root.minsize(860, 670)
        self.messages: queue.Queue = queue.Queue()
        self.working = False
        self.stop_event = threading.Event()
        self.image_paths: list[Path] = []
        self.preview_photo: tk.PhotoImage | None = None
        self.config = bootstrap_config()
        self._variables()
        self._build()
        self.root.after(100, self._consume_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _variables(self) -> None:
        llm = self.config["llm"]
        comfy = self.config["comfyui"]
        options = self.config.get("ui", {})
        self.llm_url = tk.StringVar(value=llm.get("base_url", "http://127.0.0.1:1234"))
        self.comfy_url = tk.StringVar(value=comfy.get("base_url", "http://127.0.0.1:8188"))
        self.model = tk.StringVar(value="" if llm.get("model") == "SELECT_IN_GUI" else llm.get("model", ""))
        workflows = list(self.config.get("workflows", {}))
        preferred = options.get("workflow", workflows[0] if workflows else "自動")
        self.workflow = tk.StringVar(value=preferred if preferred in workflows else "自動")
        self.width = tk.StringVar(value=str(options.get("width", 768)))
        self.height = tk.StringVar(value=str(options.get("height", 768)))
        self.steps = tk.StringVar(value=str(options.get("steps", 20)))
        self.cfg = tk.StringVar(value=str(options.get("cfg", 5.0)))
        self.seed = tk.StringVar(value=str(options.get("seed", "")))
        self.reference_image = tk.StringVar(value="")
        self.unload_llm = tk.BooleanVar(value=llm.get("unload_after_inference", True))
        self.free_comfy = tk.BooleanVar(value=comfy.get("free_before_llm", True))
        self.status = tk.StringVar(value="準備完了 — LM Studioのサーバーを起動してください")
        self.result_info = tk.StringVar(value="生成画像はここに表示されます")

    def _build(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Heading.TLabel", font=("Yu Gothic UI", 17, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Yu Gothic UI", 10, "bold"))
        style.configure("Run.TButton", padding=(14, 9))

        layout = ttk.Frame(self.root, padding=14)
        layout.pack(fill="both", expand=True)
        ttk.Label(layout, text="Comfy Orchestrator", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            layout,
            text="自然文 → LM Studioで解釈 → LLMアンロード → ComfyUI画像生成",
        ).pack(anchor="w", pady=(2, 12))

        connection = ttk.LabelFrame(layout, text="接続・モデル", padding=10, style="Section.TLabelframe")
        connection.pack(fill="x")
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(3, weight=1)
        ttk.Label(connection, text="LM Studio").grid(row=0, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=self.llm_url).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(connection, text="ComfyUI").grid(row=0, column=2, sticky="w", padx=(0, 7))
        ttk.Entry(connection, textvariable=self.comfy_url).grid(row=0, column=3, sticky="ew")
        ttk.Label(connection, text="解釈用モデル").grid(row=1, column=0, sticky="w", pady=(6, 3))
        self.model_box = ttk.Combobox(connection, textvariable=self.model, state="normal")
        self.model_box.grid(row=1, column=1, sticky="ew", pady=(6, 3), padx=(0, 12))
        ttk.Button(connection, text="モデルを更新", command=self._refresh_models).grid(
            row=1, column=2, sticky="ew", padx=(0, 7), pady=(6, 3)
        )
        ttk.Button(connection, text="接続確認", command=self._check_connections).grid(
            row=1, column=3, sticky="w", pady=(6, 3)
        )

        options_frame = ttk.Frame(connection)
        options_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            options_frame, text="解釈後にLM Studioの選択モデルをアンロード（推奨）",
            variable=self.unload_llm
        ).pack(side="left", padx=(0, 22))
        ttk.Checkbutton(
            options_frame, text="解釈前にComfyUIの空きモデルを解放",
            variable=self.free_comfy
        ).pack(side="left")
        ttk.Button(options_frame, text="設定を保存", command=self._save_settings).pack(side="right")

        main = ttk.Panedwindow(layout, orient="horizontal")
        main.pack(fill="both", expand=True, pady=(12, 8))

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=3)
        main.add(right, weight=2)

        prompt_panel = ttk.LabelFrame(left, text="自然文から生成", padding=10, style="Section.TLabelframe")
        prompt_panel.pack(fill="both", expand=True, padx=(0, 6))
        ttk.Label(
            prompt_panel,
            text="日本語で描写してください。プロンプトの整形はLLMが担当します。",
        ).pack(anchor="w", pady=(0, 5))
        self.prompt = scrolledtext.ScrolledText(prompt_panel, height=9, wrap="word", font=("Yu Gothic UI", 11))
        self.prompt.insert("1.0", "夕暮れの海辺に立つ銀髪の少女。アニメ調で、風になびく髪を自然に描いて。")
        self.prompt.pack(fill="both", expand=True, pady=(0, 10))

        settings = ttk.LabelFrame(prompt_panel, text="生成設定（初期値は軽量寄り）", padding=9)
        settings.pack(fill="x", pady=(0, 8))
        for i in range(6):
            settings.columnconfigure(i, weight=1 if i % 2 else 0)
        ttk.Label(settings, text="ワークフロー").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.workflow_box = ttk.Combobox(
            settings, textvariable=self.workflow,
            values=["自動", *self.config.get("workflows", {}).keys()], state="readonly",
        )
        self.workflow_box.grid(row=0, column=1, columnspan=5, sticky="ew", pady=4)
        ttk.Label(settings, text="幅").grid(row=1, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(settings, textvariable=self.width, width=7).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(settings, text="高さ").grid(row=1, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(settings, textvariable=self.height, width=7).grid(row=1, column=3, sticky="ew", padx=(0, 8))
        ttk.Label(settings, text="Steps").grid(row=1, column=4, sticky="w", padx=(0, 5))
        ttk.Entry(settings, textvariable=self.steps, width=7).grid(row=1, column=5, sticky="ew")
        ttk.Label(settings, text="CFG").grid(row=2, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.cfg, width=7).grid(row=2, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(settings, text="Seed").grid(row=2, column=2, sticky="w")
        ttk.Entry(settings, textvariable=self.seed).grid(row=2, column=3, columnspan=3, sticky="ew")
        ttk.Label(
            settings, text="Seed空欄＝毎回ランダム。元のAPIファイルは1024×1024 / 28 Stepsのまま保持。",
        ).grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0))

        image_row = ttk.Frame(prompt_panel)
        image_row.pack(fill="x", pady=(0, 12))
        ttk.Label(image_row, text="参照画像").pack(side="left", padx=(0, 8))
        ttk.Entry(image_row, textvariable=self.reference_image).pack(side="left", fill="x", expand=True)
        ttk.Button(image_row, text="参照...", command=self._browse_image).pack(side="left", padx=(5, 0))
        ttk.Button(image_row, text="消去", command=lambda: self.reference_image.set("")).pack(side="left", padx=(5, 0))
        ttk.Label(
            prompt_panel,
            text="参照画像はI2I/I2V対応ワークフローと画像対応LMMの登録後に使用できます。",
            wraplength=460,
        ).pack(anchor="w", pady=(0, 10))

        action_row = ttk.Frame(prompt_panel)
        action_row.pack(fill="x")
        self.preview_button = ttk.Button(action_row, text="解釈のみテスト", command=lambda: self._start(True))
        self.preview_button.pack(side="left", padx=(0, 8))
        self.run_button = ttk.Button(
            action_row, text="画像生成を開始", style="Run.TButton", command=lambda: self._start(False)
        )
        self.run_button.pack(side="left", padx=(0, 8))
        self.cancel_button = ttk.Button(
            action_row, text="待機を中止", command=self._request_cancel, state="disabled"
        )
        self.cancel_button.pack(side="left")

        preview_panel = ttk.LabelFrame(right, text="出力結果", padding=10, style="Section.TLabelframe")
        preview_panel.pack(fill="both", expand=True)
        self.image_label = ttk.Label(preview_panel, text="生成画像のプレビュー", anchor="center")
        self.image_label.pack(fill="both", expand=True)
        ttk.Label(preview_panel, textvariable=self.result_info, wraplength=350).pack(anchor="w", pady=(5, 6))
        self.images_list = tk.Listbox(preview_panel, height=4, exportselection=False)
        self.images_list.pack(fill="x", pady=(0, 5))
        self.images_list.bind("<<ListboxSelect>>", self._show_selected_image)
        row = ttk.Frame(preview_panel)
        row.pack(fill="x")
        self.open_button = ttk.Button(row, text="画像を開く", command=self._open_image, state="disabled")
        self.open_button.pack(side="left", padx=(0, 6))
        ttk.Button(row, text="保存先を開く", command=self._open_outputs).pack(side="left")

        status_bar = ttk.Frame(layout)
        status_bar.pack(fill="x", pady=(0, 5))
        ttk.Label(status_bar, textvariable=self.status).pack(side="left", fill="x", expand=True)
        self.progress_bar = ttk.Progressbar(status_bar, mode="indeterminate", length=180)
        self.progress_bar.pack(side="right")
        logs = ttk.LabelFrame(layout, text="実行ログ", padding=5)
        logs.pack(fill="x")
        self.log = scrolledtext.ScrolledText(logs, height=6, wrap="word", state="disabled")
        self.log.pack(fill="x")
        self._log("GUI起動。LM StudioのDeveloper画面でLocal Serverを起動してください。")
        self._log("設定は comfy-orchestrator/config.json に保存され、Gitには含まれません。")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _collect_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["llm"]["provider"] = "lmstudio"
        config["llm"]["base_url"] = self.llm_url.get().strip()
        config["llm"]["model"] = self.model.get().strip() or "SELECT_IN_GUI"
        config["llm"]["unload_after_inference"] = self.unload_llm.get()
        config["comfyui"]["base_url"] = self.comfy_url.get().strip()
        config["comfyui"]["free_before_llm"] = self.free_comfy.get()
        opts = self._overrides()
        config["ui"] = {**opts, "workflow": self.workflow.get()}
        config["ui"]["seed"] = self.seed.get().strip()
        return config

    def _overrides(self) -> dict:
        values = {
            "width": int(self.width.get()),
            "height": int(self.height.get()),
            "steps": int(self.steps.get()),
            "cfg": float(self.cfg.get()),
        }
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        return values

    def _save_settings(self) -> bool:
        if self.working:
            return False
        try:
            config = self._collect_config()
            backup_path = CONFIG.with_suffix(".json.tmp")
            backup_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            core.load_config(backup_path)
            backup_path.replace(CONFIG)
            self.config = config
            self._log("設定保存: config.json")
            self.status.set("設定を保存しました")
            return True
        except (ValueError, OSError, core.OrchestratorError) as exc:
            messagebox.showerror("設定エラー", str(exc))
            return False

    def _browse_image(self) -> None:
        picked = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        )
        if picked:
            self.reference_image.set(picked)

    def _refresh_models(self) -> None:
        settings = copy.deepcopy(self.config["llm"])
        settings["base_url"] = self.llm_url.get().strip()
        def task():
            try:
                models = list_models(settings)
                self.messages.put(("models", models))
            except Exception as exc:
                self.messages.put(("error", f"モデル一覧を取得できません: {exc}"))
        threading.Thread(target=task, daemon=True).start()
        self._log("LM Studioのモデル一覧を取得中...")

    def _check_connections(self) -> None:
        llm = copy.deepcopy(self.config["llm"])
        llm["base_url"] = self.llm_url.get().strip()
        comfy = self.comfy_url.get().strip()
        def task():
            results = []
            for name, fn in (
                ("LM Studio", lambda: list_models(llm)),
                ("ComfyUI", lambda: core.http_json(comfy, "/queue", timeout=12)),
            ):
                try:
                    fn()
                    results.append(name + ": 接続OK")
                except Exception as exc:
                    results.append(name + ": 失敗 (" + str(exc) + ")")
            self.messages.put(("check", results))
        threading.Thread(target=task, daemon=True).start()
        self._log("接続を確認中...")

    def _start(self, dry_run: bool) -> None:
        if self.working:
            return
        if not self._save_settings():
            return
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("入力が必要です", "生成内容を入力してください。")
            return
        if self.model.get().strip() in ("", "SELECT_IN_GUI"):
            messagebox.showwarning("モデル未設定", "「モデルを更新」からLM Studioのモデルを選択してください。")
            return
        image = Path(self.reference_image.get()).expanduser() if self.reference_image.get() else None
        selected = self.workflow.get()
        if selected == "自動":
            selected = None
        overrides = self._overrides()
        cfg = copy.deepcopy(self.config)
        self.stop_event.clear()
        self.working = True
        self.run_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress_bar.start(12)
        self.status.set("解釈テスト中..." if dry_run else "生成準備中...")
        self._log("開始: " + ("解釈のみテスト" if dry_run else "画像生成") + f" / model={cfg['llm']['model']}")

        def task():
            try:
                result = core.execute(
                    cfg, CONFIG, prompt, image=image, dry_run=dry_run,
                    selected_workflow=selected, overrides=overrides,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event,
                )
                images = []
                if not dry_run:
                    for item in output_images(result):
                        try:
                            path = save_output_image(cfg["comfyui"]["base_url"], item, result["prompt_id"])
                            images.append(path)
                        except Exception as exc:
                            self.messages.put(("progress", f"画像取得エラー: {exc}"))
                self.messages.put(("done", (result, images)))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
            finally:
                self.messages.put(("idle", None))
        threading.Thread(target=task, daemon=True).start()

    def _request_cancel(self) -> None:
        self.stop_event.set()
        self.status.set("停止要求済み（ComfyUI側のジョブは中断しません）")
        self._log("処理の待機終了を要求しました。すでに投入された生成ジョブは続行します。")

    def _consume_messages(self) -> None:
        try:
            while True:
                kind, data = self.messages.get_nowait()
                if kind == "progress":
                    self._log(data)
                    self.status.set(data)
                elif kind == "check":
                    for line in data:
                        self._log(line)
                    self.status.set("接続確認が完了しました")
                elif kind == "models":
                    names = [item["key"] for item in data]
                    self.model_box.configure(values=names)
                    if self.model.get() not in names and names:
                        self.model.set(names[0])
                    self._log(f"LM Studioモデル: {len(names)}件。必要なモデルを選択して設定を保存してください。")
                    self.status.set(f"モデル一覧を更新: {len(names)}件")
                elif kind == "done":
                    result, images = data
                    if result["status"] == "dry_run":
                        self._log("解釈結果:\n" + json.dumps(result, ensure_ascii=False, indent=2))
                        self.status.set("解釈テスト完了（ComfyUI未実行）")
                    else:
                        self.image_paths = images
                        self.images_list.delete(0, "end")
                        for file in images:
                            self.images_list.insert("end", file.name)
                        if images:
                            self.images_list.selection_set(0)
                            self._display_image(images[0])
                            self.open_button.configure(state="normal")
                        self.result_info.set(
                            f"生成完了: {len(images)}画像保存 / prompt_id={result['prompt_id']}"
                        )
                        self._log("生成完了: " + json.dumps(result.get("parameters", {}), ensure_ascii=False))
                        self.status.set("画像生成完了")
                elif kind == "error":
                    self._log("ERROR: " + data)
                    self.status.set("エラー: " + data[:110])
                    messagebox.showerror("処理エラー", data)
                elif kind == "idle":
                    self.working = False
                    self.run_button.configure(state="normal")
                    self.preview_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self.progress_bar.stop()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._consume_messages)

    def _show_selected_image(self, _event=None) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self._display_image(self.image_paths[selected[0]])

    def _display_image(self, path: Path) -> None:
        try:
            photo = tk.PhotoImage(file=str(path))
            scale = max(1, (max(photo.width(), photo.height()) + 439) // 440)
            self.preview_photo = photo.subsample(scale, scale)
            self.image_label.configure(image=self.preview_photo, text="")
        except tk.TclError:
            self.preview_photo = None
            self.image_label.configure(image="", text="プレビュー非対応の画像です。ファイルを開いてください。")
        self.result_info.set(path.name)

    def _open_image(self) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self._open_path(self.image_paths[selected[0]])

    def _open_outputs(self) -> None:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        self._open_path(OUTPUTS)

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                self._log("出力先: " + str(path))
        except OSError as exc:
            messagebox.showerror("ファイルを開けません", str(exc))

    def _on_close(self) -> None:
        if self.working and not messagebox.askokcancel(
            "実行中", "現在の操作の進捗表示は終了します。ComfyUI側の生成ジョブは停止しません。閉じますか？"
        ):
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
