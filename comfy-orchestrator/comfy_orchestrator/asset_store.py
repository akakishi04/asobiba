"""Content-addressed immutable snapshots, with safe copy fallback."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .parameters import OrchestratorError

LIMIT = 40 * 1024 * 1024


def _copy_new(source, target):
    created = False
    try:
        with source.open("rb") as stream, target.open("xb") as out:
            created = True
            shutil.copyfileobj(stream, out)
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise


def save_snapshot(source, target, pool):
    """Copy the input before hashing; never hard-link a user's original file.

    Archived aliases remain ordinary files at their original documented paths.
    The pool and aliases are app-owned immutable data. No existing file is
    overwritten, and filesystems without hard-links keep independent copies.
    """
    source, target, pool = Path(source), Path(target), Path(pool)
    if target.exists():
        raise FileExistsError(target)
    pool.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    if before.st_size > LIMIT:
        raise OrchestratorError("保存する画像は40MB以下にしてください")
    temporary = None
    try:
        digest = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(dir=pool, suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
            with source.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > LIMIT:
                        raise OrchestratorError("保存する画像は40MB以下にしてください")
                    digest.update(chunk)
                    out.write(chunk)
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or total != before.st_size:
            raise OrchestratorError("保存中に参照画像が変更されました")
        blob = pool / (digest.hexdigest() + ".blob")
        try:
            os.link(temporary, blob)
        except FileExistsError:
            pass
        except OSError:
            _copy_new(temporary, target)
            return target
        # Do not link corrupted, symlinked or manually changed pool entries.
        try:
            if blob.is_symlink() or blob.stat().st_size != total:
                raise OSError("snapshot pool mismatch")
            with blob.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest.hexdigest():
                    raise OSError("snapshot pool mismatch")
            os.link(blob, target)
        except FileExistsError:
            raise
        except OSError:
            _copy_new(temporary, target)
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
