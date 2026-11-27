"""Application service for new generations, replays and long-video recovery.

No Tk dependencies. GUI supplies immutable job settings and receives events.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import core, output_collection
from .history import HistoryError
from .task_controller import worker_events  # compatibility export
from .long_video import run_long_video


def active_aux_inputs(kind, mask, pose, composition):
    """Ignore inactive still-image inputs without discarding their editor values."""
    if kind in core.VIDEO_KINDS:
        return None, None, None
    return mask, pose, composition


def record_history(config, history_store, journal, result, images, request_text,
                   source_image=None, mask_image=None, pose_image=None, composition_image=None,
                   prompt_profile=None, character_references=(), character_traits=None,
                   character_analysis=None, *, progress=None):
    def note(message):
        if progress:
            progress(message)
    if not images:
        return None
    job_id = result.get("job_id")
    try:
        workflow_id = result["workflow_id"]
        if job_id:
            record = journal.read(job_id)
            ctx = journal.context_for_history(record)
            request_text = ctx.get("request_text", request_text)
            source_image = ctx["reference_image"]
            mask_image = ctx["mask_image"]
            pose_image = ctx["pose_image"]
            composition_image = ctx["composition_image"]
            prompt_profile = ctx.get("prompt_profile", prompt_profile)
            character_references = ctx["character_references"]
            character_traits = ctx.get("character_traits")
            character_analysis = ctx.get("character_analysis")
        entry = history_store.record(
            prompt_id=result["prompt_id"],
            workflow_id=workflow_id,
            kind=result.get("kind") or config["workflows"][workflow_id]["kind"],
            request_text=request_text,
            parameters=result["parameters"],
            images=images,
            reference_image=source_image,
            mask_image=mask_image,
            pose_image=pose_image,
            composition_image=composition_image,
            prompt_profile=prompt_profile,
            character_references=character_references,
            character_traits=character_traits,
            character_analysis=character_analysis,
        )
        if result.get("job_id") and journal is not None:
            try:
                journal.update(result["job_id"], state="collected",
                                        collection_state="collected", history_id=entry.id)
            except (OSError, ValueError, core.OrchestratorError) as exc:
                note(f"ジョブ記録の更新に失敗: {exc}")
        return entry.id
    except (HistoryError, OSError, ValueError, sqlite3.Error, core.OrchestratorError) as exc:
        if job_id:
            try:
                journal.update(job_id, collection_state="history_failed", collection_error=str(exc))
            except (OSError, ValueError, core.OrchestratorError):
                pass
        note(f"履歴保存に失敗しました（出力は保持）: {exc}")
        return None



class GenerationController:
    def __init__(self, config, config_path, output_dir, history_store, journal,
                 *, progress=None, cancel_event=None, prompt_cache=None):
        self.config = config
        self.config_path = Path(config_path)
        self.output_dir = Path(output_dir)
        self.history_store = history_store
        self.journal = journal
        self.progress = progress
        self.cancel_event = cancel_event
        self.prompt_cache = prompt_cache

    def note(self, message):
        if self.progress:
            self.progress(message)

    def record(self, result, images, request_text, source_image=None, **context):
        return record_history(self.config, self.history_store, self.journal,
                              result, images, request_text, source_image,
                              progress=self.progress, **context)

    def finish(self, result, kind, request_text, source_image=None, **context):
        if result["status"] == "dry_run":
            return result, [], None
        images = output_collection.collect_generation_outputs(
            self.config["comfyui"]["base_url"], result, kind, output_dir=self.output_dir,
            journal=self.journal, cancel_event=self.cancel_event,
        )
        history_id = self.record(result, images, request_text, source_image, **context)
        return result, images, history_id

    def generate(self, request, workflow_id, overrides, *, image=None, mask_image=None,
                 pose_image=None, composition_image=None, prompt_profile=None,
                 character_references=(), character_traits=None, character_analysis=None,
                 dry_run=False):
        kind = self.config["workflows"][workflow_id]["kind"]
        mask_image, pose_image, composition_image = active_aux_inputs(
            kind, mask_image, pose_image, composition_image,
        )
        if kind in core.VIDEO_KINDS:
            character_references, character_traits, character_analysis = (), None, None
        context = {"prompt_profile": prompt_profile, "character_references": character_references,
                   "character_traits": character_traits, "character_analysis": character_analysis}
        result = core.execute(
            self.config, self.config_path, request, image=image, dry_run=dry_run,
            selected_workflow=workflow_id, overrides=overrides, progress=self.progress,
            cancel_event=self.cancel_event, mask_image=mask_image, pose_image=pose_image,
            composition_image=composition_image, character_traits=character_traits,
            job_journal=self.journal, job_context=context, prompt_cache=self.prompt_cache,
            release_before_dry_run=True,
        )
        return self.finish(result, kind, request, image, mask_image=mask_image,
                           pose_image=pose_image, composition_image=composition_image, **context)

    def replay(self, entry, *, new_seed=False):
        refs = entry.character_references
        refs_ok = all(p.is_file() for p in refs)
        composition = entry.composition_image
        context = {
            "request_text": entry.request_text, "prompt_profile": entry.prompt_profile,
            "composition_image": composition if composition and composition.is_file() else None,
            "character_references": refs if refs_ok else (),
            "character_traits": entry.character_traits,
            "character_analysis": entry.character_analysis if refs_ok else None,
        }
        result = core.execute_saved(
            self.config, self.config_path, entry.workflow_id, entry.parameters,
            reference_image=entry.reference_image, new_seed=new_seed, progress=self.progress,
            cancel_event=self.cancel_event, mask_image=entry.mask_image, pose_image=entry.pose_image,
            job_journal=self.journal, job_context=context,
        )
        return self.finish(result, entry.kind, entry.request_text, entry.reference_image,
                           mask_image=entry.mask_image, pose_image=entry.pose_image,
                           **{key: value for key, value in context.items() if key != "request_text"})

    def complete_long(self, store, manifest, media, *, confirm_unknown=None,
                      join_only=False, auto_join=True, on_checkpoint=None):
        def download(result, directory):
            videos = [item for item in output_collection.output_media(result)
                      if Path(item["filename"]).suffix.lower() in output_collection.VIDEO_EXTENSIONS]
            if not videos:
                raise core.OrchestratorError("長尺区間の動画を取得できません")
            return output_collection.save_output_image(
                self.config["comfyui"]["base_url"], videos[0], result["prompt_id"],
                output_dir=directory,
            )
        self.note("長尺記録: " + str(store.folder(manifest["run_id"]) / "manifest.json"))
        result, video = run_long_video(
            store, manifest, self.config, self.config_path, self.journal, self.output_dir,
            download, progress=self.progress, cancel_event=self.cancel_event,
            prompt_cache=self.prompt_cache, media=media, confirm_unknown=confirm_unknown,
            join_only=join_only, auto_join=auto_join, on_checkpoint=on_checkpoint,
        )
        if result is None:
            return manifest["run_id"]
        existing = self.history_store.find_by_prompt_id(result["prompt_id"])
        history_id = existing.id if existing else self.record(
            result, [video], manifest["request"], store.source_asset(manifest),
            prompt_profile=manifest.get("profile"),
        )
        return result, [video], history_id

    def recover(self):
        recovered = remaining = 0
        comfy = core.ComfyUI(self.config["comfyui"])
        for record in self.journal.recoverable(comfy.base):
            if record.get("context", {}).get("long_run_id"):
                remaining += 1
                self.note("長尺区間は「長尺再開」で回収してください")
                continue
            try:
                prompt_id = record["prompt_id"]
                existing = self.history_store.find_by_prompt_id(prompt_id)
                if existing is not None:
                    self.journal.update(record["job_id"], state="collected",
                                        collection_state="collected", history_id=existing.id)
                    continue
                state, info = self.journal.inspect(comfy, record)
                if state != "completed":
                    remaining += state != "failed"
                    self.note(f"{prompt_id}: {state}")
                    continue
                context = self.journal.context_for_history(record)
                result = {"status": "completed", "job_id": record["job_id"],
                          "prompt_id": prompt_id, "workflow_id": record["workflow_id"],
                          "kind": record["kind"], "parameters": record["parameters"],
                          "outputs": info.get("outputs", {})}
                _, _, history_id = self.finish(result, record["kind"],
                                               context.get("request_text", ""), context["reference_image"])
                if history_id is not None:
                    recovered += 1
                else:
                    remaining += 1
            except Exception as exc:
                remaining += 1
                self.note(f"回収失敗 {record['prompt_id']}: {exc}")
        return recovered, remaining


