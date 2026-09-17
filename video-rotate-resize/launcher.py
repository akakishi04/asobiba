from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


# SeedVR2 prints Unicode/emoji during CLI startup. Windows Japanese locales can
# otherwise expose cp932 to piped child processes and fail before inference.
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

BASE = Path(__file__).resolve().parent
LOCAL_DEPS = BASE / ".app_deps"
TKINTERDND_VERSION = "0.6.3"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}


def _install_local_dnd() -> bool:
    """Install tkinterdnd2 into a git-ignored local folder when needed."""
    LOCAL_DEPS.mkdir(parents=True, exist_ok=True)
    local = str(LOCAL_DEPS)
    if local not in sys.path:
        sys.path.insert(0, local)

    try:
        import tkinterdnd2  # noqa: F401
        return True
    except ImportError:
        pass

    print(f"tkinterdnd2 {TKINTERDND_VERSION} をローカルへセットアップします...")
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--upgrade",
        "--target",
        str(LOCAL_DEPS),
        f"tkinterdnd2=={TKINTERDND_VERSION}",
    ]
    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"D&D依存関係を導入できませんでした: {exc}")
        return False
    if result.returncode != 0:
        print("D&D依存関係の導入に失敗しました。通常のファイル選択で起動します。")
        return False

    # pip may have populated a directory that Python has already searched once.
    import importlib

    importlib.invalidate_caches()
    try:
        import tkinterdnd2  # noqa: F401
        return True
    except ImportError:
        print("tkinterdnd2 を読み込めませんでした。通常のファイル選択で起動します。")
        return False


def _enable_drag_and_drop(app_ai) -> bool:
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
    except ImportError:
        return False

    # app_ai.main() creates tk.Tk(). Replace only that constructor; the rest of
    # tkinter/ttk remains untouched.
    app_ai.tk.Tk = TkinterDnD.Tk

    original_init = app_ai.App.__init__
    original_path_row = app_ai.App._path_row

    def set_input_video(self, raw_path: str) -> bool:
        path = Path(raw_path).expanduser()
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            return False

        resolved = path.resolve()
        self.input.set(str(resolved))
        self.output.set(str(resolved.with_name(resolved.stem + "_converted.mp4")))
        self.info.set("解析中...")
        try:
            info = app_ai.probe_media(resolved)
            self.info.set(
                f"{info.width}×{info.height} / {info.codec} / "
                f"{info.fps or 0:.3f} fps / D&D読込"
            )
        except Exception as exc:
            self.info.set(f"解析失敗: {exc}")
        return True

    def on_drop(self, event):
        try:
            paths = [Path(item) for item in self.root.tk.splitlist(event.data)]
        except Exception as exc:
            self.status.set(f"D&D解析失敗: {exc}")
            return

        videos = [
            path
            for path in paths
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
        if not videos:
            self.status.set("D&D: 対応する動画ファイルがありません。")
            return

        set_input_video(self, str(videos[0]))
        if len(videos) > 1:
            self.status.set(
                f"D&D: {len(videos)}本中、先頭の動画を入力に設定しました。"
            )
        else:
            self.status.set("D&D: 動画を入力に設定しました。")

    def path_row_with_dnd(self, parent, row, label, var, command):
        # Keep the existing layout exactly the same, but retain the input Entry
        # so it can be registered as a native Windows drop target.
        if label != "入力動画":
            return original_path_row(self, parent, row, label, var, command)

        app_ai.ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", pady=3
        )
        entry = app_ai.ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=3)
        app_ai.ttk.Button(parent, text="参照...", command=command).grid(
            row=row, column=2, pady=3
        )
        entry.drop_target_register(DND_FILES)
        entry.dnd_bind("<<Drop>>", self._on_drop_video)
        self.input_entry = entry
        return None

    def init_with_dnd(self, root):
        original_init(self, root)
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", self._on_drop_video)
        if self.info.get() == "動画を選択してください。":
            self.info.set("動画を選択するか、このウィンドウへD&Dしてください。")

    app_ai.App._set_input_video = set_input_video
    app_ai.App._on_drop_video = on_drop
    app_ai.App._path_row = path_row_with_dnd
    app_ai.App.__init__ = init_with_dnd
    return True


def main() -> None:
    dnd_ready = _install_local_dnd()

    import app_ai

    if dnd_ready and _enable_drag_and_drop(app_ai):
        print("Drag & Drop: enabled")
    else:
        print("Drag & Drop: unavailable (通常の参照ボタンは利用できます)")

    app_ai.main()


if __name__ == "__main__":
    main()
