"""Durable continuous-video projects and immutable revision creation."""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import core, h3_prompt
from .asset_store import save_snapshot
from .project_lock import lock_project
from .timeline import validate_cut_frames, validate_prompt_plan, validate_overlap_frames
from .long_video_plan import (FPS, schedule_windows, manifest_windows, manifest_schedule,
                              long_generation_model, validate_structured_timing, project_cut_lengths,
                              first_changed_cut, connection_changed_from)


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

    def create(self, backend: str, request: str, source: Path | None, overrides: dict,
               seconds: int | float, profile=None, *, prompt_plan=None, cut_frames=None,
               draft=False, overlap_frames=0) -> dict:
        text_only = source is None
        if text_only and (not request.strip() or not isinstance(prompt_plan, dict)
                          or prompt_plan.get("format") != h3_prompt.FORMAT):
            raise core.OrchestratorError("参照画像なしの長尺生成には自然文とH3公式形式の計画が必要です")
        p = long_generation_model(overrides, text_only=text_only)
        core.validate_h3_video_parameters(p)
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
            validate_structured_timing(prompt_plan, windows, p, text_only=text_only)
        p.setdefault("seed", secrets.randbits(32))
        if source is not None:
            source = Path(source)
            if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise core.OrchestratorError("長尺生成の参照画像がありません")
            if source.stat().st_size > 40 * 1024 * 1024:
                raise core.OrchestratorError("参照画像は40MB以下にしてください")
        run_id = str(uuid.uuid4())
        folder = self.folder(run_id)
        folder.mkdir()
        try:
            name = None
            if source is not None:
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
        if manifest["source"] is None:
            if (not manifest["request"].strip() or manifest.get("prompt_plan", {}).get("format") != h3_prompt.FORMAT
                    or core.h3_ref2va_filename(manifest["overrides"].get("h3_model")) is not None):
                raise core.OrchestratorError("参照なし長尺プロジェクトの記録が不正です")
        elif not isinstance(manifest["source"], str) or not manifest["source"]:
            raise core.OrchestratorError("長尺プロジェクトの参照画像記録が不正です")
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

    def source_asset(self, manifest) -> Path | None:
        name = manifest["source"]
        return None if name is None else self.asset(manifest, name)

    def asset(self, manifest, name) -> Path:
        folder = self.folder(manifest["run_id"])
        path = (folder / name).resolve()
        if not path.is_relative_to(folder):
            raise core.OrchestratorError("長尺記録のパスが不正です")
        return path


def project_generation_inputs(store, manifest, *, overrides=None, source=None):
    """Resolve live generation inputs without changing the saved cut schedule.

    The left form's standard segment length is for new plans only. Once a
    plan exists, the right editor owns its frame-accurate cut lengths.
    """
    old = manifest["overrides"]
    saved_source = store.source_asset(manifest)
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
            p = long_generation_model(p, text_only=saved_source is None)
    selected = saved_source
    source_changed = False
    if source is not None:
        if saved_source is None:
            raise core.OrchestratorError("参照画像の有無を変える場合は新規計画を作成してください")
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
    validate_structured_timing(approved, new_windows, effective, text_only=selected_source is None)
    old_windows = manifest_windows(manifest)
    boundary = connection_changed_from(manifest, cuts, overlap)
    if boundary is not None:
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
                    or old_windows[i]["trim_start_frames"] != new_windows[i]["trim_start_frames"]
                    or old_windows[i].get("guide_frames", 0) != new_windows[i].get("guide_frames", 0)):
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
    text_only = params.get("long_text_only") is True
    if approved is None or (not text_only and (source is None or not source.is_file())):
        raise core.OrchestratorError("履歴に計画または参照画像が保存されていません")
    if text_only:
        if source is not None:
            raise core.OrchestratorError("履歴の参照なし設定が不正です")
        source = None
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
