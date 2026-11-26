"""Sequential H3 continuation, durable segment checkpoints and CPU video joining."""
from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime, timezone
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid
from fractions import Fraction
from pathlib import Path

from . import core
from .jobs import JobCancellationRequested, JobExecutionFailed, UnknownLongJob
from .timeline import (validate_prompt_plan, prompt_for_segment, validate_cut_frames,
                       generation_frames_for_cuts, segment_windows, validate_overlap_frames,
                       CONTINUATION_OVERLAP_FRAMES)
from .asset_store import save_snapshot
from .timing import report_estimate, ERRORS as TIMING_ERRORS
from .project_lock import lock_project

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


def schedule_windows(seconds, nominal_frames, cut_frames=None, *, overlap_frames=0):
    """Derive output intervals from the legacy schedule, then extend raw clips."""
    overlap_frames = validate_overlap_frames(overlap_frames)
    base = (generation_frames_for_cuts(cut_frames) if cut_frames is not None
            else segment_plan(seconds, nominal_frames))
    windows = segment_windows(base, seconds, cut_frames=cut_frames, overlap_frames=overlap_frames)
    # Always expose the exact trim used by the runtime, even in old records.
    for i, w in enumerate(windows):
        w.setdefault("trim_start_frames", int(i > 0))
    return windows


def manifest_windows(manifest):
    return schedule_windows(manifest["seconds"], manifest["overrides"]["frames"],
                            manifest.get("cut_frames"),
                            overlap_frames=manifest.get("overlap_frames", 0))


def manifest_schedule(manifest: dict) -> tuple[list[int], list[int] | None, int]:
    """Validate both legacy and versioned lead-in schedules."""
    cuts = manifest.get("cut_frames")
    overlap = validate_overlap_frames(manifest.get("overlap_frames", 0))
    if cuts is not None:
        cuts = validate_cut_frames(cuts)
        if manifest["seconds"] != sum(cuts) / FPS or "prompt_plan" not in manifest:
            raise core.OrchestratorError("長尺カット記録が不正です")
    if overlap and "prompt_plan" not in manifest:
        raise core.OrchestratorError("助走付き長尺には区間プロンプト計画が必要です")
    windows = manifest_windows(manifest)
    plan = [w["generation_frames"] for w in windows]
    if manifest["plan"] != plan:
        raise core.OrchestratorError("長尺計画が不正です")
    return plan, cuts, sum(w["output_frames"] for w in windows)


def continuation_anchor_count(previous, current):
    """One-based frame number: lead-in ends exactly at the output boundary."""
    return previous["trim_start_frames"] + previous["output_frames"] - current["trim_start_frames"] + 1


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


def planned_segment_parameters(base: dict, prompt_plan: dict, index: int, frames: int,
                               *, lead_in_frames=0) -> dict:
    """Apply only the approved prompt for this interval, including segment zero."""
    p = dict(base)
    model = p.get("h3_model")
    if index and model is not None:
        p["h3_model"] = continuation_model(model)
    p["frames"] = frames
    # The ordinary parameter validator accepts signed 63-bit nonnegative seeds.
    # Wrap on its actual domain, not an unsigned 64-bit domain.
    p["seed"] = (int(base["seed"]) + index) % (core.PARAMS["seed"][2] + 1)
    p["positive_prompt"] = prompt_for_segment(prompt_plan, index)
    if index and lead_in_frames > 1:
        p["positive_prompt"] = (
            f"Immediately continue the preceding ongoing motion without pausing. "
            f"For the first {lead_in_frames / FPS:.3f} seconds, sustain that motion and the camera trajectory; "
            "then progress into this segment's new action smoothly. "
            "Do not start with a stationary hold or repeat earlier dialogue. "
            + p["positive_prompt"]
        )
        core.check_param("positive_prompt", p["positive_prompt"])
    if index == 0 and core.h3_ref2va_filename(model) is not None:
        p["positive_prompt"] = core.ensure_h3_reference_prompt(p["positive_prompt"])
    core.check_param("seed", p["seed"])
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
                raise core.OrchestratorError("カットごとの助走フレーム数が不正です")
            skips = trim_start_frames
        if keep_frames is not None:
            if (not isinstance(keep_frames, list) or len(keep_frames) != len(clips)
                    or any(type(n) is not int or n <= 0 for n in keep_frames)
                    or sum(keep_frames) != target_frames
                    or any(n + skip > info["frames"]
                           for n, skip, (_, info) in zip(keep_frames, skips, clips))):
                raise core.OrchestratorError("カットごとの結合フレーム数が不正です")
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
               seconds: int | float, profile=None, *, prompt_plan=None, cut_frames=None,
               draft=False, overlap_frames=0) -> dict:
        p = dict(overrides)
        core.validate_h3_video_parameters(p)
        model = p.get("h3_model")
        if model is not None:
            continuation_model(model)
        overlap_frames = validate_overlap_frames(overlap_frames)
        if cut_frames is not None:
            cut_frames = validate_cut_frames(cut_frames)
            if seconds != sum(cut_frames) / FPS or prompt_plan is None:
                raise core.OrchestratorError("カット尺とプロンプト計画が一致しません")
        if overlap_frames and prompt_plan is None:
            raise core.OrchestratorError("助走付き長尺には区間プロンプト計画が必要です")
        windows = schedule_windows(seconds, p["frames"], cut_frames, overlap_frames=overlap_frames)
        plan = [w["generation_frames"] for w in windows]
        if prompt_plan is not None:
            prompt_plan = validate_prompt_plan(prompt_plan, len(plan))
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
            save_snapshot(source, folder / name, self.root.parent / "asset_pool")
            manifest = {"schema": 1, "run_id": run_id, "backend": backend.rstrip("/"),
                        "request": request, "profile": profile, "source": name,
                        "overrides": p, "seconds": seconds, "plan": plan,
                        "first_parameters": None, "segments": [],
                        "state": "draft" if draft else "generating",
                        "created_at": datetime.now(timezone.utc).isoformat()}
            if prompt_plan is not None:
                manifest["prompt_plan"] = prompt_plan
            if cut_frames is not None:
                manifest["cut_frames"] = cut_frames
            if overlap_frames:
                manifest["overlap_frames"] = overlap_frames
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
        manifest_schedule(manifest)
        if "prompt_plan" in manifest:
            manifest["prompt_plan"] = validate_prompt_plan(manifest["prompt_plan"], len(manifest["plan"]))
        if not isinstance(manifest["segments"], list) or len(manifest["segments"]) > len(manifest["plan"]):
            raise core.OrchestratorError("長尺区間記録が不正です")
        seeds = manifest.get("cut_seeds")
        if seeds is not None:
            if not isinstance(seeds, list) or len(seeds) != len(manifest["plan"]):
                raise core.OrchestratorError("長尺Seed記録が不正です")
            for seed in seeds:
                core.check_param("seed", seed)
        return manifest

    def projects(self):
        """Read independent projects, including drafts; corrupt records stay untouched."""
        result = []
        for path in self.root.glob("*/manifest.json"):
            try:
                result.append((path.stat().st_mtime, self.load(path)))
            except (OSError, ValueError, KeyError, TypeError, core.OrchestratorError):
                continue
        return [m for _, m in sorted(result, key=lambda item: item[0], reverse=True)]

    def asset(self, manifest, name) -> Path:
        folder = self.folder(manifest["run_id"])
        path = (folder / name).resolve()
        if not path.is_relative_to(folder):
            raise core.OrchestratorError("長尺記録のパスが不正です")
        return path


def project_cut_lengths(manifest):
    manifest_schedule(manifest)
    return [w["output_frames"] for w in manifest_windows(manifest)]


def first_changed_cut(manifest, prompt_plan, cut_frames):
    old = manifest.get("prompt_plan")
    if old is None:
        raise core.OrchestratorError("旧形式の計画なしプロジェクトは編集できません")
    old_cuts = project_cut_lengths(manifest)
    if old["common"] != prompt_plan["common"]:
        return 0
    for i, (old_text, new_text) in enumerate(zip(old["segments"], prompt_plan["segments"])):
        if old_text != new_text or old_cuts[i] != cut_frames[i]:
            return i
    return min(len(old_cuts), len(cut_frames)) if len(old_cuts) != len(cut_frames) else None


def project_generation_inputs(store, manifest, *, overrides=None, source=None):
    """Resolve live generation inputs without changing the saved cut schedule.

    The left form's standard segment length is for new plans only. Once a
    plan exists, the right editor owns its frame-accurate cut lengths.
    """
    old = manifest["overrides"]
    p = dict(old)
    if overrides is not None:
        # Remove old optional model-specific selections when the new model
        # does not use them. Preserve legacy non-UI parameters and timing.
        for key in core.H3_OPTION_KEYS:
            p.pop(key, None)
        p.update(overrides)
        p["frames"] = old["frames"]
        p["seed"] = overrides["seed"] if "seed" in overrides else secrets.randbits(32)
        core.validate_h3_video_parameters(p)
        core.check_param("seed", p["seed"])
        _, options = core.split_h3_options(p, enabled=True)
        if options:
            continuation_model(options["h3_model"])
    saved_source = store.asset(manifest, manifest["source"])
    selected = saved_source
    source_changed = False
    if source is not None:
        selected = Path(source).expanduser().resolve()
        if not selected.is_file() or selected.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise core.OrchestratorError("左側で有効な参照画像を指定してください")
        if selected.stat().st_size > 40 * 1024 * 1024:
            raise core.OrchestratorError("参照画像は40MB以下にしてください")
        if selected != saved_source.resolve():
            source_changed = True
            if (saved_source.is_file() and selected.suffix.lower() == saved_source.suffix.lower()
                    and selected.stat().st_size == saved_source.stat().st_size):
                with selected.open("rb") as a, saved_source.open("rb") as b:
                    source_changed = hashlib.file_digest(a, "sha256").digest() != hashlib.file_digest(b, "sha256").digest()
            if not source_changed:
                selected = saved_source
    return p, selected, p != old or source_changed


@lock_project
def edit_project(store, manifest, journal, prompt_plan, cut_frames, *, regenerate_from=None,
                 overlap_frames=None, overrides=None, source=None):
    """Create a revision with its unchanged generated prefix. Never remove old data.

    A new run ID isolates job recovery and final history. Old unfinished remote
    jobs must be recovered/cancelled before branching from an already-running plan.
    """
    old_cuts = project_cut_lengths(manifest)
    cuts = list(cut_frames)
    if cuts != old_cuts:
        cuts = validate_cut_frames(cuts)
    approved = validate_prompt_plan(prompt_plan, len(cuts))
    changed = first_changed_cut(manifest, approved, cuts)
    effective, selected_source, inputs_changed = project_generation_inputs(
        store, manifest, overrides=overrides, source=source)
    if inputs_changed:
        changed = 0
    old_overlap = manifest.get("overlap_frames", 0)
    overlap = validate_overlap_frames(old_overlap if overlap_frames is None else overlap_frames)
    same_schedule = cuts == old_cuts
    new_seconds = manifest["seconds"] if same_schedule else sum(cuts) / FPS
    new_cuts = manifest.get("cut_frames") if same_schedule else cuts
    new_windows = schedule_windows(new_seconds, effective["frames"], new_cuts,
                                   overlap_frames=overlap)
    old_windows = manifest_windows(manifest)
    if overlap != old_overlap:
        boundary = next((i for i, (a, b) in enumerate(zip(old_windows, new_windows))
                         if a["generation_frames"] != b["generation_frames"]
                         or a["trim_start_frames"] != b["trim_start_frames"]), len(new_windows))
        changed = boundary if changed is None else min(changed, boundary)
    if regenerate_from is not None:
        if type(regenerate_from) is not int or not 0 <= regenerate_from < len(cuts):
            raise core.OrchestratorError("再生成するカット番号が不正です")
        changed = regenerate_from if changed is None else min(changed, regenerate_from)
    if changed is None:
        return manifest
    # Don't fork away from an active or uncertain remote job. A completed
    # result may remain uncollected; preserve it in the old project.
    for path in journal.root.glob("*/record.json"):
        record = journal.read(path.parent.name)
        if (record.get("context", {}).get("long_run_id") == manifest["run_id"]
                and record["state"] not in ("failed", "completed", "collected")):
            raise core.OrchestratorError("未確定の生成ジョブがあります。元のプロジェクトを再開して状態を確定してください")
    new = store.create(
        manifest["backend"], manifest["request"], selected_source,
        effective, new_seconds, manifest.get("profile"), prompt_plan=approved,
        cut_frames=new_cuts, draft=True, overlap_frames=overlap,
    )
    folder = store.folder(new["run_id"])
    try:
        new["parent_run_id"] = manifest["run_id"]
        new["revision"] = int(manifest.get("revision", 0)) + 1
        new["changed_from"] = changed
        prefix = min(changed, len(manifest["segments"]), len(new["plan"]))
        for i in range(prefix):
            segment = manifest["segments"][i]
            if (new["plan"][i] != manifest["plan"][i]
                    or old_windows[i]["trim_start_frames"] != new_windows[i]["trim_start_frames"]):
                raise core.OrchestratorError("引継ぎカットの生成・助走フレーム数が一致しません")
            old_file = store.asset(manifest, segment["file"])
            dest = store.asset(new, segment["file"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Hard-link immutable completed clips where supported; fall back to
            # a regular copy. Later generations use a different run directory.
            try:
                dest.hardlink_to(old_file)
            except OSError:
                shutil.copy2(old_file, dest)
            new["segments"].append(dict(segment))
        if prefix:
            new["first_parameters"] = dict(manifest["first_parameters"])
        modulus = core.PARAMS["seed"][2] + 1
        old_seeds = manifest.get("cut_seeds") or [
            (int(manifest["overrides"]["seed"]) + i) % modulus
            for i in range(len(old_cuts))
        ]
        seed_changed = effective["seed"] != manifest["overrides"]["seed"]
        seeds = [old_seeds[i] if i < len(old_seeds) and not seed_changed
                 else (int(new["overrides"]["seed"]) + i) % modulus
                 for i in range(len(cuts))]
        # A changed seed or model/source is an explicit new comparison. Keep
        # the specified seed progression rather than randomizing it silently.
        if regenerate_from is not None and not inputs_changed:
            for i in range(regenerate_from, len(seeds)):
                seeds[i] = secrets.randbits(32)
        new["cut_seeds"] = seeds
        store.save(new)
        return new
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def restore_project_plan(store, entry, fallback_backend):
    """Recover a plan-only draft from completed history; never invent old clips."""
    params = dict(entry.parameters)
    approved = params.get("long_prompt_plan")
    source = entry.reference_image
    if approved is None or source is None or not source.is_file():
        raise core.OrchestratorError("履歴に計画または参照画像が保存されていません")
    base = params.get("long_base_overrides")
    if base is None:
        base = {k: v for k, v in params.items() if not k.startswith("long_") and k != "positive_prompt"}
        base["frames"] = params.get("long_segment_frames", 124)
    if not isinstance(base, dict):
        raise core.OrchestratorError("履歴の生成設定が不正です")
    seeds = params.get("long_cut_seeds")
    if seeds is not None:
        if not isinstance(seeds, list) or len(seeds) != len(approved.get("segments", [])):
            raise core.OrchestratorError("履歴のSeed記録が不正です")
        for seed in seeds:
            core.check_param("seed", seed)
    manifest = store.create(params.get("long_backend") or fallback_backend,
                            entry.request_text, source, base, params["long_seconds"],
                            entry.prompt_profile, prompt_plan=approved,
                            cut_frames=params.get("long_cut_frames"), draft=True,
                            overlap_frames=params.get("long_overlap_frames", 0))
    manifest["restored_from_run_id"] = params.get("long_run_id")
    if seeds is not None:
        manifest["cut_seeds"] = list(seeds)
    store.save(manifest)
    return manifest


def series_index(journal, run_id, backend):
    """One journal scan per series execution, keyed by its stable cut index."""
    indexed = {}
    for record in journal.records():
        ctx = record.get("context", {})
        if (record["backend"] == backend.rstrip("/") and ctx.get("long_run_id") == run_id
                and type(ctx.get("long_segment")) is int and record["state"] != "failed"):
            indexed.setdefault(ctx["long_segment"], []).append(record)
    for records in indexed.values():
        records.sort(key=lambda r: r["created_at"], reverse=True)
    return indexed


def series_records(journal, run_id, index, backend):
    return series_index(journal, run_id, backend).get(index, [])


def estimate_remaining(journal, manifest, config, start, plan, indexed=None):
    """Approximate outstanding generation waits, not LLM, downloads or joining."""
    try:
        workflow = config.get("workflows", {}).get(core.H3_I2V_ID, {})
        base = {**workflow.get("defaults", {}), **manifest["overrides"],
                **(manifest.get("first_parameters") or {})}
        inputs = []
        for i in range(start, len(plan)):
            matches = (indexed or {}).get(i, ())
            if matches and matches[0]["state"] in ("completed", "collected"):
                continue
            params = {**base, "frames": plan[i]}
            if i and params.get("h3_model") is not None:
                params["h3_model"] = continuation_model(params["h3_model"])
            inputs.append(params)
        return journal.timings.sequence(manifest["backend"], core.H3_I2V_ID, inputs)
    except TIMING_ERRORS:
        return None


def existing_result(journal, comfy, manifest, index, cancel_event, *, confirm_unknown=None, indexed=None):
    matches = (series_records(journal, manifest["run_id"], index, comfy.base) if indexed is None
               else [journal.read(row["job_id"]) for row in indexed.get(index, [])])
    matches = [row for row in matches if row["state"] != "failed"]
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
        if confirm_unknown is not None and confirm_unknown(record):
            if journal.abandon_unknown(comfy, record["job_id"]):
                return None
            raise core.OrchestratorError("ジョブの状態が変化したか、ComfyUIに実行・待機ジョブがあります。再度長尺再開してください")
        raise UnknownLongJob(record)
    return {"job_id": record["job_id"], "prompt_id": record["prompt_id"],
            "parameters": record["parameters"], "outputs": info.get("outputs", {})}


@lock_project
def run_long_video(store, manifest, config, config_path, journal, output_dir,
                   download, progress=None, cancel_event=None, prompt_cache=None, media=None,
                   confirm_unknown=None, join_only=False, auto_join=True, on_checkpoint=None):
    """Run/resume a series, or join saved cuts without connecting to ComfyUI."""
    media = media or FFmpeg()
    backend = config["comfyui"]["base_url"].rstrip("/")
    if not join_only and manifest["backend"] != backend:
        raise core.OrchestratorError("長尺生成の接続先が保存時と異なります")
    p = manifest["overrides"]
    core.validate_h3_video_parameters(p)
    if p.get("h3_model") is not None:
        continuation_model(p["h3_model"])
    plan, cut_frames, target_frames = manifest_schedule(manifest)
    windows = manifest_windows(manifest)
    overlap = manifest.get("overlap_frames", 0)
    if len(manifest["segments"]) > len(plan):
        raise core.OrchestratorError("長尺計画が不正です")
    prompt_plan = None
    if "prompt_plan" in manifest:
        prompt_plan = validate_prompt_plan(manifest["prompt_plan"], len(plan))
    folder = store.folder(manifest["run_id"])
    source = store.asset(manifest, manifest["source"])
    if not source.is_file():
        raise core.OrchestratorError("長尺生成の元画像がありません")
    if join_only and len(manifest["segments"]) != len(plan):
        raise core.OrchestratorError("全カット生成後に結合してください")
    comfy = None
    indexed = {}
    if not join_only:
        comfy = core.ComfyUI(config["comfyui"])
        comfy.extend_video_timeout(config["comfyui"])
        if len(manifest["segments"]) < len(plan):
            indexed = series_index(journal, manifest["run_id"], comfy.base)
            try:
                journal.timings.bootstrap(journal.root)
            except TIMING_ERRORS:
                pass
        if manifest["state"] == "draft":
            manifest["state"] = "generating"
            store.save(manifest)
            if on_checkpoint:
                on_checkpoint(manifest)
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
            if overlap:
                w = windows[i]
                progress(f"カット{i + 1}: 採用 {w['output_frames']}f / 助走 {w['trim_start_frames']}f / 生成 {plan[i]}f")
        report_estimate(estimate_remaining(journal, manifest, config, i, plan, indexed), label="残カット生成待ち")
        cut_started = time.monotonic()
        result = existing_result(journal, comfy, manifest, i, cancel_event,
                                 confirm_unknown=confirm_unknown, indexed=indexed)
        recovered = result is not None
        if result is None:
            if prompt_plan is not None:
                image = source
                if i:
                    image = folder / f"anchor_{i:03d}.png"
                    # Frame-exact opening anchor, inside the preceding retained window.
                    anchor_frames = continuation_anchor_count(windows[i - 1], windows[i])
                    if overlap and progress:
                        progress(f"カット{i + 1}: 前カットのフレーム {anchor_frames}（1始まり）を開始画像に使用")
                    media.last_frame(clips[-1][0], anchor_frames, image, cancel_event)
                # Always derive seed progression from segment zero's seed.
                params = planned_segment_parameters(
                    manifest["first_parameters"] if i else p, prompt_plan, i, plan[i],
                    lead_in_frames=windows[i]["trim_start_frames"] if overlap else 0,
                )
                if manifest.get("cut_seeds") is not None:
                    params["seed"] = manifest["cut_seeds"][i]
                result = core.execute_saved(
                    config, config_path, core.H3_I2V_ID, params, reference_image=image,
                    progress=progress, cancel_event=cancel_event, job_journal=journal,
                    job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                 "request_text": manifest["request"], "prompt_profile": manifest["profile"]},
                )
            elif i == 0:
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
                                     "parameters": result["parameters"], "frames": info["frames"],
                                     "cut_processing_seconds": round(time.monotonic() - cut_started, 3),
                                     "generation_wait_seconds": result.get("elapsed_seconds") if not recovered else None})
        store.save(manifest)
        journal.update(result["job_id"], state="collected", collection_state="collected")
        clips.append((clip, info))
        if on_checkpoint:
            on_checkpoint(manifest)
    check_cancel(cancel_event)
    report_estimate(None, label="結合・保存" if auto_join or join_only else "保存")
    if not auto_join and not join_only:
        if manifest["state"] != "completed":
            manifest["state"] = "ready_to_join"
            store.save(manifest)
            if on_checkpoint:
                on_checkpoint(manifest)
        return None, None
    output = Path(output_dir) / f"long_{manifest['run_id']}.mp4"
    if manifest["state"] != "completed" or not output.is_file():
        join_options = {"keep_frames": cut_frames} if cut_frames is not None else {}
        if overlap:
            join_options = {"keep_frames": [w["output_frames"] for w in windows],
                            "trim_start_frames": [w["trim_start_frames"] for w in windows]}
        join_started = time.monotonic()
        media.join(clips, target_frames, output, cancel_event, progress, **join_options)
        manifest["join_seconds"] = round(time.monotonic() - join_started, 3)
        manifest["state"] = "completed"
        store.save(manifest)
        if on_checkpoint:
            on_checkpoint(manifest)
    first = dict(manifest["first_parameters"])
    first.update(frames=target_frames, long_segment_frames=p["frames"],
                 long_seconds=manifest["seconds"], long_run_id=manifest["run_id"])
    if cut_frames is not None:
        first["long_cut_frames"] = cut_frames
    if overlap:
        first["long_overlap_frames"] = overlap
    if prompt_plan is not None:
        first["long_prompt_plan"] = prompt_plan
        first["long_base_overrides"] = dict(manifest["overrides"])
        first["long_backend"] = manifest["backend"]
        first["long_cut_seeds"] = [segment["parameters"]["seed"] for segment in manifest["segments"]]
    return {"status": "completed", "workflow_id": LONG_VIDEO_ID, "kind": "i2v",
            "parameters": first, "prompt_id": manifest["run_id"], "outputs": {}}, output


def _check_segment(info, p, frames):
    if (info["frames"] != frames or info["width"] != p["width"] or info["height"] != p["height"]
            or abs(info["fps"] - FPS) > 0.01):
        raise core.OrchestratorError(f"H3区間の実測情報が計画と異なります: {info} / {frames}f")
