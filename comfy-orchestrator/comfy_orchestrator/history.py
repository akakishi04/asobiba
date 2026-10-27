"""Local SQLite history for ComfyUI runs, with durable I2I reference snapshots.

Only files beneath the application's own output directory are indexed.
The database and reference copies live under data/, which must be git-ignored.
No images or prompt content are sent to external storage by this module.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryError(ValueError):
    """Invalid or unavailable history data."""


@dataclass(frozen=True)
class HistoryEntry:
    id: str
    created_at: str
    prompt_id: str
    workflow_id: str
    kind: str
    request_text: str
    parameters: dict[str, Any]
    images: tuple[Path, ...]
    reference_image: Path | None
    legacy: bool = False
    mask_image: Path | None = None
    pose_image: Path | None = None

    @property
    def first_image(self) -> Path | None:
        return self.images[0] if self.images else None


class HistoryStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.data = self.root / "data"
        self.outputs = self.root / "outputs"
        self.database = self.data / "history.sqlite3"
        self.data.mkdir(parents=True, exist_ok=True)
        self.outputs.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS generations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    prompt_id TEXT NOT NULL UNIQUE,
                    workflow_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    request_text TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    images_json TEXT NOT NULL,
                    reference_file TEXT,
                    legacy INTEGER NOT NULL DEFAULT 0
                )
            """)
            columns = {row[1] for row in con.execute("PRAGMA table_info(generations)")}
            for column in ("mask_file", "pose_file"):
                if column not in columns:
                    con.execute(f"ALTER TABLE generations ADD COLUMN {column} TEXT")
            con.execute(
                "CREATE INDEX IF NOT EXISTS history_recent_idx "
                "ON generations(created_at DESC, id DESC)"
            )

    @staticmethod
    def _child_path(root: Path, relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise HistoryError("履歴に不正なファイルパスが含まれています")
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise HistoryError("履歴の画像パスが保存領域の外を指しています")
        return target

    def _relative_output(self, path: Path) -> str:
        absolute = path.resolve()
        if not absolute.is_relative_to(self.outputs):
            raise HistoryError("出力画像はアプリのoutputsフォルダに保存してください")
        if not absolute.is_file():
            raise HistoryError(f"履歴へ登録する画像が見つかりません: {absolute}")
        return absolute.relative_to(self.outputs).as_posix()

    def record(
        self, *,
        prompt_id: str,
        workflow_id: str,
        kind: str,
        request_text: str,
        parameters: dict,
        images: list[Path],
        reference_image: Path | None = None,
        mask_image: Path | None = None,
        pose_image: Path | None = None,
    ) -> HistoryEntry:
        if not isinstance(parameters, dict):
            raise HistoryError("履歴の生成設定はJSONオブジェクトである必要があります")
        if not images:
            raise HistoryError("出力画像がない生成結果は履歴に登録できません")
        if not prompt_id or not workflow_id:
            raise HistoryError("prompt_idとworkflow_idが必要です")
        image_names = [self._relative_output(Path(x)) for x in images]
        row_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        copied: list[Path] = []

        def snapshot_asset(source: Path | None, folder_name: str) -> str | None:
            if source is None:
                return None
            source = Path(source).resolve()
            if not source.is_file() or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                raise HistoryError(f"保存する画像がないか、対応していない形式です: {source}")
            if source.stat().st_size > 40 * 1024 * 1024:
                raise HistoryError("履歴の参照画像は40MB以下にしてください")
            folder = self.data / folder_name
            folder.mkdir(parents=True, exist_ok=True)
            snapshot = folder / (row_id + source.suffix.lower())
            # Never copy over the same path if a reference is already archived.
            shutil.copyfile(source, snapshot)
            copied.append(snapshot)
            return snapshot.relative_to(self.data).as_posix()

        try:
            reference_file = snapshot_asset(reference_image, "references")
            mask_file = snapshot_asset(mask_image, "masks")
            pose_file = snapshot_asset(pose_image, "poses")
        except Exception:
            for file in copied:
                file.unlink(missing_ok=True)
            raise

        try:
            with self._connection() as con:
                con.execute(
                    """INSERT INTO generations
                    (id,created_at,prompt_id,workflow_id,kind,request_text,
                     parameters_json,images_json,reference_file,legacy,mask_file,pose_file)
                    VALUES (?,?,?,?,?,?,?,?,?,0,?,?)""",
                    (
                        row_id, now, prompt_id, workflow_id, kind, request_text,
                        json.dumps(parameters, ensure_ascii=False),
                        json.dumps(image_names, ensure_ascii=False),
                        reference_file, mask_file, pose_file,
                    ),
                )
        except Exception:
            for file in copied:
                file.unlink(missing_ok=True)
            raise
        result = self.get(row_id)
        assert result is not None
        return result

    def _read_row(self, row: sqlite3.Row) -> HistoryEntry:
        try:
            relative_images = json.loads(row["images_json"])
            parameters = json.loads(row["parameters_json"])
            if not isinstance(relative_images, list) or not isinstance(parameters, dict):
                raise ValueError("invalid JSON structure")
            images = tuple(self._child_path(self.outputs, p) for p in relative_images)
            reference = (
                self._child_path(self.data, row["reference_file"])
                if row["reference_file"] else None
            )
            mask = (
                self._child_path(self.data, row["mask_file"])
                if row["mask_file"] else None
            )
            pose = (
                self._child_path(self.data, row["pose_file"])
                if row["pose_file"] else None
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HistoryError(f"保存した履歴が壊れています: {row['id']}") from exc
        return HistoryEntry(
            id=row["id"], created_at=row["created_at"],
            prompt_id=row["prompt_id"], workflow_id=row["workflow_id"],
            kind=row["kind"], request_text=row["request_text"],
            parameters=parameters, images=images,
            reference_image=reference, legacy=bool(row["legacy"]),
            mask_image=mask, pose_image=pose,
        )

    def list_entries(self, limit: int = 200) -> list[HistoryEntry]:
        if not isinstance(limit, int) or not 1 <= limit <= 2000:
            raise HistoryError("履歴の取得件数は1～2000です")
        with self._connection() as con:
            rows = con.execute(
                "SELECT * FROM generations ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._read_row(row) for row in rows]

    def get(self, entry_id: str) -> HistoryEntry | None:
        with self._connection() as con:
            row = con.execute("SELECT * FROM generations WHERE id = ?", (entry_id,)).fetchone()
        return self._read_row(row) if row is not None else None

    def import_legacy_outputs(self, limit: int = 500) -> int:
        """Index images saved before this feature without inventing generation settings.

        Legacy entries are viewable and comparable, but are not reproducible.
        They are never overwritten, moved, or deleted.
        """
        if not 1 <= limit <= 2000:
            raise HistoryError("インポート上限は1～2000です")
        extensions = {".png", ".jpg", ".jpeg", ".webp"}
        with self._connection() as con:
            previous = con.execute("SELECT images_json FROM generations").fetchall()
        indexed: set[str] = set()
        for row in previous:
            try:
                indexed.update(json.loads(row["images_json"]))
            except (ValueError, TypeError):
                continue
        imported = 0
        candidates = sorted(
            (f for f in self.outputs.iterdir() if f.is_file() and f.suffix.lower() in extensions),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        # One database transaction instead of hundreds of fsyncs at GUI launch.
        with self._connection() as con:
            for image in candidates:
                if imported >= limit:
                    break
                relative = self._relative_output(image)
                if relative in indexed:
                    continue
                row_id = uuid.uuid4().hex
                con.execute(
                    """INSERT INTO generations
                    (id,created_at,prompt_id,workflow_id,kind,request_text,
                     parameters_json,images_json,reference_file,legacy)
                    VALUES (?,?,?,?,?,?,?,?,?,1)""",
                    (
                        row_id,
                        datetime.fromtimestamp(image.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                        "legacy:" + row_id,
                        "unknown", "legacy", "以前の生成画像（設定情報なし）",
                        "{}", json.dumps([relative]), None,
                    ),
                )
                indexed.add(relative)
                imported += 1
        return imported
