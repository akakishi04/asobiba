from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from video_tool import VideoToolError


SEEDVR2_REPO_URL = "https://github.com/comfyorg/comfyui_seedvr2.git"
# Pin the standalone CLI revision used by ai_backends.py so upstream changes do not
# silently break a previously working installation.
SEEDVR2_REVISION = "6d50cf04803aa6d27300ccf2724d5471d366eb12"
VSRVRT_VERSION = "1.1.3"

# vsrvrt's published wheels are built/tested against PyTorch 2.7.1 + cu128.
# Keep that exact torch ABI rather than silently upgrading to a newer release.
RVRT_TORCH_PACKAGES = ("torch==2.7.1", "torchvision")
RVRT_TORCH_INDEX = "https://download.pytorch.org/whl/cu128"
SEEDVR2_TORCH_PACKAGES = (
    "torch==2.6.0",
    "torchvision==0.21.0",
    "torchaudio==2.6.0",
)
SEEDVR2_TORCH_INDEX = "https://download.pytorch.org/whl/cu126"

RunCommand = Callable[[list[str], str, Optional[Path]], None]
LogLine = Callable[[str], None]


@dataclass(frozen=True)
class AISetupPaths:
    base: Path
    engines: Path
    seedvr2_repo: Path
    rvrt_venv: Path
    seedvr2_venv: Path

    @classmethod
    def for_base(cls, base: str | Path) -> "AISetupPaths":
        root = Path(base).resolve()
        return cls(
            base=root,
            engines=root / "ai_engines",
            seedvr2_repo=root / "ai_engines" / "SeedVR2",
            rvrt_venv=root / ".venv-rvrt",
            seedvr2_venv=root / ".venv-seedvr2",
        )

    @staticmethod
    def venv_python(venv: Path) -> Path:
        if os.name == "nt":
            return venv / "Scripts" / "python.exe"
        return venv / "bin" / "python"

    @property
    def rvrt_python(self) -> Path:
        return self.venv_python(self.rvrt_venv)

    @property
    def seedvr2_python(self) -> Path:
        return self.venv_python(self.seedvr2_venv)


@dataclass(frozen=True)
class AISetupResult:
    rvrt_python: Path
    seedvr2_repo: Path
    seedvr2_python: Path


def _python_from_probe(command: list[str]) -> Optional[Path]:
    try:
        result = subprocess.run(
            command + ["-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    raw = result.stdout.strip().splitlines()
    if not raw:
        return None
    candidate = Path(raw[-1].strip())
    return candidate if candidate.is_file() else None


def find_python312() -> Optional[Path]:
    """Find a Python 3.12 interpreter suitable for the managed AI venvs."""
    if sys.version_info[:2] == (3, 12):
        current = Path(sys.executable)
        if current.is_file():
            return current

    py = shutil.which("py")
    if py:
        found = _python_from_probe([py, "-3.12"])
        if found:
            return found

    direct = shutil.which("python3.12")
    if direct:
        found = _python_from_probe([direct])
        if found:
            return found

    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Python" / "Python312" / "python.exe")
    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(Path(program_files) / "Python312" / "python.exe")
    candidates.append(Path("C:/Python312/python.exe"))

    for candidate in candidates:
        if candidate.is_file():
            found = _python_from_probe([str(candidate)])
            if found:
                return found
    return None


def _default_run(command: list[str], label: str, cwd: Optional[Path]) -> None:
    print(f"\n[{label}]\n{subprocess.list2cmdline(command)}", flush=True)
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
    if result.returncode:
        raise VideoToolError(f"{label} failed (code {result.returncode})")


def _ensure_python312(run: RunCommand, log: LogLine) -> Path:
    found = find_python312()
    if found:
        log(f"Python 3.12: {found}")
        return found

    if os.name != "nt":
        raise VideoToolError(
            "Python 3.12 が見つかりません。Python 3.12をインストールしてから再実行してください。"
        )

    winget = shutil.which("winget")
    if not winget:
        raise VideoToolError(
            "Python 3.12 が見つからず、winget も利用できません。Python 3.12 x64をインストールしてください。"
        )

    log("Python 3.12 がないため winget でユーザー領域へインストールします。")
    run(
        [
            winget,
            "install",
            "--id",
            "Python.Python.3.12",
            "--exact",
            "--scope",
            "user",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        "Install Python 3.12",
        None,
    )
    found = find_python312()
    if not found:
        raise VideoToolError(
            "Python 3.12 のインストール後も実行ファイルを検出できませんでした。Windowsへ再サインイン後に再実行してください。"
        )
    log(f"Python 3.12: {found}")
    return found


def _ensure_venv(
    base_python: Path,
    venv: Path,
    run: RunCommand,
    label: str,
) -> Path:
    python = AISetupPaths.venv_python(venv)
    if not python.is_file():
        run([str(base_python), "-m", "venv", str(venv)], f"Create {label} venv", None)
    if not python.is_file():
        raise VideoToolError(f"{label} の仮想環境を作成できませんでした: {venv}")
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
        ],
        f"Update {label} pip",
        None,
    )
    return python


def _ensure_seedvr2_repo(paths: AISetupPaths, run: RunCommand, log: LogLine) -> None:
    git = shutil.which("git")
    if not git:
        raise VideoToolError("git が見つかりません。Git for Windowsをインストールしてください。")

    repo = paths.seedvr2_repo
    if not (repo / ".git").is_dir():
        if repo.exists() and any(repo.iterdir()):
            raise VideoToolError(
                f"SeedVR2の管理先が空ではありません: {repo}\nフォルダを退避または削除して再実行してください。"
            )
        repo.parent.mkdir(parents=True, exist_ok=True)
        run(
            [git, "clone", SEEDVR2_REPO_URL, str(repo)],
            "Clone SeedVR2",
            paths.engines,
        )
    else:
        run(
            [git, "-C", str(repo), "fetch", "origin"],
            "Update SeedVR2 refs",
            paths.base,
        )

    # Use a known-compatible standalone CLI revision. This folder is managed and
    # git-ignored by asobiba, so detached HEAD here is intentional.
    run(
        [git, "-C", str(repo), "checkout", "--detach", SEEDVR2_REVISION],
        "Pin SeedVR2",
        paths.base,
    )
    marker = repo / "inference_cli.py"
    if not marker.is_file():
        raise VideoToolError(f"SeedVR2 inference_cli.py が見つかりません: {marker}")
    log(f"SeedVR2 revision: {SEEDVR2_REVISION[:12]}")


def _install_rvrt(python: Path, run: RunCommand) -> None:
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            *RVRT_TORCH_PACKAGES,
            "--index-url",
            RVRT_TORCH_INDEX,
        ],
        "Install RVRT CUDA PyTorch",
        None,
    )
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            f"vsrvrt=={VSRVRT_VERSION}",
            "Pillow",
        ],
        "Install RVRT backend",
        None,
    )
    run(
        [
            str(python),
            "-c",
            (
                "import torch, vsrvrt; "
                "from vsrvrt._binary import load_deform_attn; "
                "assert torch.cuda.is_available(), 'CUDA is not available in RVRT environment'; "
                "load_deform_attn(); "
                "print('RVRT ready:', torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))"
            ),
        ],
        "Verify RVRT",
        None,
    )


def _install_seedvr2(repo: Path, python: Path, run: RunCommand) -> None:
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            *SEEDVR2_TORCH_PACKAGES,
            "--index-url",
            SEEDVR2_TORCH_INDEX,
        ],
        "Install SeedVR2 CUDA PyTorch",
        repo,
    )
    run(
        [str(python), "-m", "pip", "install", "-r", str(repo / "requirements.txt")],
        "Install SeedVR2 requirements",
        repo,
    )
    run(
        [
            str(python),
            "-c",
            (
                "import torch; "
                "assert torch.cuda.is_available(), 'CUDA is not available in SeedVR2 environment'; "
                "print('SeedVR2 CUDA ready:', torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0))"
            ),
        ],
        "Verify SeedVR2 CUDA",
        repo,
    )
    run(
        [str(python), str(repo / "inference_cli.py"), "--help"],
        "Verify SeedVR2 CLI",
        repo,
    )


def setup_ai_environment(
    base: str | Path,
    *,
    run: RunCommand = _default_run,
    log: LogLine = print,
) -> AISetupResult:
    """Install/update both managed AI backends without tracking them in Git."""
    paths = AISetupPaths.for_base(base)
    paths.engines.mkdir(parents=True, exist_ok=True)

    base_python = _ensure_python312(run, log)
    _ensure_seedvr2_repo(paths, run, log)

    rvrt_python = _ensure_venv(base_python, paths.rvrt_venv, run, "RVRT")
    seed_python = _ensure_venv(base_python, paths.seedvr2_venv, run, "SeedVR2")

    _install_rvrt(rvrt_python, run)
    _install_seedvr2(paths.seedvr2_repo, seed_python, run)

    log("AI環境セットアップ完了。モデル重みは各エンジンの初回使用時に自動取得されます。")
    return AISetupResult(
        rvrt_python=rvrt_python,
        seedvr2_repo=paths.seedvr2_repo,
        seedvr2_python=seed_python,
    )


def main() -> None:
    base = Path(__file__).resolve().parent
    result = setup_ai_environment(base)

    # Keep command-line setup useful too: persist the generated paths just like the GUI.
    from ai_backends import AIConfig

    config_path = base / "ai_config.json"
    try:
        config = AIConfig.load(config_path)
    except VideoToolError:
        config = AIConfig()
    config.rvrt_python = str(result.rvrt_python)
    config.rvrt_repo = ""
    config.seedvr2_repo = str(result.seedvr2_repo)
    config.seedvr2_python = str(result.seedvr2_python)
    config.save(config_path)
    print(f"設定保存: {config_path}")


if __name__ == "__main__":
    main()
