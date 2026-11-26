"""Read-only storage accounting, including app-owned hard-link aliases."""
from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def _files(path):
    # Do not follow directory symlinks, junctions, or other reparse points.
    pending = [path]
    while pending:
        item = pending.pop()
        try:
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                continue
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(item) as entries:
                    pending.extend(Path(entry.path) for entry in entries)
            elif stat.S_ISREG(info.st_mode):
                yield item, info
        except (FileNotFoundError, PermissionError):
            continue


def storage_report(root):
    """Logical bytes and distinct-file bytes (not filesystem allocation sizes)."""
    root = Path(root).resolve()
    data = root / "data"
    areas = [
        ("完成・出力", root / "outputs"),
        ("長尺プロジェクト", data / "long_videos"),
        ("ジョブ記録", data / "jobs"),
        ("参照画像プール", data / "asset_pool"),
        ("解釈キャッシュ", root / ".cache"),
    ]
    known = {path for _, path in areas}
    history = []
    try:
        history = [p for p in data.iterdir() if p not in known]
    except FileNotFoundError:
        pass
    sizes = {}
    rows = []
    for label, paths in [(name, [path]) for name, path in areas] + [("履歴・その他データ", history)]:
        files = logical = unique = 0
        local = set()
        for path in paths:
            for name, info in _files(path):
                files += 1
                logical += info.st_size
                key = (info.st_dev, info.st_ino) if info.st_ino else ("path", str(name))
                if key not in local:
                    unique += info.st_size
                    local.add(key)
                sizes.setdefault(key, info.st_size)
        rows.append({"name": label, "files": files, "logical_bytes": logical,
                     "unique_bytes": unique})
    # The unique total counts linked files only once across all areas.
    logical = sum(row["logical_bytes"] for row in rows)
    unique = sum(sizes.values())
    disk = shutil.disk_usage(root)
    return {"rows": rows, "logical_bytes": logical, "unique_bytes": unique,
            "shared_bytes": max(0, logical - unique), "disk_free_bytes": disk.free,
            "disk_total_bytes": disk.total}


def format_bytes(value):
    value = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{value:.0f} B"
        value /= 1024
