from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ai_restoration import (
    AI_MODES,
    RestorationConfig,
    load_engine_config,
    run_restoration_pipeline,
)
from video_tool import (
    VideoToolError,
    build_ffmpeg_command,
    find_executable,
    nvenc_available,
    probe_media,
    validate_target_resolution,
)


ROTATION_CHOICES = {
    "なし": "none",
    "時計回り 90°": "cw90",
    "反時計回り 90°": "ccw90",
    "180°": "180",
}

RESOLUTION_CHOICES = {
    "元の解像度": None,
    "1080p (1920×1080)": (1920, 1080),
    "720p (1280×720)": (1280, 720),
    "4K (3840×2160)": (3840, 2160),
    "カスタム": "custom",
}

AI_CHOICES = {label: key for key, label in AI_MODES.items()}

RVRT_TASK_CHOICES = {
    "Deblur / GoPro (推奨)": "005_RVRT_videodeblurring_GoPro_16frames",
    "Deblur / DVD": "004_RVRT_videodeblurring_DVD_16frames",
    "Denoise / DAVIS": "006_RVRT_videodenoising_DAVIS_16frames",
}

PROGRESS_KEYS = {
    "frame",
    "fps",
    "stream_0_0_q",
    "bitrate",
    "total_size",
    "out_time_us",
    "out_time_ms",
    "out_time",
    "dup_frames",
    "drop_frames",
    "speed",
    "progress",
}


class VideoTransformApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Video Transform & AI Restore")
        self.root.geometry("820x760")
        self.root.minsize(740, 680)

        self.process: subprocess.Popen[str] | None = None
        self.duration_seconds: float | None = None
        self.running = False

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.info_var = tk.StringVar(value="動画を選択してください。")
        self.rotation_var = tk.StringVar(value="時計回り 90°")
        self.resolution_var = tk.StringVar(value="1080p (1920×1080)")
        self.custom_width_var = tk.StringVar(value="1920")
        self.custom_height_var = tk.StringVar(value="1080")
        self.encoder_var = tk.StringVar(value="自動（NVENC優先）")
        self.ai_mode_var = tk.StringVar(value=AI_MODES["off"])
        self.rvrt_task_var = tk.StringVar(value="Deblur / GoPro (推奨)")
        self.status_var = tk.StringVar(value="待機中")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(10, weight=1)

        ttk.Label(outer, text="入力動画").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(outer, text="参照...", command=self._choose_input).grid(row=0, column=2, pady=4)

        ttk.Label(outer, textvariable=self.info_var, foreground="#555555").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 10)
        )

        ttk.Label(outer, text="出力先").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(outer, text="参照...", command=self._choose_output).grid(row=2, column=2, pady=4)

        transform = ttk.LabelFrame(outer, text="変換設定", padding=12)
        transform.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        transform.columnconfigure(1, weight=1)

        ttk.Label(transform, text="回転").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            transform,
            textvariable=self.rotation_var,
            values=list(ROTATION_CHOICES),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(transform, text="解像度").grid(row=1, column=0, sticky="w", pady=4)
        resolution_box = ttk.Combobox(
            transform,
            textvariable=self.resolution_var,
            values=list(RESOLUTION_CHOICES),
            state="readonly",
        )
        resolution_box.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        resolution_box.bind("<<ComboboxSelected>>", lambda _event: self._update_custom_state())

        custom_frame = ttk.Frame(transform)
        custom_frame.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=4)
        self.custom_width_entry = ttk.Entry(custom_frame, width=8, textvariable=self.custom_width_var)
        self.custom_width_entry.pack(side="left")
        ttk.Label(custom_frame, text=" × ").pack(side="left")
        self.custom_height_entry = ttk.Entry(custom_frame, width=8, textvariable=self.custom_height_var)
        self.custom_height_entry.pack(side="left")
        ttk.Label(custom_frame, text=" px").pack(side="left")

        ttk.Label(transform, text="エンコーダー").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            transform,
            textvariable=self.encoder_var,
            values=["自動（NVENC優先）", "NVIDIA NVENC", "CPU (libx264)"],
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(
            transform,
            text="AI有効時は、回転・リサイズを先に適用してからAI復元します。元解像度維持も選べます。",
            foreground="#555555",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ai = ttk.LabelFrame(outer, text="AI鮮明化 / Video Restoration", padding=12)
        ai.grid(row=4, column=0, columnspan=3, sticky="ew", pady=8)
        ai.columnconfigure(1, weight=1)

        ttk.Label(ai, text="処理方式").grid(row=0, column=0, sticky="w", pady=4)
        ai_box = ttk.Combobox(
            ai,
            textvariable=self.ai_mode_var,
            values=list(AI_CHOICES),
            state="readonly",
        )
        ai_box.grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)
        ai_box.bind("<<ComboboxSelected>>", lambda _event: self._update_ai_state())

        ttk.Label(ai, text="RVRTモデル").grid(row=1, column=0, sticky="w", pady=4)
        self.rvrt_task_box = ttk.Combobox(
            ai,
            textvariable=self.rvrt_task_var,
            values=list(RVRT_TASK_CHOICES),
            state="readonly",
        )
        self.rvrt_task_box.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(
            ai,
            text="RVRTは忠実寄りの1x復元、SeedVR2は生成力の強い復元。併用時は RVRT → SeedVR2 の順です。",
            foreground="#555555",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(
            ai,
            text="AIエンジンのrepo/環境は ai_engines.json で指定します。AIなしなら追加セットアップ不要です。",
            foreground="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.progress = ttk.Progressbar(outer, variable=self.progress_var, maximum=100.0, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        ttk.Label(outer, textvariable=self.status_var).grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 8))

        button_frame = ttk.Frame(outer)
        button_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.start_button = ttk.Button(button_frame, text="変換開始", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(button_frame, text="キャンセル", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="ログ").grid(row=9, column=0, columnspan=3, sticky="w")
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=10, column=0, columnspan=3, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        self._update_custom_state()
        self._update_ai_state()

    def _update_custom_state(self) -> None:
        state = "normal" if self.resolution_var.get() == "カスタム" else "disabled"
        self.custom_width_entry.configure(state=state)
        self.custom_height_entry.configure(state=state)

    def _update_ai_state(self) -> None:
        mode = AI_CHOICES[self.ai_mode_var.get()]
        rvrt_enabled = mode in {"rvrt", "rvrt_seedvr2"}
        self.rvrt_task_box.configure(state="readonly" if rvrt_enabled else "disabled")

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="入力動画を選択",
            filetypes=[("動画ファイル", "*.mp4 *.mov *.mkv *.m4v *.avi *.webm"), ("すべてのファイル", "*.*")],
        )
        if not path:
            return
        self.input_var.set(path)
        source = Path(path)
        self.output_var.set(str(source.with_name(f"{source.stem}_converted.mp4")))
        self.info_var.set("解析中...")
        threading.Thread(target=self._probe_worker, args=(path,), daemon=True).start()

    def _choose_output(self) -> None:
        initial = self.output_var.get() or "output.mp4"
        path = filedialog.asksaveasfilename(
            title="出力先を選択",
            initialfile=Path(initial).name,
            initialdir=str(Path(initial).parent) if Path(initial).parent.exists() else None,
            defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4")],
        )
        if path:
            self.output_var.set(path)

    def _probe_worker(self, path: str) -> None:
        try:
            info = probe_media(path)
            self.duration_seconds = info.duration_seconds
            fps_text = f"{info.fps:.3f} fps" if info.fps else "fps不明"
            duration_text = self._format_duration(info.duration_seconds) if info.duration_seconds is not None else "長さ不明"
            rotation_text = f" / 回転情報 {info.rotation}°" if info.rotation else ""
            text = f"{info.width}×{info.height} / {info.codec} / {fps_text} / {duration_text}{rotation_text}"
            self.root.after(0, lambda: self.info_var.set(text))
        except Exception as exc:
            self.duration_seconds = None
            self.root.after(0, lambda: self.info_var.set(f"解析失敗: {exc}"))

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(round(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"

    def _target_resolution(self) -> tuple[int, int] | None:
        selected = RESOLUTION_CHOICES[self.resolution_var.get()]
        if selected != "custom":
            return selected
        try:
            target = (int(self.custom_width_var.get()), int(self.custom_height_var.get()))
        except ValueError as exc:
            raise VideoToolError("カスタム解像度は整数で入力してください。") from exc
        validate_target_resolution(target)
        return target

    def _selected_encoder(self, ffmpeg_bin: str) -> str:
        value = self.encoder_var.get()
        if value == "CPU (libx264)":
            return "libx264"
        if value == "NVIDIA NVENC":
            if not nvenc_available(ffmpeg_bin):
                raise VideoToolError("この FFmpeg では h264_nvenc を利用できません。")
            return "nvenc"
        return "nvenc" if nvenc_available(ffmpeg_bin) else "libx264"

    def _start(self) -> None:
        if self.running:
            return
        try:
            source = Path(self.input_var.get().strip())
            destination = Path(self.output_var.get().strip())
            if not source.is_file():
                raise VideoToolError("入力動画を選択してください。")
            if not destination.name or destination.suffix.lower() != ".mp4":
                raise VideoToolError("出力先はMP4で指定してください。")
            if not destination.parent.exists():
                raise VideoToolError("出力先フォルダが存在しません。")

            rotation = ROTATION_CHOICES[self.rotation_var.get()]
            target = self._target_resolution()
            ai_mode = AI_CHOICES[self.ai_mode_var.get()]
            if rotation == "none" and target is None and ai_mode == "off":
                raise VideoToolError("回転・解像度変更・AI鮮明化のいずれかを指定してください。")

            ffmpeg_bin = find_executable("ffmpeg")
            find_executable("ffprobe")
            encoder = self._selected_encoder(ffmpeg_bin)
            restoration = RestorationConfig(
                mode=ai_mode,
                rvrt_task=RVRT_TASK_CHOICES[self.rvrt_task_var.get()],
            )
            engines = load_engine_config()
        except VideoToolError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return

        self._set_running(True)
        self.progress_var.set(0.0)
        self.status_var.set("処理中...")
        self._append_log("\n--- 処理開始 ---\n")
        self._append_log(f"Encoder: {encoder}\nAI: {self.ai_mode_var.get()}\n")
        threading.Thread(
            target=self._pipeline_worker,
            args=(source, destination, rotation, target, encoder, ffmpeg_bin, restoration, engines),
            daemon=True,
        ).start()

    def _pipeline_worker(
        self,
        source: Path,
        destination: Path,
        rotation: str,
        target: tuple[int, int] | None,
        encoder: str,
        ffmpeg_bin: str,
        restoration: RestorationConfig,
        engines,
    ) -> None:
        try:
            if restoration.mode == "off":
                command = build_ffmpeg_command(source, destination, rotation, target, encoder, ffmpeg_bin)
                self._run_ffmpeg(command)
            else:
                with tempfile.TemporaryDirectory(prefix="video_transform_") as tmp_raw:
                    prepared = source
                    if rotation != "none" or target is not None:
                        prepared = Path(tmp_raw) / "prepared.mp4"
                        command = build_ffmpeg_command(source, prepared, rotation, target, encoder, ffmpeg_bin)
                        self._append_from_worker("[Preprocess] 回転/リサイズ\n")
                        self._run_ffmpeg(command)
                    if not self.running:
                        return
                    self.root.after(0, lambda: self.progress.configure(mode="indeterminate"))
                    self.root.after(0, self.progress.start)
                    run_restoration_pipeline(
                        prepared,
                        destination,
                        restoration,
                        engines,
                        encoder=encoder,
                        ffmpeg=ffmpeg_bin,
                        on_line=lambda line: self._append_from_worker(line + "\n"),
                        register_process=self._register_process,
                    )
                    self.root.after(0, self.progress.stop)
                    self.root.after(0, lambda: self.progress.configure(mode="determinate"))

            if not self.running:
                return
            self.root.after(0, lambda: self.progress_var.set(100.0))
            self.root.after(0, lambda: self.status_var.set("完了"))
            self.root.after(0, lambda: self._append_log(f"\n完了: {destination}\n"))
            self.root.after(0, lambda: messagebox.showinfo("変換完了", f"保存しました:\n{destination}"))
        except Exception as exc:
            if self.running:
                self.root.after(0, lambda: self.status_var.set("エラー"))
                self.root.after(0, lambda: self._append_log(f"\nエラー: {exc}\n"))
                self.root.after(0, lambda: messagebox.showerror("変換エラー", str(exc)))
        finally:
            self.process = None
            self.root.after(0, self.progress.stop)
            self.root.after(0, lambda: self.progress.configure(mode="determinate"))
            self.root.after(0, lambda: self._set_running(False))

    def _run_ffmpeg(self, command: list[str]) -> None:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._append_from_worker(f"Command: {subprocess.list2cmdline(command)}\n")
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        self._register_process(process)
        try:
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key in {"out_time_us", "out_time_ms"}:
                        self._update_progress_from_microseconds(value)
                        continue
                    if key == "speed":
                        self.root.after(0, lambda s=value: self.status_var.set(f"変換中... {s}"))
                        continue
                    if key in PROGRESS_KEYS:
                        continue
                self._append_from_worker(line + "\n")
            code = process.wait()
            if code != 0:
                raise VideoToolError(f"FFmpeg が失敗しました (exit code {code})")
        finally:
            self._register_process(None)

    def _register_process(self, process: subprocess.Popen[str] | None) -> None:
        self.process = process

    def _append_from_worker(self, text: str) -> None:
        self.root.after(0, lambda t=text: self._append_log(t))

    def _update_progress_from_microseconds(self, raw_value: str) -> None:
        if not self.duration_seconds or self.duration_seconds <= 0:
            return
        try:
            elapsed = int(raw_value) / 1_000_000.0
        except ValueError:
            return
        percent = max(0.0, min(100.0, elapsed / self.duration_seconds * 100.0))
        self.root.after(0, lambda p=percent: self.progress_var.set(p))

    def _cancel(self) -> None:
        self.running = False
        proc = self.process
        self.status_var.set("キャンセル中...")
        self._append_log("\nキャンセル要求を送信しました。\n")
        if proc is not None:
            try:
                proc.terminate()
            except OSError:
                pass
        self._set_running(False)
        self.status_var.set("キャンセルしました")

    def _set_running(self, running: bool) -> None:
        self.running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno("終了", "処理中です。停止して終了しますか？"):
                return
            self._cancel()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    VideoTransformApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
