"""Named, local character-description library, independent of generation history."""
from __future__ import annotations

import sqlite3
import unicodedata
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .character_refs import normalize_approved


class FeatureExistsError(ValueError):
    """A named feature already exists; overwrite requires explicit approval."""


@dataclass(frozen=True)
class SavedFeature:
    name: str
    traits: str
    updated_at: str


def normalize_name(value):
    if not isinstance(value, str):
        raise ValueError("特徴名を入力してください")
    clean = unicodedata.normalize("NFC", value.strip())
    if not 1 <= len(clean) <= 80 or any(ord(c) < 32 or ord(c) == 127 for c in clean):
        raise ValueError("特徴名は1～80文字、1行で入力してください")
    return clean


class CharacterFeatureStore:
    def __init__(self, database: Path):
        self.database = Path(database)

    @contextmanager
    def _connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=5)) as con, con:
            con.execute("""CREATE TABLE IF NOT EXISTS features (
                name_key TEXT PRIMARY KEY, name TEXT NOT NULL,
                traits TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            yield con

    def save(self, name, traits, *, overwrite=False):
        name = normalize_name(name)
        traits = normalize_approved(traits)
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as con:
            if overwrite:
                con.execute("""INSERT INTO features VALUES (?, ?, ?, ?)
                    ON CONFLICT(name_key) DO UPDATE SET name=excluded.name,
                    traits=excluded.traits, updated_at=excluded.updated_at""",
                            (name.casefold(), name, traits, now))
            else:
                try:
                    con.execute("INSERT INTO features VALUES (?, ?, ?, ?)",
                                (name.casefold(), name, traits, now))
                except sqlite3.IntegrityError as exc:
                    raise FeatureExistsError("同じ名前のキャラ特徴が既にあります") from exc
        return SavedFeature(name, traits, now)

    def list(self):
        with self._connection() as con:
            rows = con.execute("SELECT name, traits, updated_at FROM features ORDER BY updated_at DESC, name_key").fetchall()
        return [SavedFeature(*row) for row in rows]

    def delete(self, name):
        key = normalize_name(name).casefold()
        with self._connection() as con:
            return con.execute("DELETE FROM features WHERE name_key=?", (key,)).rowcount == 1
