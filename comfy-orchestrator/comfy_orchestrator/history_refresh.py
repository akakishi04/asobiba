"""Coalesced asynchronous history reads. No widget access from worker threads."""
from __future__ import annotations

import threading


class HistoryRefresh:
    def __init__(self, store, emit):
        self.store = store
        self.emit = emit
        self.running = False
        self.pending = None

    def request(self, select_id=None, *, scan_legacy=True, working=False):
        scan_legacy = scan_legacy and not working
        if self.running:
            previous = self.pending
            self.pending = (
                select_id if select_id is not None else (previous[0] if previous else None),
                scan_legacy or bool(previous and previous[1]),
            )
            return
        self.running = True

        def task():
            try:
                if scan_legacy:
                    self.store.import_legacy_outputs(limit=500)
                entries = self.store.list_entries(limit=500)
                self.emit(("history_loaded", (entries, select_id, None)))
            except Exception as exc:
                self.emit(("history_loaded", (None, select_id, str(exc))))

        threading.Thread(target=task, daemon=True).start()

    def complete(self, entries, select_id, error, *, working=False, on_entries, on_error):
        self.running = False
        if error is not None:
            on_error(error)
        pending, self.pending = self.pending, None
        if pending is not None:
            self.request(pending[0] if pending[0] is not None else select_id,
                         scan_legacy=pending[1], working=working)
        elif entries is not None:
            on_entries(entries, select_id)
