"""Persistent, local generation journal. No UI, no implicit submission retries."""
from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .parameters import OrchestratorError

ASSETS = ("reference_image", "mask_image", "pose_image", "composition_image")
TERMINAL = frozenset({"collected", "failed"})


class JobCancellationRequested(OrchestratorError):
    """The targeted cancellation request was acknowledged, not necessarily finished."""


class JobExecutionFailed(OrchestratorError):
    """The server reported an execution failure."""


class JobSubmissionRejected(JobExecutionFailed):
    """ComfyUI explicitly rejected the prompt before queueing it."""


class UnknownLongJob(OrchestratorError):
    """A previous long-video submission has no provable outcome."""
    def __init__(self, record):
        self.job_id = record["job_id"]
        self.prompt_id = record["prompt_id"]
        super().__init__("前回ジョブの状態が不明です。再投入には確認が必要です: " + self.prompt_id)


def _now():
    return datetime.now(timezone.utc).isoformat()


class JobJournal:
    """One atomic JSON record per submission, with immutable input snapshots.

    The ID is chosen before POST /prompt, so an ambiguous network response on
    supported ComfyUI versions can be inspected by that ID without resubmitting.
    Older servers may return a different ID; persist the actual accepted ID.
    """
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _folder(self, job_id: str) -> Path:
        try:
            if str(uuid.UUID(job_id)) != job_id:
                raise ValueError()
        except (ValueError, AttributeError, TypeError) as exc:
            raise OrchestratorError("ジョブIDが不正です") from exc
        return self.root / job_id

    def _write(self, record: dict) -> None:
        folder = self._folder(record["job_id"])
        target = folder / "record.json"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                             suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.flush()
            temporary.replace(target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def create(self, backend: str, workflow_id: str, kind: str, parameters: dict,
               graph: dict, context: dict | None = None) -> dict:
        job_id = str(uuid.uuid4())
        folder = self._folder(job_id)
        folder.mkdir()
        snapshot = dict(context or {})
        try:
            assets = folder / "assets"
            assets.mkdir()

            def copy_asset(value, stem):
                if value is None:
                    return None
                source = Path(value)
                if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                    raise OrchestratorError(f"ジョブの参照画像を保存できません: {source}")
                if source.stat().st_size > 40 * 1024 * 1024:
                    raise OrchestratorError("ジョブの参照画像は40MB以下にしてください")
                target = assets / (stem + source.suffix.lower())
                shutil.copyfile(source, target)
                return target.relative_to(folder).as_posix()

            for name in ASSETS:
                snapshot[name] = copy_asset(snapshot.get(name), name)
            snapshot["character_references"] = [
                copy_asset(value, f"character_{idx}")
                for idx, value in enumerate(snapshot.get("character_references", ()))
            ]
            record = {
                "schema": 1, "job_id": job_id, "prompt_id": job_id,
                "backend": backend.rstrip("/"), "state": "submitting",
                "collection_state": "pending",
                "created_at": _now(), "updated_at": _now(),
                "workflow_id": workflow_id, "kind": kind,
                "parameters": parameters, "graph": graph, "context": snapshot,
            }
            self._write(record)
            return record
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def read(self, job_id: str) -> dict:
        record = json.loads((self._folder(job_id) / "record.json").read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != 1 or record.get("job_id") != job_id:
            raise OrchestratorError("ジョブ記録の形式が不正です")
        return record

    def update(self, job_id: str, **fields) -> dict:
        record = self.read(job_id)
        record.update(fields, updated_at=_now())
        self._write(record)
        return record

    def recoverable(self, backend: str) -> list[dict]:
        records = []
        for path in self.root.glob("*/record.json"):
            record = self.read(path.parent.name)
            if record["backend"] == backend.rstrip("/") and record["state"] not in TERMINAL:
                records.append(record)
        return sorted(records, key=lambda r: r["created_at"])

    def abandon_unknown(self, comfy, job_id: str) -> bool:
        """Only after explicit operator approval and two server checks."""
        record = self.read(job_id)
        if record["state"] in TERMINAL:
            return False
        state, _ = self.inspect(comfy, record)
        if state != "unknown" or not comfy.queue_is_idle():
            return False
        state, _ = self.inspect(comfy, record)
        if state != "unknown":
            return False
        self.update(job_id, state="failed", error="operator abandoned unresolved submission",
                    failure_kind="operator_abandoned")
        return True

    def context_for_history(self, record: dict) -> dict:
        folder = self._folder(record["job_id"])
        context = dict(record.get("context", {}))

        def resolve_asset(value):
            if value is None:
                return None
            target = (folder / value).resolve()
            if not target.is_relative_to(folder / "assets") or not target.is_file():
                raise OrchestratorError("ジョブ記録の参照画像がありません")
            return target

        for name in ASSETS:
            context[name] = resolve_asset(context.get(name))
        context["character_references"] = tuple(resolve_asset(p) for p in context.get("character_references", ()))
        return context

    def inspect(self, comfy, record: dict) -> tuple[str, dict | None]:
        """Inspect an existing prompt only. Never submit or interrupt anything."""
        if record["backend"] != comfy.base.rstrip("/"):
            raise OrchestratorError("ジョブとComfyUIの接続先が一致しません")
        if record["state"] == "completed" and isinstance(record.get("outputs"), dict):
            return "completed", {"outputs": record["outputs"], "status": record.get("comfy_status", {})}
        history = comfy.job_history(record["prompt_id"])
        if history is None:
            return comfy.job_queue_state(record["prompt_id"]), None
        status = history.get("status", {})
        if isinstance(status, dict) and (status.get("status_str") == "error" or status.get("completed") is False):
            self.update(record["job_id"], state="failed", comfy_status=status)
            return "failed", history
        self.update(record["job_id"], state="completed", outputs=history.get("outputs", {}), comfy_status=status)
        return "completed", history


def run_job(comfy, graph: dict, workflow_id: str, kind: str, parameters: dict,
            *, progress=None, cancel_event=None, journal: JobJournal | None = None,
            context: dict | None = None) -> tuple[str, dict, dict]:
    """Shared submission/wait path for first-generation and history replay."""
    record = None
    start = time.monotonic()
    if journal is not None:
        record = journal.create(comfy.base, workflow_id, kind, parameters, graph, context)
    try:
        if cancel_event is not None and cancel_event.is_set():
            if record is not None:
                journal.update(record["job_id"], state="failed", error="cancelled before submission")
            raise JobExecutionFailed("生成開始前に中止しました")
        prompt_id = (comfy.submit(graph, prompt_id=record["prompt_id"]) if record is not None
                     else comfy.submit(graph))
        if record is not None:
            journal.update(record["job_id"], state="submitted", prompt_id=prompt_id)
        if progress:
            progress(f"ComfyUI: 生成完了を待機中（{prompt_id}）")
        history = (comfy.wait(prompt_id, cancel_event=cancel_event, cancel_remote=True)
                   if record is not None else comfy.wait(prompt_id, cancel_event=cancel_event))
        elapsed = round(time.monotonic() - start, 3)
        if record is None:
            return prompt_id, history, {}
        journal.update(record["job_id"], state="completed", outputs=history.get("outputs", {}),
                       comfy_status=history.get("status", {}), elapsed_seconds=elapsed)
        return prompt_id, history, {"job_id": record["job_id"], "elapsed_seconds": elapsed}
    except Exception as exc:
        if record is not None:
            state = ("cancel_requested" if isinstance(exc, JobCancellationRequested) else
                     "failed" if isinstance(exc, JobExecutionFailed) else "unknown")
            # Ambiguous network failures are deliberately not classified as failed.
            kind = ("submission_rejected" if isinstance(exc, JobSubmissionRejected) else
                    "execution_failed" if isinstance(exc, JobExecutionFailed) else
                    "cancel_requested" if isinstance(exc, JobCancellationRequested) else "uncertain")
            journal.update(record["job_id"], state=state, error=str(exc), failure_kind=kind,
                           elapsed_seconds=round(time.monotonic() - start, 3))
        raise
