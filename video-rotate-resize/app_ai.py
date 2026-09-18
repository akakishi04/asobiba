from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_backends import (
    AI_CHOICES,
    AI_NONE,
    AI_RVRT,
    AI_RVRT_SEEDVR2,
    AI_SEEDVR2,
    RVRT_TASKS,
    AIConfig,
    build_rvrt_command,
    build_seedvr2_command,
    normalize_png_sequence,
    resolve_python,
    validate_for_mode,
)
from ai_setup import setup_ai_environment
from video_tool import (
    VideoToolError,
    build_extract_png_command,
    build_ffmpeg_command,
    build_frames_to_lossless_video_command,
    build_frames_to_video_command,
    build_lossless_transform_command,
    find_executable,
    nvenc_available,
    probe_media,
    transformed_dimensions,
    validate_target_resolution,
)

ROTATIONS = {
    "なし": "none",
    "時計回り 90°": "cw90",
    "反時計回り 90°": "ccw90",
    "180°": "180",
}
RESOLUTIONS = {
    "元の解像度": None,
    "1080p (1920×1080)": (1920, 1080),
    "720p (1280×720)": (1280, 720),
    "4K (3840×2160)": (3840, 2160),
    "カスタム": "custom",
}


class Cancelled(RuntimeError):
    pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Video Rotate, Resize & AI Restore")
        root.geometry("900x740")
        root.minsize(780, 640)
        self.proc: subprocess.Popen[str] | None = None
        self.running = False
        self.cancelled = False
        self.setup_step = 0
        self.base = Path(__file__).resolve().parent
        self.config_path = self.base / "ai_config.json"
        try:
            self.config = AIConfig.load(self.config_path)
        except VideoToolError:
            self.config = AIConfig()

        self.input = tk.StringVar()
        self.output = tk.StringVar()
        self.info = tk.StringVar(value="動画を選択してください。")
        self.rotation = tk.StringVar(value="時計回り 90°")
        self.resolution = tk.StringVar(value="1080p (1920×1080)")
        self.cw = tk.StringVar(value="1920")
        self.ch = tk.StringVar(value="1080")
        self.encoder = tk.StringVar(value="自動（NVENC優先）")
        self.ai_mode = tk.StringVar(value="なし")
        self.ai_state = tk.StringVar()
        self.status = tk.StringVar(value="待機中")
        self.progress = tk.DoubleVar(value=0)
        self._ui()
        self._refresh_ai_state()
        root.protocol("WM_DELETE_WINDOW", self._close)

    def _ui(self):
        f = ttk.Frame(self.root, padding=16)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(9, weight=1)

        self._path_row(f, 0, "入力動画", self.input, self._pick_input)
        ttk.Label(f, textvariable=self.info, foreground="#555").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 8)
        )
        self._path_row(f, 2, "出力先", self.output, self._pick_output)

        s = ttk.LabelFrame(f, text="変換設定", padding=10)
        s.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 8))
        s.columnconfigure(1, weight=1)
        self._combo_row(s, 0, "回転", self.rotation, list(ROTATIONS))
        box = self._combo_row(s, 1, "解像度", self.resolution, list(RESOLUTIONS))
        box.bind("<<ComboboxSelected>>", lambda _e: self._custom_state())

        c = ttk.Frame(s)
        c.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=3)
        self.cw_entry = ttk.Entry(c, width=8, textvariable=self.cw)
        self.cw_entry.pack(side="left")
        ttk.Label(c, text=" × ").pack(side="left")
        self.ch_entry = ttk.Entry(c, width=8, textvariable=self.ch)
        self.ch_entry.pack(side="left")
        ttk.Label(c, text=" px").pack(side="left")

        self._combo_row(
            s,
            3,
            "エンコーダー",
            self.encoder,
            ["自動（NVENC優先）", "NVIDIA NVENC", "CPU (libx264)"],
        )
        ttk.Label(s, text="AI鮮明化").grid(row=4, column=0, sticky="w", pady=3)
        ar = ttk.Frame(s)
        ar.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=3)
        ar.columnconfigure(0, weight=1)
        ttk.Combobox(
            ar,
            textvariable=self.ai_mode,
            values=list(AI_CHOICES),
            state="readonly",
        ).grid(row=0, column=0, sticky="ew")
        self.setup_button = ttk.Button(
            ar, text="AI自動セットアップ", command=self._auto_setup
        )
        self.setup_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Button(ar, text="AI設定...", command=self._settings).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Label(s, textvariable=self.ai_state, foreground="#555").grid(
            row=5, column=1, sticky="w", padx=(10, 0)
        )
        ttk.Label(
            s,
            text=(
                "AIなしは従来のFFmpeg変換。AI環境は初回だけ自動セットアップできます。"
                " AI時は最終解像度を維持し、元動画の音声を戻します。"
            ),
            foreground="#555",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self._custom_state()

        ttk.Progressbar(f, variable=self.progress, maximum=100).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(10, 4)
        )
        ttk.Label(f, textvariable=self.status).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        b = ttk.Frame(f)
        b.grid(row=6, column=0, columnspan=3, sticky="w", pady=(2, 8))
        self.start = ttk.Button(b, text="変換開始", command=self._start)
        self.start.pack(side="left")
        self.stop = ttk.Button(
            b, text="キャンセル", command=self._cancel, state="disabled"
        )
        self.stop.pack(side="left", padx=(8, 0))

        ttk.Label(f, text="ログ").grid(row=7, column=0, columnspan=3, sticky="w")
        lf = ttk.Frame(f)
        lf.grid(row=8, column=0, columnspan=3, rowspan=2, sticky="nsew")
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self.log = tk.Text(lf, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(lf, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)

    def _path_row(self, parent, row, label, var, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(
            row=row, column=1, sticky="ew", padx=8, pady=3
        )
        ttk.Button(parent, text="参照...", command=command).grid(
            row=row, column=2, pady=3
        )

    def _combo_row(self, parent, row, label, var, values):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        box = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        box.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=3)
        return box

    def _custom_state(self):
        state = "normal" if self.resolution.get() == "カスタム" else "disabled"
        self.cw_entry.configure(state=state)
        self.ch_entry.configure(state=state)

    def _pick_input(self):
        p = filedialog.askopenfilename(
            title="入力動画",
            filetypes=[
                ("動画", "*.mp4 *.mov *.mkv *.m4v *.avi *.webm"),
                ("すべて", "*.*"),
            ],
        )
        if not p:
            return
        self.input.set(p)
        src = Path(p)
        self.output.set(str(src.with_name(src.stem + "_converted.mp4")))
        try:
            i = probe_media(src)
            self.info.set(f"{i.width}×{i.height} / {i.codec} / {i.fps or 0:.3f} fps")
        except Exception as e:
            self.info.set(f"解析失敗: {e}")

    def _pick_output(self):
        current = self.output.get() or "output.mp4"
        p = filedialog.asksaveasfilename(
            title="出力先",
            initialfile=Path(current).name,
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4")],
        )
        if p:
            self.output.set(p)

    def _target(self):
        v = RESOLUTIONS[self.resolution.get()]
        if v != "custom":
            return v
        try:
            v = (int(self.cw.get()), int(self.ch.get()))
        except ValueError as e:
            raise VideoToolError("カスタム解像度は整数にしてください。") from e
        validate_target_resolution(v)
        return v

    def _enc(self, ffmpeg):
        v = self.encoder.get()
        if v == "CPU (libx264)":
            return "libx264"
        if v == "NVIDIA NVENC":
            if not nvenc_available(ffmpeg):
                raise VideoToolError("h264_nvencを利用できません。")
            return "nvenc"
        return "nvenc" if nvenc_available(ffmpeg) else "libx264"

    def _start(self):
        if self.running:
            return
        try:
            src, dst = Path(self.input.get().strip()), Path(self.output.get().strip())
            if not src.is_file():
                raise VideoToolError("入力動画を選択してください。")
            if dst.suffix.lower() != ".mp4" or not dst.parent.exists():
                raise VideoToolError("有効なMP4出力先を指定してください。")
            if src.resolve() == dst.resolve():
                raise VideoToolError("入力と出力は別ファイルにしてください。")
            rot, target = ROTATIONS[self.rotation.get()], self._target()
            mode = AI_CHOICES[self.ai_mode.get()]
            ffmpeg = find_executable("ffmpeg")
            find_executable("ffprobe")
            enc = self._enc(ffmpeg)
            info = probe_media(src)
            fps = info.fps or 30.0

            if mode == AI_NONE:
                if rot == "none" and target is None:
                    raise VideoToolError(
                        "回転、解像度変更、またはAI鮮明化を指定してください。"
                    )
                cmd = build_ffmpeg_command(src, dst, rot, target, enc, ffmpeg)
                self._launch(self._standard_worker, cmd, dst)
                return

            validate_for_mode(self.config, mode)
            dims = transformed_dimensions(info, rot, target)
            self._launch(
                self._ai_worker, src, dst, rot, target, mode, enc, fps, dims, ffmpeg
            )
        except VideoToolError as e:
            messagebox.showerror("設定エラー", str(e))

    def _launch(self, worker, *args):
        self.cancelled = False
        self.running = True
        self.start.configure(state="disabled")
        self.setup_button.configure(state="disabled")
        self.stop.configure(state="normal")
        self.progress.set(0)
        threading.Thread(target=worker, args=args, daemon=True).start()

    def _standard_worker(self, cmd, dst):
        try:
            self._stage(5, "通常変換中...")
            self._run(cmd, "FFmpeg")
            self._done(dst)
        except Cancelled:
            self._cancelled()
        except Exception as e:
            self._failed(e)
        finally:
            self._idle()

    def _ai_worker(self, src, dst, rot, target, mode, enc, fps, dims, ffmpeg):
        try:
            with tempfile.TemporaryDirectory(prefix=".video_ai_", dir=dst.parent) as td:
                t = Path(td)
                frames = None

                if mode in {AI_RVRT, AI_RVRT_SEEDVR2}:
                    self._stage(5, "RVRT用フレーム展開...")
                    inp = t / "rvrt_input"
                    inp.mkdir(parents=True)
                    self._run(
                        build_extract_png_command(
                            src, inp / "frame%06d.png", rot, target, ffmpeg
                        ),
                        "Frame extract",
                    )
                    self._stage(20, "RVRT復元中...")
                    raw = t / "rvrt_raw"
                    raw.mkdir()
                    cmd, cwd = build_rvrt_command(
                        self.config,
                        inp,
                        raw,
                        self.base / "rvrt_runner.py",
                    )
                    self._run(cmd, "RVRT", cwd)
                    frames = t / "rvrt_out"
                    normalize_png_sequence(raw, frames)

                if mode in {AI_SEEDVR2, AI_RVRT_SEEDVR2}:
                    if mode == AI_RVRT_SEEDVR2:
                        self._stage(55, "SeedVR2用中間映像作成...")
                        seed_in = t / "rvrt_seed.mkv"
                        self._run(
                            build_frames_to_lossless_video_command(
                                frames / "frame%06d.png", fps, seed_in, ffmpeg
                            ),
                            "Lossless intermediate",
                        )
                    else:
                        seed_in = src
                        if rot != "none" or target is not None:
                            self._stage(8, "SeedVR2用中間映像作成...")
                            seed_in = t / "seed_input.mkv"
                            self._run(
                                build_lossless_transform_command(
                                    src, seed_in, rot, target, ffmpeg
                                ),
                                "Lossless transform",
                            )
                    self._stage(
                        62 if mode == AI_RVRT_SEEDVR2 else 20, "SeedVR2復元中..."
                    )
                    out = t / "seed_out"
                    out.mkdir()
                    cmd, cwd = build_seedvr2_command(
                        self.config, seed_in, out, min(dims)
                    )
                    self._run(cmd, "SeedVR2", cwd)
                    frames = t / "seed_norm"
                    normalize_png_sequence(out, frames)

                if frames is None:
                    raise VideoToolError("AI出力を取得できませんでした。")
                self._stage(92, "最終MP4作成中...")
                self._run(
                    build_frames_to_video_command(
                        frames / "frame%06d.png", fps, src, dst, enc, dims, ffmpeg
                    ),
                    "Final encode",
                )
                self._done(dst)
        except Cancelled:
            self._cancelled()
        except Exception as e:
            self._failed(e)
        finally:
            self._idle()

    def _auto_setup(self):
        if self.running:
            return
        ok = messagebox.askyesno(
            "AI自動セットアップ",
            (
                "RVRT と SeedVR2 の専用環境を自動構築します。\n\n"
                "・Python 3.12 が無い場合は winget でユーザー領域へ追加\n"
                "・CUDA版PyTorchを2環境へインストール\n"
                "・SeedVR2を ai_engines/ に取得\n"
                "・数GBのダウンロード/ディスク使用が発生します\n\n"
                "続行しますか？"
            ),
        )
        if ok:
            self._launch(self._setup_worker)

    def _setup_worker(self):
        self.setup_step = 0
        try:
            self._stage(1, "AI環境セットアップ開始...")

            def run_setup(cmd: list[str], label: str, cwd: Path | None):
                self.setup_step += 1
                percent = min(94, 4 + self.setup_step * 7)
                self.root.after(0, lambda p=percent: self.progress.set(p))
                self.root.after(0, lambda text=label: self.status.set(f"AIセットアップ: {text}"))
                self._run(cmd, label, cwd)

            result = setup_ai_environment(
                self.base,
                run=run_setup,
                log=lambda text: self._log_async(text + "\n"),
            )
            self.config.rvrt_repo = ""
            self.config.rvrt_python = str(result.rvrt_python)
            self.config.seedvr2_repo = str(result.seedvr2_repo)
            self.config.seedvr2_python = str(result.seedvr2_python)
            self.config.save(self.config_path)
            self.root.after(0, self._refresh_ai_state)
            self.root.after(0, lambda: self.progress.set(100))
            self.root.after(0, lambda: self.status.set("AI環境セットアップ完了"))
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "AIセットアップ完了",
                    "RVRT / SeedVR2 の環境を構築して設定へ登録しました。\nモデル重みは初回使用時に自動取得されます。",
                ),
            )
        except Cancelled:
            self._cancelled()
        except Exception as e:
            self._failed(e)
        finally:
            self._idle()

    def _run(self, cmd, label, cwd=None):
        if self.cancelled:
            raise Cancelled()
        self._log_async(f"\n[{label}]\n{subprocess.list2cmdline(cmd)}\n")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        p = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
        self.proc = p
        try:
            for line in p.stdout or ():
                if line.strip():
                    self._log_async(line)
                if self.cancelled:
                    self._kill(p)
                    break
            code = p.wait()
        finally:
            if self.proc is p:
                self.proc = None
        if self.cancelled:
            raise Cancelled()
        if code:
            raise VideoToolError(f"{label} failed (code {code})")

    def _stage(self, n, text):
        self.root.after(0, lambda: self.progress.set(n))
        self.root.after(0, lambda: self.status.set(text))
        self._log_async(f"\n--- {text} ---\n")

    def _done(self, dst):
        self.root.after(0, lambda: self.progress.set(100))
        self.root.after(0, lambda: self.status.set("完了"))
        self._log_async(f"\n完了: {dst}\n")
        self.root.after(
            0, lambda: messagebox.showinfo("完了", f"保存しました:\n{dst}")
        )

    def _failed(self, e):
        self.root.after(0, lambda: self.status.set("エラー"))
        self._log_async(f"\nエラー: {e}\n")
        self.root.after(0, lambda: messagebox.showerror("処理エラー", str(e)))

    def _cancelled(self):
        self.root.after(0, lambda: self.status.set("キャンセルしました"))
        self._log_async("\nキャンセルしました。\n")

    def _idle(self):
        self.proc = None
        self.running = False
        self.root.after(0, lambda: self.start.configure(state="normal"))
        self.root.after(0, lambda: self.setup_button.configure(state="normal"))
        self.root.after(0, lambda: self.stop.configure(state="disabled"))

    def _cancel(self):
        self.cancelled = True
        self.status.set("キャンセル中...")
        if self.proc:
            self._kill(self.proc)

    @staticmethod
    def _kill(p):
        if p.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(p.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                p.terminate()
        except OSError:
            pass

    def _log_async(self, text):
        self.root.after(0, lambda: self._log(text))

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _settings(self):
        w = tk.Toplevel(self.root)
        w.title("AI設定")
        w.geometry("780x550")
        w.grab_set()
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        vals = {
            "rp": tk.StringVar(value=self.config.rvrt_python),
            "rc": tk.StringVar(value=str(self.config.rvrt_chunk_size)),
            "ro": tk.StringVar(value=str(self.config.rvrt_chunk_overlap)),
            "sr": tk.StringVar(value=self.config.seedvr2_repo),
            "sp": tk.StringVar(value=self.config.seedvr2_python),
            "sm": tk.StringVar(value=self.config.seedvr2_model),
            "sb": tk.StringVar(value=str(self.config.seedvr2_batch_size)),
            "ss": tk.StringVar(value=str(self.config.seedvr2_blocks_to_swap)),
            "sx": tk.StringVar(value=str(self.config.seedvr2_resolution_override)),
        }
        rev = {v: k for k, v in RVRT_TASKS.items()}
        rt = tk.StringVar(
            value=rev.get(self.config.rvrt_task, next(iter(RVRT_TASKS)))
        )

        def row(r, label, key, directory=False):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=vals[key]).grid(
                row=r, column=1, sticky="ew", padx=8, pady=3
            )

            def pick():
                p = filedialog.askdirectory() if directory else filedialog.askopenfilename()
                if p:
                    vals[key].set(p)

            ttk.Button(f, text="参照...", command=pick).grid(row=r, column=2)

        ttk.Label(f, text="RVRT (vsrvrt)", font=("", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        row(1, "RVRT Python", "rp")
        ttk.Label(f, text="RVRTモデル").grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            f, textvariable=rt, values=list(RVRT_TASKS), state="readonly"
        ).grid(row=2, column=1, sticky="ew", padx=8)
        radv = ttk.Frame(f)
        radv.grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ttk.Label(radv, text="Chunk").pack(side="left")
        ttk.Entry(radv, width=7, textvariable=vals["rc"]).pack(
            side="left", padx=(3, 10)
        )
        ttk.Label(radv, text="Overlap").pack(side="left")
        ttk.Entry(radv, width=7, textvariable=vals["ro"]).pack(
            side="left", padx=(3, 10)
        )

        ttk.Separator(f).grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=10
        )
        ttk.Label(f, text="SeedVR2", font=("", 10, "bold")).grid(
            row=5, column=0, sticky="w"
        )
        row(6, "SeedVR2フォルダ", "sr", True)
        row(7, "SeedVR2 Python", "sp")
        ttk.Label(f, text="Model").grid(row=8, column=0, sticky="w")
        ttk.Entry(f, textvariable=vals["sm"]).grid(
            row=8, column=1, sticky="ew", padx=8
        )
        adv = ttk.Frame(f)
        adv.grid(row=9, column=1, sticky="w", padx=8, pady=6)
        for label, key in [
            ("Batch", "sb"),
            ("BlockSwap", "ss"),
            ("処理短辺(0=ネイティブ)", "sx"),
        ]:
            ttk.Label(adv, text=label).pack(side="left")
            ttk.Entry(adv, width=7, textvariable=vals[key]).pack(
                side="left", padx=(3, 10)
            )
        ttk.Label(
            f,
            text=(
                "自動セットアップ推奨。4070 Ti SUPER 16GB向けSeedVR2初期値: "
                "3B FP8 / Batch 5 / BlockSwap 20 / VAE tiling。"
            ),
            foreground="#555",
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=8)

        def save():
            try:
                rchunk = int(vals["rc"].get())
                rover = int(vals["ro"].get())
                batch = int(vals["sb"].get())
                swap = int(vals["ss"].get())
                res = int(vals["sx"].get())
                if (
                    rchunk < 4
                    or rover < 0
                    or rover >= rchunk
                    or batch < 1
                    or swap < 0
                    or res < 0
                ):
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "AI設定",
                    "RVRT Chunk>=4、0<=Overlap<Chunk、Batch>=1、BlockSwap/処理短辺>=0の整数にしてください。",
                    parent=w,
                )
                return
            self.config = AIConfig(
                rvrt_repo="",
                rvrt_python=vals["rp"].get().strip(),
                rvrt_task=RVRT_TASKS[rt.get()],
                rvrt_chunk_size=rchunk,
                rvrt_chunk_overlap=rover,
                seedvr2_repo=vals["sr"].get().strip(),
                seedvr2_python=vals["sp"].get().strip(),
                seedvr2_model=vals["sm"].get().strip(),
                seedvr2_batch_size=batch,
                seedvr2_blocks_to_swap=swap,
                seedvr2_temporal_overlap=self.config.seedvr2_temporal_overlap,
                seedvr2_resolution_override=res,
                seedvr2_vae_tiling=True,
                seedvr2_vae_tile_size=self.config.seedvr2_vae_tile_size,
                seedvr2_vae_tile_overlap=self.config.seedvr2_vae_tile_overlap,
            )
            self.config.save(self.config_path)
            self._refresh_ai_state()
            w.destroy()

        bar = ttk.Frame(f)
        bar.grid(row=11, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(bar, text="キャンセル", command=w.destroy).pack(side="right")
        ttk.Button(bar, text="保存", command=save).pack(side="right", padx=8)

    def _refresh_ai_state(self):
        def python_ready(py):
            try:
                resolve_python(py)
                return True
            except VideoToolError:
                return False

        r = python_ready(self.config.rvrt_python) and (
            self.base / "rvrt_runner.py"
        ).is_file()
        s = (
            bool(self.config.seedvr2_repo)
            and (Path(self.config.seedvr2_repo) / "inference_cli.py").is_file()
            and python_ready(self.config.seedvr2_python)
        )
        self.ai_state.set(
            f"RVRT: {'準備済み' if r else '未設定'} / SeedVR2: {'準備済み' if s else '未設定'}"
        )

    def _close(self):
        if self.running and not messagebox.askyesno(
            "終了", "実行中の処理を停止して終了しますか？"
        ):
            return
        self.cancelled = True
        if self.proc:
            self._kill(self.proc)
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    # Direct execution keeps the optimized AI pipeline too. Drag & Drop still
    # requires launcher.py / run.bat because tkinterdnd2 owns the root window.
    import sys

    from eta_support import enable_eta
    from rvrt_streaming import enable_rvrt_streaming
    from seedvr2_streaming import enable_seedvr2_streaming
    from settings_extension import enable_seedvr2_chunk_settings

    module = sys.modules[__name__]
    enable_seedvr2_streaming(module)
    enable_rvrt_streaming(module)
    enable_seedvr2_chunk_settings(module)
    enable_eta(module)
    main()
