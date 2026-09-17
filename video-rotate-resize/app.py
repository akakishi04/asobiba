from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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
        self.root.title("Video Rotate & Resize")
        self.root.geometry("760x590")
        self.root.minsize(700, 540)

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
        self.status_var = tk.StringVar(value="待機中")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(8, weight=1)

        ttk.Label(outer, text="入力動画").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.input_var).grid(
            row=0, column=1, sticky="ew", padx=(8, 8), pady=4
        )
        ttk.Button(outer, text="参照...", command=self._choose_input).grid(
            row=0, column=2, pady=4
        )

        ttk.Label(outer, textvariable=self.info_var, foreground="#555555").grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(0, 10)
        )

        ttk.Label(outer, text="出力先").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.output_var).grid(
            row=2, column=1, sticky="ew", padx=(8, 8), pady=4
        )
        ttk.Button(outer, text="参照...", command=self._choose_output).grid(
            row=2, column=2, pady=4
        )

        settings = ttk.LabelFrame(outer, text="変換設定", padding=12)
        settings.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="回転").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            settings,
            textvariable=self.rotation_var,
            values=list(ROTATION_CHOICES),
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(settings, text="解像度").grid(row=1, column=0, sticky="w", pady=4)
        resolution_box = ttk.Combobox(
            settings,
            textvariable=self.resolution_var,
            values=list(RESOLUTION_CHOICES),
            state="readonly",
        )
        resolution_box.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=4)
        resolution_box.bind("<<ComboboxSelected>>", lambda _event: self._update_custom_state())

        custom_frame = ttk.Frame(settings)
        custom_frame.grid(row=2, column=1, sticky="w", padx=(12, 0), pady=4)
        self.custom_width_entry = ttk.Entry(custom_frame, width=8, textvariable=self.custom_width_var)
        self.custom_width_entry.pack(side="left")
        ttk.Label(custom_frame, text=" × ").pack(side="left")
        self.custom_height_entry = ttk.Entry(custom_frame, width=8, textvariable=self.custom_height_var)
        self.custom_height_entry.pack(side="left")
        ttk.Label(custom_frame, text=" px").pack(side="left")

        ttk.Label(settings, text="エンコーダー").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            settings,
            textvariable=self.encoder_var,
            values=["自動（NVENC優先）", "NVIDIA NVENC", "CPU (libx264)"],
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=4)

        ttk.Label(
            settings,
            text="解像度変更時はアスペクト比を維持し、必要なら黒帯で指定サイズに合わせます。",
            foreground="#555555",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self._update_custom_state()

        self.progress = ttk.Progressbar(
            outer, variable=self.progress_var, maximum=100.0, mode="determinate"
        )
        self.progress.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        ttk.Label(outer, textvariable=self.status_var).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        button_frame = ttk.Frame(outer)
        button_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        self.start_button = ttk.Button(button_frame, text="変換開始", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(
            button_frame, text="キャンセル", command=self._cancel, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="ログ").grid(row=7, column=0, columnspan=3, sticky="w")
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def _update_custom_state(self) -> None:
        state = "normal" if self.resolution_var.get() == "カスタム" else "disabled"
        self.custom_width_entry.configure(state=state)
        self.custom_height_entry.configure(state=state)

    def _choose_input(self) -> None:
        path = filedialog.askopenfilename(
            title="入力動画を選択",
            filetypes=[
                ("動画ファイル", "*.mp4 *.mov *.mkv *.m4v *.avi *.webm"),
                ("すべてのファイル", "*.*"),
            ],
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
            duration_text = (
                self._format_duration(info.duration_seconds)
                if info.duration_seconds is not None
                else "長さ不明"
            )
            rotation_text = f" / 回転情報 {info.rotation}°" if info.rotation else ""
            text = (
                f"{info.width}×{info.height} / {info.codec} / {fps_text} / "
                f"{duration_text}{rotation_text}"
            )
            self.root.after(0, lambda: self.info_var.set(text))
        except Exception as exc:
            self.duration_seconds = None
            self.root.after(0, lambda: self.info_var.set(f"解析失敗: {exc}"))

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(round(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

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
            if not destination.name:
                raise VideoToolError("出力先を指定してください。")
            if destination.suffix.lower() != ".mp4":
                raise VideoToolError("現在の出力形式は MP4 のみです。")
            if not destination.parent.exists():
                raise VideoToolError("出力先フォルダが存在しません。")

            rotation = ROTATION_CHOICES[self.rotation_var.get()]
            target = self._target_resolution()
            if rotation == "none" and target is None:
                raise VideoToolError("回転または解像度変更を指定してください。")

            ffmpeg_bin = find_executable("ffmpeg")
            find_executable("ffprobe")
            encoder = self._selected_encoder(ffmpeg_bin)
            command = build_ffmpeg_command(
                source,
                destination,
                rotation=rotation,
                target=target,
                encoder=encoder,
                ffmpeg=ffmpeg_bin,
            )
        except VideoToolError as exc:
            messagebox.showerror("設定エラー", str(exc))
            return

        self._set_running(True)
        self.progress_var.set(0.0)
        self._append_log("\n--- 変換開始 ---\n")
        self._append_log(f"Encoder: {encoder}\n")
        self._append_log(f"Command: {subprocess.list2cmdline(command)}\n\n")
        threading.Thread(
            target=self._conversion_worker,
            args=(command, destination),
            daemon=True,
        ).start()

    def _conversion_worker(self, command: list[str], destination: Path) -> None:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )

            assert self.process.stdout is not None
            speed = ""
            for raw_line in self.process.stdout:
                line = raw_line.strip()
                if not line:
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    if key in {"out_time_us", "out_time_ms"}:
                        self._update_progress_from_microseconds(value)
                        continue
                    if key == "speed":
                        speed = value
                        self.root.after(0, lambda s=speed: self.status_var.set(f"変換中... {s}"))
                        continue
                    if key in PROGRESS_KEYS:
                        continue

                self.root.after(0, lambda text=line: self._append_log(text + "\n"))

            return_code = self.process.wait()
            if return_code == 0:
                self.root.after(0, lambda: self.progress_var.set(100.0))
                self.root.after(0, lambda: self.status_var.set("完了"))
                self.root.after(0, lambda: self._append_log(f"\n完了: {destination}\n"))
                self.root.after(
                    0,
                    lambda: messagebox.showinfo("変換完了", f"保存しました:\n{destination}"),
                )
            elif self.running:
                self.root.after(0, lambda: self.status_var.set(f"失敗 (code {return_code})"))
                self.root.after(0, lambda: self._append_log(f"\nFFmpeg failed: {return_code}\n"))
        except Exception as exc:
            self.root.after(0, lambda: self.status_var.set("エラー"))
            self.root.after(0, lambda: self._append_log(f"\nエラー: {exc}\n"))
            self.root.after(0, lambda: messagebox.showerror("変換エラー", str(exc)))
        finally:
            self.process = None
            self.root.after(0, lambda: self._set_running(False))

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
        proc = self.process
        if proc is None:
            return
        self.status_var.set("キャンセル中...")
        self._append_log("\nキャンセル要求を送信しました。\n")
        try:
            proc.terminate()
        except OSError:
            pass

    def _set_running(self, running: bool) -> None:
        self.running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        if not running and self.status_var.get() == "キャンセル中...":
            self.status_var.set("キャンセルしました")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno("終了", "変換中です。処理を停止して終了しますか？"):
                return
            try:
                self.process.terminate()
            except OSError:
                pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = VideoTransformApp(root)
    root.mainloop()
    del app


if __name__ == "__main__":
    main()
