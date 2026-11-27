"""FFmpeg/FFprobe adapter for frame extraction and CPU audiovisual joining."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from .parameters import OrchestratorError
from .long_video_plan import FPS, check_cancel


class FFmpeg:
    """No GPU encoding, no all-video frame buffer, no shell interpolation."""
    def __init__(self):
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")
        if not self.ffmpeg or not self.ffprobe:
            raise OrchestratorError("長尺生成にはFFmpegとFFprobeが必要です。FFmpegをPATHに追加してください")

    def _run(self, args, cancel_event=None, timeout=600):
        import time
        check_cancel(cancel_event)
        process = subprocess.Popen(
            [str(v) for v in args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + timeout
        try:
            while True:
                check_cancel(cancel_event)
                if time.monotonic() >= deadline:
                    raise OrchestratorError("FFmpeg処理がタイムアウトしました")
                try:
                    out, err = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise OrchestratorError("FFmpeg処理失敗: " + err.decode("utf-8", errors="replace")[-1800:])
            return out
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()

    def probe(self, path: Path, cancel_event=None) -> dict:
        out = self._run([
            self.ffprobe, "-v", "error", "-count_frames", "-show_entries",
            "stream=codec_type,width,height,avg_frame_rate,nb_read_frames", "-of", "json", path,
        ], cancel_event)
        streams = json.loads(out)["streams"]
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video is None:
            raise OrchestratorError(f"動画ストリームがありません: {path.name}")
        try:
            return {"frames": int(video["nb_read_frames"]), "width": int(video["width"]),
                    "height": int(video["height"]), "fps": float(Fraction(video["avg_frame_rate"])),
                    "audio": any(s.get("codec_type") == "audio" for s in streams)}
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            raise OrchestratorError("動画のフレーム情報を取得できません") from exc

    def last_frame(self, clip: Path, frames: int, target: Path, cancel_event=None):
        self.extract_frame(clip, frames, target, cancel_event)

    def extract_frame(self, clip: Path, frame: int, target: Path, cancel_event=None):
        """Decode an exact one-based frame number, independent of nominal FPS."""
        if type(frame) is not int or frame < 1:
            raise OrchestratorError("フレーム番号は1以上の整数です")
        temporary = target.with_name(target.stem + ".part.png")
        try:
            self._run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                       "-threads", "2", "-i", clip, "-map", "0:v:0", "-vf", f"select=eq(n\\,{frame - 1})",
                       "-frames:v", "1", "-threads", "2", temporary], cancel_event)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise OrchestratorError("指定フレームを取得できません")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def extract_guide_frames(self, clip: Path, start: int, count: int, folder: Path, cancel_event=None):
        """Decode the exact contiguous retained frames in chronological order."""
        from .h3_guide import GUIDE_LENGTHS
        if type(start) is not int or start < 0 or count not in GUIDE_LENGTHS:
            raise OrchestratorError("H3ガイドの切り出し範囲が不正です")
        folder = Path(folder)
        paths = tuple(folder / f"frame_{i:03d}.png" for i in range(count))
        if any(path.exists() for path in paths):
            raise OrchestratorError("H3ガイドの一時保存先が使用済みです")
        self._run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                   "-threads", "2", "-i", clip, "-map", "0:v:0",
                   "-vf", f"select=between(n\\,{start}\\,{start + count - 1})",
                   "-fps_mode", "passthrough", "-frames:v", str(count),
                   "-start_number", "0", "-threads", "2", folder / "frame_%03d.png"], cancel_event)
        if (tuple(sorted(folder.glob("frame_*.png"))) != paths
                or any(not path.is_file() or path.stat().st_size == 0 for path in paths)):
            raise OrchestratorError("H3ガイドに必要な連続フレームを取得できません")
        return paths

    def join(self, clips: list[tuple[Path, dict]], target_frames: int, output: Path, cancel_event=None, progress=None, *,
             keep_frames=None, trim_start_frames=None):
        """Remove repeated anchors, preserve video/audio timing, trim to exact length.

        Encode one short part at a time into matching H.264 + PCM tracks.
        Final concatenation copies video and encodes AAC only once.
        """
        skips = [int(i > 0) for i in range(len(clips))]
        if trim_start_frames is not None:
            if (keep_frames is None or not isinstance(trim_start_frames, list)
                    or len(trim_start_frames) != len(clips)
                    or any(type(n) is not int or n < 0 for n in trim_start_frames)
                    or not trim_start_frames or trim_start_frames[0] != 0):
                raise OrchestratorError("カットごとの助走フレーム数が不正です")
            skips = trim_start_frames
        if keep_frames is not None:
            if (not isinstance(keep_frames, list) or len(keep_frames) != len(clips)
                    or any(type(n) is not int or n <= 0 for n in keep_frames)
                    or sum(keep_frames) != target_frames
                    or any(n + skip > info["frames"]
                           for n, skip, (_, info) in zip(keep_frames, skips, clips))):
                raise OrchestratorError("カットごとの結合フレーム数が不正です")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.stem + ".part.mp4")
        try:
            with tempfile.TemporaryDirectory(prefix="join-", dir=clips[0][0].parent.parent) as folder:
                work = Path(folder)
                listing = ["ffconcat version 1.0"]
                remaining = target_frames
                for i, (clip, info) in enumerate(clips):
                    check_cancel(cancel_event)
                    if remaining <= 0:
                        break
                    skip = skips[i]
                    count = keep_frames[i] if keep_frames is not None else min(remaining, info["frames"] - skip)
                    if count <= 0:
                        raise OrchestratorError("結合区間に有効なフレームがありません")
                    part = f"part_{i:03d}.mkv"
                    if progress:
                        progress(f"長尺結合 {i + 1}/{len(clips)}")
                    args = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                            "-threads", "2", "-i", clip]
                    # Normalize audio to exactly 2000 samples per 24fps frame.
                    if info["audio"]:
                        audio = "0:a:0"
                        af = f"aresample=48000,atrim=start_sample={skip * 2000},asetpts=PTS-STARTPTS"
                    else:
                        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
                        audio = "1:a:0"
                        af = "asetpts=PTS-STARTPTS"
                    af += f",apad=whole_len={count * 2000},atrim=end_sample={count * 2000}"
                    args += ["-map", "0:v:0", "-map", audio,
                             "-vf", f"trim=start_frame={skip}:end_frame={skip + count},setpts=N/(24*TB)",
                             "-af", af, "-filter_threads", "2", "-c:v", "libx264",
                             "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                             "-threads", "4", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
                             work / part]
                    self._run(args, cancel_event)
                    listing += [f"file '{part}'", f"duration {count / FPS:.12f}"]
                    remaining -= count
                if remaining:
                    raise OrchestratorError("結合するフレームが不足しています")
                (work / "parts.ffconcat").write_text("\n".join(listing) + "\n", encoding="ascii")
                self._run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "concat", "-safe", "1", "-i", work / "parts.ffconcat",
                           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", temporary], cancel_event, timeout=1800)
            info = self.probe(temporary, cancel_event)
            if info["frames"] != target_frames or abs(info["fps"] - FPS) > 0.05 or not info["audio"]:
                raise OrchestratorError(f"結合結果の検証に失敗しました: {info}")
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
