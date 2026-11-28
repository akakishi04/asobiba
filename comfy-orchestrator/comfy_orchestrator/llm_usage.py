"""Local, opt-in-by-operation telemetry for actual LLM server token usage.

No prompts, response text, images, URLs or credentials are persisted. The
request boundary records even invalid/retried answers. Unknown usage is NULL,
never a fabricated token estimate. Recording failure cannot stop generation.
"""
from __future__ import annotations

import csv
import sqlite3
import tempfile
import time
import uuid
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

_ACTIVE = ContextVar("llm_usage_session", default=None)
_PURPOSE = ContextVar("llm_usage_purpose", default=None)

ACTIONS = {
    "generate": "直接生成", "review": "プロンプト確認",
    "review_generate": "確認済み生成", "review_translate": "単発・翻訳",
    "review_apply": "単発・編集反映", "review_regenerate": "単発・再生成",
    "long_plan": "連続・計画", "long_translate": "連続・翻訳",
    "long_translate_all": "連続・一括翻訳", "long_apply": "連続・編集反映",
    "long_regenerate": "連続・再生成", "long_save": "連続・保存",
    "long_generate": "連続・カット生成", "long_generate_join": "連続・生成と結合",
    "long_join": "連続・結合", "replay": "履歴・再生成",
    "character_analysis": "キャラ特徴抽出", "character_revision": "キャラ説明修正",
    "cli_run": "CLI生成", "cli_review": "CLI解釈",
    "adjust_generate": "画像調整・再生成", "adjust_translate": "画像調整・翻訳",
    "adjust_apply": "画像調整・編集反映", "adjust_regenerate": "画像調整・修正指示",
    "image_compare": "画像・モデル比較",
}
MODES = {"image": "画像", "video": "動画", "continuous": "連続動画", "character": "キャラ参照"}

TOKEN_COLUMNS = ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens")
REQUEST_FIELDS = ("request_id", "operation_id", "requested_at", "provider", "route",
                  "purpose", "model", "vision", "request_status", "seconds", *TOKEN_COLUMNS)
OPERATION_FIELDS = ("operation_id", "group_id", "started_at", "finished_at", "action",
                    "mode", "workflow", "frames", "cuts", "operation_status", "recording_errors")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _dict(value):
    return value if isinstance(value, dict) else {}


def _token(value):
    # SQLite uses signed 64-bit integers; reject malformed counts and bools.
    if type(value) is int and 0 <= value <= 2**63 - 1:
        return value
    return None


def parse_usage(provider, route, reply):
    """Return actual counts only; reasoning is a subset of total output."""
    reply = _dict(reply)
    if provider == "ollama":
        values = (reply.get("prompt_eval_count"), reply.get("eval_count"), None, None)
    elif route == "/api/v1/chat":
        stats = _dict(reply.get("stats"))
        values = (stats.get("input_tokens"), stats.get("total_output_tokens"),
                  stats.get("reasoning_output_tokens"), None)
    else:
        usage = _dict(reply.get("usage"))
        values = (usage.get("prompt_tokens"), usage.get("completion_tokens"),
                  _dict(usage.get("completion_tokens_details")).get("reasoning_tokens"),
                  _dict(usage.get("prompt_tokens_details")).get("cached_tokens"))
    return dict(zip(TOKEN_COLUMNS, map(_token, values)))


@contextmanager
def inference_purpose(name):
    """The native API has no response-format schema name in the payload."""
    token = _PURPOSE.set(name)
    try:
        yield
    finally:
        _PURPOSE.reset(token)


def request_purpose(provider, payload):
    payload = _dict(payload)
    name = _dict(_dict(payload.get("response_format")).get("json_schema")).get("name")
    if isinstance(name, str) and name:
        return name[:128]
    return _PURPOSE.get() or ("ollama_plan" if provider == "ollama" else "chat")


def _has_vision(payload):
    payload = _dict(payload)
    if payload.get("images"):
        return True
    for message in payload.get("messages", ()) or ():
        content = _dict(message).get("content")
        if isinstance(content, list) and any(_dict(part).get("type") in ("image_url", "image", "input_image")
                                             for part in content):
            return True
    content = payload.get("input")
    return isinstance(content, list) and any(_dict(part).get("type") in ("image_url", "image", "input_image")
                                             for part in content)


def _notify(notify, text):
    if notify is not None:
        try:
            notify(text)
        except Exception:
            # Diagnostics may not change the original task's outcome.
            pass


# COUNT rather than COALESCE alone preserves partial and unavailable usage.
_AGG = """
    COUNT(r.request_id) AS calls,
    COALESCE(SUM(r.input_tokens), 0) AS input_tokens,
    COALESCE(SUM(r.output_tokens), 0) AS output_tokens,
    COALESCE(SUM(r.reasoning_tokens), 0) AS reasoning_tokens,
    COALESCE(SUM(r.cached_input_tokens), 0) AS cached_input_tokens,
    COUNT(r.input_tokens) AS input_measured,
    COUNT(r.output_tokens) AS output_measured,
    COUNT(r.reasoning_tokens) AS reasoning_measured,
    COUNT(r.cached_input_tokens) AS cached_measured,
    COALESCE(SUM(CASE WHEN r.request_id IS NOT NULL
                     AND (r.input_tokens IS NULL OR r.output_tokens IS NULL)
                     THEN 1 ELSE 0 END), 0) AS missing,
    COALESCE(SUM(CASE WHEN r.request_status = 'error' THEN 1 ELSE 0 END), 0) AS failed
"""


def format_count(row, key):
    count_key = {"input_tokens": "input_measured", "output_tokens": "output_measured",
                 "reasoning_tokens": "reasoning_measured", "cached_input_tokens": "cached_measured"}[key]
    calls = row["calls"]
    measured = row[count_key]
    incomplete = bool(row.get("recording_errors") or row.get("operation_status") == "running"
                      or row.get("unfinished"))
    if not calls:
        return "—" if incomplete else "0"
    if not measured:
        return "—"
    return ("≥" if measured < calls or incomplete else "") + f"{row[key]:,}"


def format_summary(row):
    suffix = f" / 未計測 {row['missing']}件" if row["missing"] else ""
    if row.get("recording_errors"):
        suffix += f" / 記録失敗 {row['recording_errors']}件"
    if row.get("unfinished"):
        suffix += f" / 未完了 {row['unfinished']}操作"
    return (f"IN {format_count(row, 'input_tokens')} / OUT {format_count(row, 'output_tokens')}"
            f" / {row['calls']}リクエスト" + suffix)


class UsageStore:
    def __init__(self, database):
        self.database = Path(database)

    @contextmanager
    def _connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=3)) as con:
            con.row_factory = sqlite3.Row
            with con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS llm_operations (
                        operation_id TEXT PRIMARY KEY, group_id TEXT NOT NULL,
                        started_at TEXT NOT NULL, finished_at TEXT,
                        action TEXT NOT NULL, mode TEXT NOT NULL, workflow TEXT NOT NULL,
                        frames INTEGER, cuts INTEGER, operation_status TEXT NOT NULL,
                        recording_errors INTEGER NOT NULL DEFAULT 0
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS llm_requests (
                        request_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL,
                        requested_at TEXT NOT NULL, provider TEXT NOT NULL, route TEXT NOT NULL,
                        purpose TEXT NOT NULL, model TEXT NOT NULL, vision INTEGER NOT NULL,
                        request_status TEXT NOT NULL, seconds REAL,
                        input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER,
                        cached_input_tokens INTEGER
                    )
                """)
                con.execute("CREATE INDEX IF NOT EXISTS llm_requests_operation ON llm_requests(operation_id)")
                con.execute("CREATE INDEX IF NOT EXISTS llm_operations_started ON llm_operations(started_at)")
                yield con

    def _begin(self, operation_id, action, mode, workflow, frames, cuts, group_id):
        with self._connection() as con:
            con.execute("""
                INSERT INTO llm_operations
                (operation_id, group_id, started_at, action, mode, workflow, frames, cuts, operation_status)
                VALUES (?,?,?,?,?,?,?,?,'running')
            """, (operation_id, group_id or operation_id, _now(), action, mode, workflow, frames, cuts))

    def _finish(self, operation_id, status, errors, group_id):
        with self._connection() as con:
            con.execute("""
                UPDATE llm_operations SET operation_status=?, finished_at=?, recording_errors=?,
                    group_id=COALESCE(?, group_id) WHERE operation_id=?
            """, (status, _now(), errors, group_id, operation_id))
            row = con.execute(f"""
                SELECT o.*, {_AGG} FROM llm_operations o
                LEFT JOIN llm_requests r ON r.operation_id=o.operation_id
                WHERE o.operation_id=? GROUP BY o.operation_id
            """, (operation_id,)).fetchone()
            return dict(row)

    def _start_request(self, operation_id, provider, route, payload, model):
        request_id = uuid.uuid4().hex
        with self._connection() as con:
            con.execute("""
                INSERT INTO llm_requests
                (request_id, operation_id, requested_at, provider, route, purpose, model, vision, request_status)
                VALUES (?,?,?,?,?,?,?,?,'running')
            """, (request_id, operation_id, _now(), provider, route, request_purpose(provider, payload),
                  str(model or _dict(payload).get("model") or "unknown")[:1024], int(_has_vision(payload))))
        return request_id

    def _finish_request(self, request_id, status, elapsed, usage):
        with self._connection() as con:
            con.execute("""
                UPDATE llm_requests SET request_status=?, seconds=?, input_tokens=?, output_tokens=?,
                    reasoning_tokens=?, cached_input_tokens=? WHERE request_id=?
            """, (status, elapsed, *(usage[key] for key in TOKEN_COLUMNS), request_id))

    def run(self, operation, *, action, mode="", workflow="", frames=None, cuts=None, group_id=None,
            notify=None):
        """Run exactly once in this worker, with independent telemetry scope."""
        operation_id = uuid.uuid4().hex
        try:
            self._begin(operation_id, action, mode, workflow, frames, cuts, group_id)
        except Exception as exc:
            _notify(notify, f"LLM使用量の記録を開始できません: {exc}")
            # If a higher-level operation has already opened a session, do not
            # mistakenly attribute the nested unrecorded work to that session.
            token = _ACTIVE.set(None)
            try:
                return operation()
            finally:
                _ACTIVE.reset(token)
        session = _Session(self, operation_id, notify)
        token = _ACTIVE.set(session)
        status = "interrupted"
        final_group = None
        try:
            result = operation()
            status = "completed"
            if action == "long_plan" and isinstance(result, dict):
                run_id = result.get("run_id")
                if isinstance(run_id, str) and run_id:
                    final_group = run_id
            return result
        finally:
            _ACTIVE.reset(token)
            try:
                row = self._finish(operation_id, status, session.errors, final_group)
                label = ACTIONS.get(action, action)
                _notify(notify, f"LLM使用量 [{label}]: " + format_summary(row))
            except Exception as exc:
                _notify(notify, f"LLM使用量の集計に失敗: {exc}")

    def report(self, *, limit=100):
        with self._connection() as con:
            total = dict(con.execute(f"SELECT {_AGG} FROM llm_requests r").fetchone())
            total["recording_errors"] = con.execute(
                "SELECT COALESCE(SUM(recording_errors),0) FROM llm_operations").fetchone()[0]
            total["operations"] = con.execute("SELECT COUNT(*) FROM llm_operations").fetchone()[0]
            total["unfinished"] = con.execute(
                "SELECT COUNT(*) FROM llm_operations WHERE operation_status='running'").fetchone()[0]
            operations = [dict(row) for row in con.execute(f"""
                SELECT o.*, {_AGG} FROM
                    (SELECT * FROM llm_operations ORDER BY started_at DESC, operation_id DESC LIMIT ?) o
                LEFT JOIN llm_requests r ON r.operation_id=o.operation_id
                GROUP BY o.operation_id ORDER BY o.started_at DESC, o.operation_id DESC
            """, (limit,))]
            purposes = [dict(row) for row in con.execute(f"""
                SELECT r.model, r.purpose, {_AGG} FROM llm_requests r
                GROUP BY r.model, r.purpose ORDER BY r.model, r.purpose
            """)]
        return {"total": total, "operations": operations, "purposes": purposes}

    def export_csv(self, path):
        path = Path(path)
        if path.resolve() == self.database.resolve() or path.suffix.lower() != ".csv":
            raise ValueError("CSVファイルを指定してください")
        # Include zero-request operations as one row with empty request fields.
        # Missing counts remain blank, and ids allow grouping reviewed runs.
        fields = (*OPERATION_FIELDS, *(key for key in REQUEST_FIELDS if key != "operation_id"))
        select = ", ".join([f"o.{key}" for key in OPERATION_FIELDS] +
                           [f"r.{key}" for key in REQUEST_FIELDS if key != "operation_id"])
        temporary = None
        try:
            with self._connection() as con, tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
                    suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                writer = csv.writer(stream)
                writer.writerow(fields)
                for row in con.execute(f"""
                    SELECT {select} FROM llm_operations o
                    LEFT JOIN llm_requests r ON r.operation_id=o.operation_id
                    ORDER BY o.started_at, o.operation_id, r.requested_at, r.request_id
                """):
                    # Model identifiers must remain text in spreadsheet apps.
                    writer.writerow(["'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r"))
                                     else v for v in row])
            temporary.replace(path)
            return path
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


class _Session:
    def __init__(self, store, operation_id, notify):
        self.store = store
        self.operation_id = operation_id
        self.notify = notify
        self.errors = 0

    def record_error(self, exc):
        self.errors += 1
        if self.errors == 1:
            _notify(self.notify, f"LLM使用量の記録に失敗（生成は継続）: {exc}")


def measured_request(provider, route, payload, model, send):
    """Measure one actual inference HTTP request, including transport errors."""
    session = _ACTIVE.get()
    if session is None:
        return send()
    request_id = None
    try:
        request_id = session.store._start_request(session.operation_id, provider, route, payload, model)
    except Exception as exc:
        session.record_error(exc)
    started = time.monotonic()
    status = "error"
    result = None
    try:
        result = send()
        status = "response"
        return result
    finally:
        if request_id is not None:
            try:
                session.store._finish_request(request_id, status, time.monotonic() - started,
                                              parse_usage(provider, route, result))
            except Exception as exc:
                session.record_error(exc)
