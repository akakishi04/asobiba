"""Output identity, atomic download and recoverable collection (no Tk)."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from .parameters import OrchestratorError
from .workflow_registry import VIDEO_KINDS

VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".mkv"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def is_video_output(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def output_media(result: dict) -> list[dict]:
    """Native SaveVideo uses images + animated; also support videos/gifs metadata."""
    media = []
    seen = set()
    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict):
        return media
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for key in ("images", "videos", "gifs"):
            entries = node_output.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
                    continue
                name = entry["filename"]
                if Path(name).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                    continue
                subfolder = str(entry.get("subfolder", ""))
                kind = str(entry.get("type", "output"))
                identity = (name, subfolder, kind)
                if identity in seen:
                    continue
                seen.add(identity)
                media.append({"filename": name, "subfolder": subfolder, "type": kind})
    return media


def output_images(result: dict) -> list[dict]:
    return [m for m in output_media(result) if Path(m["filename"]).suffix.lower() in IMAGE_EXTENSIONS]


def output_destination(metadata: dict, prompt_id: str, directory: Path) -> Path:
    """Stable local filename used for both output reservation and atomic download."""
    parameters = {key: metadata[key] for key in ("filename", "subfolder", "type")}
    safe_name = Path(metadata["filename"].replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        raise OrchestratorError("未対応の出力形式です")
    prefix = "".join(c for c in prompt_id[:16] if c.isalnum() or c in "-_") or "output"
    identity = json.dumps([prompt_id, parameters], sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return directory / (prefix + "_" + digest + "_" + Path(safe_name).stem[:100] + suffix)


def save_output_image(base_url: str, metadata: dict, prompt_id: str, *, output_dir) -> Path:
    """Download a bounded image or video atomically into the local outputs directory."""
    parameters = {key: metadata[key] for key in ("filename", "subfolder", "type")}
    safe_name = Path(metadata["filename"].replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        raise OrchestratorError("未対応の出力形式です")
    limit = (512 if suffix in VIDEO_EXTENSIONS else 40) * 1024 * 1024
    url = base_url.rstrip("/") + "/view?" + urllib.parse.urlencode(parameters)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = output_destination(metadata, prompt_id, directory)
    temporary = destination.with_suffix(destination.suffix + ".part")
    total = 0
    try:
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise OrchestratorError("出力ファイルがサイズ上限を超えました")
                out.write(chunk)
        if total == 0:
            raise OrchestratorError("出力ファイルが空です")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def collect_generation_outputs(base_url, result, kind, *, output_dir, journal=None, cancel_event=None,
                               downloader=None):
    """Checkpoint all supported files; partial downloads are never collected."""
    job_id = result.get("job_id") if journal is not None else None
    downloads = {}
    reserved = {}
    if job_id:
        record = journal.read(job_id)
        stored = record.get("downloaded_outputs", {})
        if isinstance(stored, dict):
            downloads = dict(stored)
        stored = record.get("reserved_outputs", {})
        if isinstance(stored, dict):
            reserved = dict(stored)
    output_root = Path(output_dir).resolve()
    if downloader is None:
        def downloader(base, item, prompt_id):
            return save_output_image(base, item, prompt_id, output_dir=output_root)
    images = []
    try:
        entries = output_media(result)
        if not entries:
            raise OrchestratorError("生成結果に回収できる出力がありません")
        if job_id:
            for item in entries:
                identity = json.dumps(item, sort_keys=True, ensure_ascii=False)
                reserved[identity] = output_destination(item, result["prompt_id"], output_root).relative_to(output_root).as_posix()
            # Reserve before any atomic rename so legacy indexing cannot claim a partial collection.
            journal.update(job_id, reserved_outputs=reserved)
        for item in entries:
            if cancel_event is not None and cancel_event.is_set():
                raise OrchestratorError("出力回収を中断しました")
            identity = json.dumps(item, sort_keys=True, ensure_ascii=False)
            cached = downloads.get(identity)
            path = None
            if isinstance(cached, str):
                candidate = (output_root / cached).resolve()
                if candidate.is_relative_to(output_root) and candidate.is_file() and candidate.stat().st_size > 0:
                    path = candidate
            if path is None:
                path = Path(downloader(base_url, item, result["prompt_id"])).resolve()
                if not path.is_relative_to(output_root) or not path.is_file() or path.stat().st_size <= 0:
                    raise OrchestratorError("出力ファイルの保存結果が不正です")
                downloads[identity] = path.relative_to(output_root).as_posix()
                if job_id:
                    journal.update(job_id, collection_state="downloading", downloaded_outputs=downloads)
            images.append(path)
        if kind in VIDEO_KINDS and not any(is_video_output(path) for path in images):
            raise OrchestratorError("動画出力がありません")
        if kind not in VIDEO_KINDS and not any(path.suffix.lower() in IMAGE_EXTENSIONS for path in images):
            raise OrchestratorError("画像出力がありません")
        if job_id:
            journal.update(job_id, collection_state="downloaded", downloaded_outputs=downloads,
                           collection_error=None)
        return images
    except Exception as exc:
        if job_id:
            journal.update(job_id, collection_state="download_failed", downloaded_outputs=downloads,
                           collection_error=str(exc))
        raise OrchestratorError(
            "ComfyUIでの生成は完了しましたが、出力回収に失敗しました。"
            "「未回収結果を取得」で再試行してください: " + str(exc)
        ) from exc


