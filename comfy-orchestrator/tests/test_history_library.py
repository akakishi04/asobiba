"""DB-wide queries, paging and non-destructive metadata mutations."""
import json
from contextlib import closing
import queue
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from comfy_orchestrator.history import HistoryStore, HistoryQuery, HistoryError
from comfy_orchestrator.history_refresh import HistoryRefresh
from comfy_orchestrator.long_video_plan import LONG_VIDEO_ID
from comfy_orchestrator.workflow_registry import H3_I2V_ID


class HistoryLibraryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.store = HistoryStore(self.root)
        self.image = self.store.outputs / "result.png"
        self.image.write_bytes(b"image")
        self.video = self.store.outputs / "result.mp4"
        self.video.write_bytes(b"video")

    def record(self, name, *, workflow="wai_t2i_basic", kind="t2i", text="", params=None, path=None):
        return self.store.record(prompt_id=name, workflow_id=workflow, kind=kind, request_text=text,
                                 parameters=params or {}, images=[path or self.image])

    def test_search_is_global_and_literal_across_saved_parameters(self):
        # Simulate a database with more entries than the former 500-row window.
        rows = [(f"r{i:04d}", f"2026-11-{1+i//100:02d}T00:00:{i%60:02d}+00:00",
                 f"prompt{i}", "wai_t2i_basic", "t2i",
                 "old hidden needle" if i == 0 else "ordinary",
                 json.dumps({"positive_prompt": "銀髪 50% _tag"} if i == 0 else {}),
                 json.dumps(["result.png"])) for i in range(650)]
        with self.store._connection() as con:
            con.executemany("""INSERT INTO generations
                (id,created_at,prompt_id,workflow_id,kind,request_text,parameters_json,images_json)
                VALUES (?,?,?,?,?,?,?,?)""", rows)
        page = self.store.query_entries(HistoryQuery(text="needle 50% _tag"))
        self.assertEqual(page.total, 1)
        self.assertEqual(page.entries[0].id, "r0000")
        self.assertEqual(self.store.query_entries(HistoryQuery(text="%' OR 1=1 --")).total, 0)
        self.assertEqual(self.store.query_entries(HistoryQuery(text="%")).total, 1)
        self.assertEqual(self.store.query_entries(HistoryQuery(text="_tag")).total, 1)

    def test_pagination_and_selection_follow_current_sort(self):
        entries = [self.record(f"test-{i}", text=f"item {i}") for i in range(7)]
        new = self.store.query_entries(HistoryQuery(limit=3))
        old = self.store.query_entries(HistoryQuery(limit=3, oldest_first=True))
        all_rows = self.store.query_entries(HistoryQuery(limit=20))
        self.assertEqual(new.total, 7)
        self.assertEqual(new.entries, all_rows.entries[:3])
        self.assertEqual(old.entries, tuple(reversed(all_rows.entries))[:3])
        target = all_rows.entries[-1].id
        selected = self.store.query_entries(HistoryQuery(limit=3), select_id=target)
        self.assertEqual(selected.offset, 6)
        self.assertEqual(selected.entries[0].id, target)
        clamped = self.store.query_entries(HistoryQuery(limit=3, offset=99))
        self.assertEqual(clamped.offset, 6)
        self.assertEqual(clamped.entries, selected.entries)

    def test_filter_categories_do_not_mix_single_and_continuous(self):
        image = self.record("image")
        video = self.record("video", workflow=H3_I2V_ID, kind="i2v", path=self.video)
        long = self.record("long", workflow=LONG_VIDEO_ID, kind="i2v", path=self.video)
        frame = self.store.record_frame(source=self.video, frame=3, image=self.image)
        for kind, entry in (("image", image), ("video", video), ("continuous", long), ("frame", frame)):
            page = self.store.query_entries(HistoryQuery(kind=kind))
            self.assertEqual([e.id for e in page.entries], [entry.id])

    def test_flags_are_atomic_reversible_and_persist_without_deleting_assets(self):
        first, second = self.record("first"), self.record("second")
        self.store.set_flags([first.id, second.id], favorite=True)
        self.assertEqual(self.store.query_entries(HistoryQuery(favorite_only=True)).total, 2)
        with self.assertRaises(HistoryError):
            self.store.set_flags([first.id, "missing"], archived=True)
        self.assertFalse(self.store.get(first.id).archived)
        self.store.set_flags([first.id, second.id], archived=True)
        reopened = HistoryStore(self.root)
        self.assertEqual(reopened.query_entries(HistoryQuery()).total, 0)
        self.assertEqual(reopened.query_entries(HistoryQuery(archived=True, favorite_only=True)).total, 2)
        self.assertTrue(self.image.is_file())
        self.assertEqual(reopened.import_legacy_outputs(), 0)
        self.assertEqual(reopened.find_by_prompt_id("first").id, first.id)
        reopened.set_flags([first.id], archived=False, favorite=False)
        self.assertEqual(reopened.query_entries(HistoryQuery()).entries[0].id, first.id)
        self.assertFalse(reopened.get(first.id).favorite)

    def test_old_database_migrates_flags_without_touching_existing_row(self):
        root = self.root / "old"
        (root / "data").mkdir(parents=True)
        database = root / "data" / "history.sqlite3"
        with closing(sqlite3.connect(database)) as con, con:
            con.execute("""CREATE TABLE generations (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, prompt_id TEXT UNIQUE NOT NULL,
                workflow_id TEXT NOT NULL, kind TEXT NOT NULL, request_text TEXT NOT NULL,
                parameters_json TEXT NOT NULL, images_json TEXT NOT NULL, reference_file TEXT,
                legacy INTEGER NOT NULL DEFAULT 0)""")
            con.execute("INSERT INTO generations VALUES (?,?,?,?,?,?,?,?,?,?)",
                        ("old", "2025-01-01T00:00:00+00:00", "p", "wai_t2i_basic",
                         "t2i", "original", "{}", '["old.png"]', None, 0))
        old = HistoryStore(root)
        row = old.get("old")
        self.assertEqual(row.request_text, "original")
        self.assertFalse(row.favorite or row.archived)
        old.set_flags(["old"], favorite=True)
        self.assertTrue(HistoryStore(root).get("old").favorite)

    def test_coalesced_queries_only_apply_latest_page(self):
        messages = queue.Queue()
        gate = threading.Event()
        seen = []
        def query_entries(query, *, select_id=None):
            seen.append((query.text, select_id))
            gate.wait(4)
            return query.text
        store = SimpleNamespace(query_entries=query_entries, import_legacy_outputs=Mock())
        service = HistoryRefresh(store, messages.put)
        service.request(query=HistoryQuery(text="a"), scan_legacy=False)
        service.request("b-id", query=HistoryQuery(text="b"), scan_legacy=False)
        service.request(query=HistoryQuery(text="c"), scan_legacy=False)
        gate.set()
        on_entries, on_error = Mock(), Mock()
        kind, first = messages.get(timeout=5)
        service.complete(*first, on_entries=on_entries, on_error=on_error)
        on_entries.assert_not_called()
        kind, final = messages.get(timeout=5)
        service.complete(*final, on_entries=on_entries, on_error=on_error)
        on_entries.assert_called_once_with("c", "b-id")
        self.assertEqual(seen, [("a", None), ("c", "b-id")])
        on_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
