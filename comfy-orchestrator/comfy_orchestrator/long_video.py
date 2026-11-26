"""Sequential H3 continuation, durable segment checkpoints and CPU video joining."""
from __future__ import annotations

import json
import math
import secrets
import shutil
import subprocess
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

from . import core
from .jobs import JobCancellationRequested, JobExecutionFailed

LONG_VIDEO_ID = "minimax_h3_long_video"
LONG_TARGETS = {"単発": 0, "30秒": 30, "1分": 60, "2分": 120, "3分": 180, "5分": 300}
FPS = 24


class LongVideoPaused(core.OrchestratorError):
    pass


def check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise LongVideoPaused("長尺生成を中断しました。保存済みの区間から再開できます")


def segment_plan(seconds: int, maximum_frames: int) -> list[int]:
    if seconds not in LONG_TARGETS.values() or seconds == 0:
        raise core.OrchestratorError("合計尺は30秒～5分のプリセットから選択してください")
    if type(maximum_frames) is not int or not 107 <= maximum_frames <= 362 or (maximum_frames - 5) % 17:
        raise core.OrchestratorError("H3の区間フレーム数が不正です")
    remaining = seconds * FPS
    plan = []
    while remaining > 0:
        overlap = int(bool(plan))
        # Shorten the final request on the legal 17k+5 grid, trimming only
        # the remaining excess during concatenation.
        wanted = min(maximum_frames, remaining + overlap)
        frames = max(107, 5 + 17 * math.ceil((wanted - 5) / 17))
        plan.append(frames)
        remaining -= frames - overlap
    return plan


def continuation_model(model: str) -> str:
    if core.h3_ref2va_filename(model) is None:
        return model
    filename = core.h3_hybrid_filename(model)
    if filename is None:
        raise core.OrchestratorError("長尺連続生成には開始フレーム対応モデルが必要です。純粋Ref2VAではなくHybridまたはFL2VAを選択してください")
    key = core.h3_hybrid_model_key(filename, reference_only=False)
    if key is None:
        raise core.OrchestratorError("Hybridの開始フレームモードを確認できません")
    return key


def continuation_parameters(first: dict, index: int, frames: int) -> dict:
    p = dict(first)
    model = p.get("h3_model")
    if model is not None:
        p["h3_model"] = continuation_model(model)
    prompt = p["positive_prompt"]
    if prompt == core.H3_REF2VA_DEFAULT_PROMPT:
        prompt = core.I2V_DEFAULT_PROMPT
    prefix = "Use <Picture 1> as a visual reference, not as the first frame. "
    if prompt.startswith(prefix):
        prompt = prompt[len(prefix):]
    p.update(frames=frames, seed=(int(first["seed"]) + index) % (2 ** 64),
             positive_prompt="Continue the same shot directly from this supplied opening frame. "
                             "Maintain the subject, setting, camera and motion continuity without a cut. " + prompt)
    core.check_param("seed", p["seed"])
    core.check_param("positive_prompt", p["positive_prompt"])
    return p


class FFmpeg:
    """No GPU encoding, no all-video frame buffer, no shell interpolation."""
    def __init__(self):
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")
        if not self.ffmpeg or not self.ffprobe:
            raise core.OrchestratorError("長尺生成にはFFmpegとFFprobeが必要です。FFmpegをPATHに追加してください")

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
                    raise core.OrchestratorError("FFmpeg処理がタイムアウトしました")
                try:
                    out, err = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise core.OrchestratorError("FFmpeg処理失敗: " + err.decode("utf-8", errors="replace")[-1800:])
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
            raise core.OrchestratorError(f"動画ストリームがありません: {path.name}")
        try:
            return {"frames": int(video["nb_read_frames"]), "width": int(video["width"]),
                    "height": int(video["height"]), "fps": float(Fraction(video["avg_frame_rate"])),
                    "audio": any(s.get("codec_type") == "audio" for s in streams)}
        except (KeyError, ValueError, ZeroDivisionError) as exc:
            raise core.OrchestratorError("動画のフレーム情報を取得できません") from exc

    def last_frame(self, clip: Path, frames: int, target: Path, cancel_event=None):
        temporary = target.with_name(target.stem + ".part.png")
        try:
            self._run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                       "-threads", "2", "-i", clip, "-vf", f"select=eq(n\\,{frames - 1})",
                       "-frames:v", "1", "-threads", "2", temporary], cancel_event)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise core.OrchestratorError("最終フレームを取得できません")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    def join(self, clips: list[tuple[Path, dict]], target_frames: int, output: Path, cancel_event=None, progress=None):
        """Remove repeated anchors, preserve video/audio timing, trim to exact length.

        Encode one short part at a time into matching H.264 + PCM tracks.
        Final concatenation copies video and encodes AAC only once.
        """
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
                    skip = int(i > 0)
                    count = min(remaining, info["frames"] - skip)
                    if count <= 0:
                        raise core.OrchestratorError("結合区間に有効なフレームがありません")
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
                    raise core.OrchestratorError("結合するフレームが不足しています")
                (work / "parts.ffconcat").write_text("\n".join(listing) + "\n", encoding="ascii")
                self._run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                           "-f", "concat", "-safe", "1", "-i", work / "parts.ffconcat",
                           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", temporary], cancel_event, timeout=1800)
            info = self.probe(temporary, cancel_event)
            if info["frames"] != target_frames or abs(info["fps"] - FPS) > 0.05 or not info["audio"]:
                raise core.OrchestratorError(f"結合結果の検証に失敗しました: {info}")
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)


class LongVideoStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, run_id: str) -> Path:
        try:
            if str(uuid.UUID(run_id)) != run_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError) as exc:
            raise core.OrchestratorError("長尺IDが不正です") from exc
        return self.root / run_id

    def save(self, manifest: dict):
        folder = self.folder(manifest["run_id"])
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
            temporary.replace(folder / "manifest.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def create(self, backend: str, request: str, source: Path, overrides: dict,
               seconds: int, profile=None) -> dict:
        p = dict(overrides)
        core.validate_h3_video_parameters(p)
        model = p.get("h3_model")
        if model is not None:
            continuation_model(model)
        plan = segment_plan(seconds, p["frames"])
        p.setdefault("seed", secrets.randbits(32))
        source = Path(source)
        if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise core.OrchestratorError("長尺生成の参照画像がありません")
        if source.stat().st_size > 40 * 1024 * 1024:
            raise core.OrchestratorError("参照画像は40MB以下にしてください")
        run_id = str(uuid.uuid4())
        folder = self.folder(run_id)
        folder.mkdir()
        try:
            name = "source" + source.suffix.lower()
            shutil.copyfile(source, folder / name)
            manifest = {"schema": 1, "run_id": run_id, "backend": backend.rstrip("/"),
                        "request": request, "profile": profile, "source": name,
                        "overrides": p, "seconds": seconds, "plan": plan,
                        "first_parameters": None, "segments": [], "state": "generating"}
            self.save(manifest)
            return manifest
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def load(self, path: Path) -> dict:
        path = Path(path).resolve()
        if path.name != "manifest.json" or path.parent.parent != self.root:
            raise core.OrchestratorError("このアプリの長尺manifest.jsonを選択してください")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or self.folder(manifest["run_id"]) != path.parent:
            raise core.OrchestratorError("長尺記録が不正です")
        if manifest["plan"] != segment_plan(manifest["seconds"], manifest["overrides"]["frames"]):
            raise core.OrchestratorError("長尺計画が不正です")
        return manifest

    def asset(self, manifest, name) -> Path:
        folder = self.folder(manifest["run_id"])
        path = (folder / name).resolve()
        if not path.is_relative_to(folder):
            raise core.OrchestratorError("長尺記録のパスが不正です")
        return path


def series_records(journal, run_id, index, backend):
    """Correlate durable job records even if the app died between submit/save."""
    records = []
    for path in journal.root.glob("*/record.json"):
        record = journal.read(path.parent.name)
        ctx = record.get("context", {})
        if (record["backend"] == backend.rstrip("/") and ctx.get("long_run_id") == run_id
                and ctx.get("long_segment") == index and record["state"] != "failed"):
            records.append(record)
    return sorted(records, key=lambda r: r["created_at"], reverse=True)


def existing_result(journal, comfy, manifest, index, cancel_event):
    matches = series_records(journal, manifest["run_id"], index, comfy.base)
    if not matches:
        return None
    record = matches[0]
    if record["state"] in ("completed", "collected") and isinstance(record.get("outputs"), dict):
        info = {"outputs": record["outputs"], "status": record.get("comfy_status", {})}
        state = "completed"
    else:
        state, info = journal.inspect(comfy, record)
    if state in ("pending", "running"):
        try:
            info = comfy.wait(record["prompt_id"], cancel_event=cancel_event, cancel_remote=True)
        except JobCancellationRequested:
            journal.update(record["job_id"], state="cancel_requested")
            raise
        except JobExecutionFailed:
            journal.update(record["job_id"], state="failed")
            raise
        journal.update(record["job_id"], state="completed", outputs=info.get("outputs", {}),
                       comfy_status=info.get("status", {}))
    elif state == "failed":
        return None
    elif state == "unknown":
        if record["state"] == "cancel_requested":
            # The user explicitly resumed after a targeted cancel, and the
            # server has no running/pending job for this ID.
            journal.update(record["job_id"], state="failed", error="cancelled; no active job")
            return None
        raise core.OrchestratorError("前回ジョブの状態が不明です。重複生成を防ぐため再投入しません: " + record["prompt_id"])
    return {"job_id": record["job_id"], "prompt_id": record["prompt_id"],
            "parameters": record["parameters"], "outputs": info.get("outputs", {})}


def run_long_video(store, manifest, config, config_path, journal, output_dir,
                   download, progress=None, cancel_event=None, prompt_cache=None, media=None):
    """Run or resume exactly one sequential series; no LLM between segments."""
    media = media or FFmpeg()
    backend = config["comfyui"]["base_url"].rstrip("/")
    if manifest["backend"] != backend:
        raise core.OrchestratorError("長尺生成の接続先が保存時と異なります")
    p = manifest["overrides"]
    core.validate_h3_video_parameters(p)
    if p.get("h3_model") is not None:
        continuation_model(p["h3_model"])
    plan = segment_plan(manifest["seconds"], p["frames"])
    if manifest["plan"] != plan or len(manifest["segments"]) > len(plan):
        raise core.OrchestratorError("長尺計画が不正です")
    folder = store.folder(manifest["run_id"])
    source = store.asset(manifest, manifest["source"])
    if not source.is_file():
        raise core.OrchestratorError("長尺生成の元画像がありません")
    comfy = core.ComfyUI(config["comfyui"])
    # Resume may wait for a job that was already submitted in a past process.
    comfy.extend_video_timeout(config["comfyui"])
    clips = []
    for i, segment in enumerate(manifest["segments"]):
        check_cancel(cancel_event)
        clip = store.asset(manifest, segment["file"])
        info = media.probe(clip, cancel_event)
        _check_segment(info, p, plan[i])
        clips.append((clip, info))
    for i in range(len(clips), len(plan)):
        check_cancel(cancel_event)
        if progress:
            progress(f"長尺生成 {i + 1}/{len(plan)}")
        result = existing_result(journal, comfy, manifest, i, cancel_event)
        if result is None:
            if i == 0:
                image = source
                overrides = {**p, "frames": plan[i]}
                result = core.execute(
                    config, config_path, manifest["request"], image=image,
                    selected_workflow=core.H3_I2V_ID, overrides=overrides,
                    progress=progress, cancel_event=cancel_event, job_journal=journal,
                    job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                 "prompt_profile": manifest["profile"]},
                    prompt_cache=prompt_cache,
                )
            else:
                anchor = folder / f"anchor_{i:03d}.png"
                media.last_frame(clips[-1][0], clips[-1][1]["frames"], anchor, cancel_event)
                params = continuation_parameters(manifest["first_parameters"], i, plan[i])
                result = core.execute_saved(
                    config, config_path, core.H3_I2V_ID, params, reference_image=anchor,
                    progress=progress, cancel_event=cancel_event, job_journal=journal,
                    job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                 "request_text": manifest["request"], "prompt_profile": manifest["profile"]},
                )
        check_cancel(cancel_event)
        segment_folder = folder / f"segment_{i:03d}"
        segment_folder.mkdir(exist_ok=True)
        clip = Path(download(result, segment_folder)).resolve()
        if not clip.is_relative_to(segment_folder.resolve()):
            raise core.OrchestratorError("長尺区間の保存先が不正です")
        info = media.probe(clip, cancel_event)
        _check_segment(info, p, plan[i])
        if i == 0:
            manifest["first_parameters"] = result["parameters"]
        manifest["segments"].append({"file": clip.relative_to(folder).as_posix(),
                                     "job_id": result["job_id"], "prompt_id": result["prompt_id"],
                                     "parameters": result["parameters"], "frames": info["frames"]})
        store.save(manifest)
        journal.update(result["job_id"], state="collected")
        clips.append((clip, info))
    check_cancel(cancel_event)
    output = Path(output_dir) / f"long_{manifest['run_id']}.mp4"
    if manifest["state"] != "completed" or not output.is_file():
        media.join(clips, manifest["seconds"] * FPS, output, cancel_event, progress)
        manifest["state"] = "completed"
        store.save(manifest)
    first = dict(manifest["first_parameters"])
    first.update(frames=manifest["seconds"] * FPS, long_segment_frames=p["frames"],
                 long_seconds=manifest["seconds"], long_run_id=manifest["run_id"])
    return {"status": "completed", "workflow_id": LONG_VIDEO_ID, "kind": "i2v",
            "parameters": first, "prompt_id": manifest["run_id"], "outputs": {}}, output


def _check_segment(info, p, frames):
    if (info["frames"] != frames or info["width"] != p["width"] or info["height"] != p["height"]
            or abs(info["fps"] - FPS) > 0.01):
        raise core.OrchestratorError(f"H3区間の実測情報が計画と異なります: {info} / {frames}f")
