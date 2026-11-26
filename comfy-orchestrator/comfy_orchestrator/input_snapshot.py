"""Freeze file inputs before interpretation, upload and durable recording."""
from __future__ import annotations

from functools import wraps
from inspect import signature
from pathlib import Path
from tempfile import TemporaryDirectory

from .parameters import OrchestratorError
from .h3_guide import validate_guide_inputs

_ROLES = ("image", "reference_image", "mask_image", "pose_image", "composition_image")
_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_LIMIT = 40 * 1024 * 1024


def copy_frozen_asset(value, folder: Path, name: str):
    if value is None:
        return None
    source = Path(value).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in _SUFFIXES:
        raise OrchestratorError(f"入力画像が存在しないか、未対応の形式です: {source}")
    before = source.stat()
    if before.st_size > _LIMIT:
        raise OrchestratorError("入力画像は40MB以下にしてください")
    target = folder / (name + source.suffix.lower())
    with source.open("rb") as stream, target.open("wb") as out:
        total = 0
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            if total > _LIMIT:
                raise OrchestratorError("入力画像は40MB以下にしてください")
            out.write(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or total != before.st_size:
        raise OrchestratorError(f"入力画像が保存中に変更されました: {source}")
    return target


def freeze_generation_inputs(function):
    """Journal-backed jobs use private inputs; preserve legacy CLI behavior."""
    sig = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if bound.arguments.get("job_journal") is None:
            return function(*args, **kwargs)
        with TemporaryDirectory(prefix="asobiba-input-") as temporary:
            folder = Path(temporary)
            context = dict(bound.arguments.get("job_context") or {})
            for role in _ROLES:
                if role in bound.arguments:
                    bound.arguments[role] = copy_frozen_asset(bound.arguments[role], folder, role)
                elif role in context:
                    context[role] = copy_frozen_asset(context[role], folder, role)
            context["character_references"] = tuple(
                copy_frozen_asset(value, folder, f"character_{i}")
                for i, value in enumerate(context.get("character_references", ()))
            )
            if "guide_images" in bound.arguments:
                images = validate_guide_inputs(bound.arguments["guide_images"])
                bound.arguments["guide_images"] = tuple(
                    copy_frozen_asset(value, folder, f"guide_{i:03d}")
                    for i, value in enumerate(images, start=1)
                )
            bound.arguments["job_context"] = context
            return function(*bound.args, **bound.kwargs)

    return wrapped
