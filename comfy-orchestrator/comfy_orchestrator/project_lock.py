"""Per-project OS lock: a crashed process releases it automatically."""
from __future__ import annotations

import os
from contextlib import contextmanager
from functools import wraps

from .parameters import OrchestratorError


@contextmanager
def project_lock(folder):
    # Keep the lock file; deleting/replacing its inode would defeat the lock.
    with (folder / ".project.lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise OrchestratorError("この長尺プロジェクトは別の処理で使用中です") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def lock_project(function):
    @wraps(function)
    def wrapped(store, manifest, *args, **kwargs):
        with project_lock(store.folder(manifest["run_id"])):
            # The caller's loaded state may predate another process's work.
            # Refuse if the persisted generation/plan state changed.
            saved = store.load(store.folder(manifest["run_id"]) / "manifest.json")
            if saved != manifest:
                raise OrchestratorError("長尺プロジェクトの記録が更新されています。再度開いてください")
            return function(store, manifest, *args, **kwargs)
    return wrapped
