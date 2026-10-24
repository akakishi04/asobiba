from __future__ import annotations

import tempfile
import tkinter as tk
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from video_split import (
    VIDEO_EXTENSIONS,
    build_copy_cut_command,
    build_copy_segment_command,
    parse_cut_ranges,
    parse_timecode,
    validate_prefix,
)
from video_tool import VideoToolError, find_executable, probe_media


def open_split_dialog(app) -> None:
    """Keep stream-copy operations separate from rotate/resize/AI settings."""
    if app.running:
        return
    source = Path(app.input.get().strip()).expanduser()
    if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
        messagebox.showerror("動画分割", "対応する入力動画を先に選択してください。")
        return

    try:
        info = probe_media(source)
    except (VideoToolError, OSError) as exc:
        messagebox.showerror("動画分割", str(exc))
        return

    w = tk.Toplevel(app.root)
    w.title("無再エンコード カット・分割")
    w.geometry("700x480")
    w.minsize(610, 430)
    w.transient(app.root)
    w.grab_set()

    form = ttk.Frame(w, padding=16)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="入力動画").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Label(form, text=source.name).grid(
        row=0, column=1, columnspan=2, sticky="w", pady=4
    )

    duration = info.duration_seconds
    length = f"{duration:.2f}秒" if duration and duration > 0 else "長さ不明"
    ttk.Label(
        form,
        text=f"{info.codec} / {length} / 元のコンテナ: {source.suffix.lower()}",
        foreground="#555",
    ).grid(row=1, column=1, columnspan=2, sticky="w")

    output_dir = tk.StringVar(value=str(source.parent / (source.stem + "_splits")))
    prefix = tk.StringVar(value=source.stem)
    mode = tk.StringVar(value="ranges")
    interval = tk.StringVar(value="60")

    ttk.Label(form, text="出力フォルダ").grid(row=2, column=0, sticky="w", pady=8)
    ttk.Entry(form, textvariable=output_dir).grid(
        row=2, column=1, sticky="ew", padx=(8, 8), pady=8
    )

    def browse_folder():
        chosen = filedialog.askdirectory(
            title="出力フォルダ", initialdir=str(source.parent), parent=w
        )
        if chosen:
            output_dir.set(chosen)

    ttk.Button(form, text="参照...", command=browse_folder).grid(
        row=2, column=2, pady=8
    )
    ttk.Label(form, text="ファイル名の先頭").grid(
        row=3, column=0, sticky="w", pady=4
    )
    ttk.Entry(form, textvariable=prefix).grid(
        row=3, column=1, sticky="ew", padx=(8, 8), pady=4
    )

    choices = ttk.Frame(form)
    choices.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 4))
    ttk.Radiobutton(
        choices, text="指定範囲を切り出し（複数可）",
        variable=mode, value="ranges",
    ).pack(side="left")
    ttk.Radiobutton(
        choices, text="一定間隔で自動分割",
        variable=mode, value="auto",
    ).pack(side="left", padx=(22, 0))

    manual = ttk.Frame(form)
    manual.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=8)
    manual.columnconfigure(0, weight=1)
    ttk.Label(manual, text="各行に「開始 - 終了」を入力（秒 / 分:秒 / 時:分:秒）").grid(
        row=0, column=0, sticky="w", pady=(0, 5)
    )
    ranges_entry = tk.Text(manual, height=5, wrap="none")
    ranges_entry.grid(row=1, column=0, sticky="nsew")
    example_end = min(duration, 30) if duration and duration > 0 else 30
    ranges_entry.insert("1.0", f"00:00:00 - {example_end:.3f}\n")

    automatic = ttk.Frame(form)
    automatic.grid(row=6, column=0, columnspan=3, sticky="w", pady=8)
    ttk.Label(automatic, text="分割間隔").pack(side="left")
    ttk.Entry(automatic, textvariable=interval, width=12).pack(
        side="left", padx=(8, 8)
    )
    ttk.Label(automatic, text="秒（例: 30、60、120、00:01:00）").pack(side="left")

    def refresh():
        if mode.get() == "ranges":
            manual.grid()
            automatic.grid_remove()
        else:
            manual.grid_remove()
            automatic.grid()

    mode.trace_add("write", lambda *_: refresh())
    refresh()

    ttk.Label(
        form,
        text=(
            "映像・音声・字幕はストリームコピーします。回転・解像度変更・AI処理は適用しません。\n"
            "再エンコードしないため、切断位置はキーフレームにより前後することがあります。\n"
            "既存の分割ファイルは上書きせず、キャンセル時の未完成出力は破棄します。"
        ),
        foreground="#555",
        justify="left",
    ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 12))

    def perform_split(
        folder: Path,
        name: str,
        cuts: list | None,
        seconds: Decimal | None,
        ffmpeg: str,
    ) -> None:
        try:
            folder.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".video_split_", dir=str(folder)
            ) as temporary:
                staging = Path(temporary)
                extension = source.suffix.lower()
                if cuts is not None:
                    generated = []
                    count = len(cuts)
                    for index, cut in enumerate(cuts, 1):
                        staged = staging / f"{name}_cut_{index:03d}{extension}"
                        app._stage(
                            5 + int(85 * (index - 1) / count),
                            f"無再エンコード切り出し {index}/{count}",
                        )
                        app._run(
                            build_copy_cut_command(source, staged, cut, ffmpeg),
                            f"Stream copy {index}/{count}",
                        )
                        generated.append(staged)
                else:
                    app._stage(5, "無再エンコード自動分割中...")
                    pattern = staging / f"{name}_part_%03d{extension}"
                    app._run(
                        build_copy_segment_command(source, pattern, seconds, ffmpeg),
                        "Stream copy segmentation",
                    )
                    generated = sorted(
                        path for path in staging.iterdir() if path.is_file()
                    )

                if app.cancelled:
                    raise VideoToolError("分割はキャンセルされました。")
                if not generated:
                    raise VideoToolError("分割結果がありません。元動画を確認してください。")

                final_paths = [folder / item.name for item in generated]
                if any(path.exists() for path in final_paths):
                    raise VideoToolError("同名の出力動画が既にあります。上書きしません。")

                moved = []
                try:
                    for staged, final in zip(generated, final_paths):
                        if app.cancelled:
                            raise VideoToolError("分割はキャンセルされました。")
                        if final.exists():
                            raise VideoToolError(f"出力ファイルが既に存在します: {final}")
                        staged.rename(final)
                        moved.append(final)
                except Exception:
                    for path in moved:
                        path.unlink(missing_ok=True)
                    raise

            app._log_async(
                f"\n再エンコードなしで {len(final_paths)} 本を書き出しました: {folder}\n"
            )
            app._done(folder)
        except Exception as exc:
            if app.cancelled:
                app._cancelled()
            else:
                app._failed(exc)
        finally:
            app._idle()

    def start_split():
        if app.running:
            return
        try:
            directory_string = output_dir.get().strip()
            if not directory_string:
                raise VideoToolError("出力フォルダを指定してください。")
            folder = Path(directory_string).expanduser()
            if folder.exists() and not folder.is_dir():
                raise VideoToolError("指定先はフォルダではありません。")
            if not folder.exists() and not folder.parent.is_dir():
                raise VideoToolError("出力フォルダの親フォルダが存在しません。")
            name = validate_prefix(prefix.get())
            ffmpeg = find_executable("ffmpeg")
            extension = source.suffix.lower()

            cuts, seconds = None, None
            if mode.get() == "ranges":
                cuts = parse_cut_ranges(ranges_entry.get("1.0", "end"), duration)
                names = [
                    folder / f"{name}_cut_{i:03d}{extension}"
                    for i in range(1, len(cuts) + 1)
                ]
                if any(path.exists() for path in names):
                    raise VideoToolError("同名の切り出し動画が既にあります。")
            else:
                seconds = parse_timecode(interval.get())
                if seconds <= 0:
                    raise VideoToolError("分割間隔は0より大きくしてください。")
                if folder.exists() and any(
                    p.is_file()
                    and p.name.startswith(f"{name}_part_")
                    and p.suffix.lower() == extension
                    for p in folder.iterdir()
                ):
                    raise VideoToolError("同名の自動分割ファイルが既にあります。")

        except (VideoToolError, OSError) as exc:
            messagebox.showerror("分割設定エラー", str(exc), parent=w)
            return

        w.destroy()
        app._launch(perform_split, folder, name, cuts, seconds, ffmpeg)

    buttons = ttk.Frame(form)
    buttons.grid(row=8, column=0, columnspan=3, sticky="e")
    ttk.Button(buttons, text="キャンセル", command=w.destroy).pack(side="right")
    ttk.Button(buttons, text="分割開始", command=start_split).pack(
        side="right", padx=(0, 8)
    )
