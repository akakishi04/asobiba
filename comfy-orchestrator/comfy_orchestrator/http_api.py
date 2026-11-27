"""Shared JSON HTTP transport and error normalization for local backends."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .parameters import OrchestratorError


def http_json(base: str, route: str, payload: Any = None, timeout: float = 60, allow_empty: bool = False) -> dict:
    url = base.rstrip("/") + "/" + route.lstrip("/")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    return _open_json(request, timeout, allow_empty)


class APIHTTPError(OrchestratorError):
    def __init__(self, status: int, url: str, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"HTTP {status}: {url}: {reason}")


def _open_json(request: urllib.request.Request, timeout: float, allow_empty: bool = False) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            result = json.loads(body) if body else ({} if allow_empty else None)
    except urllib.error.HTTPError as exc:
        reason = exc.read(1200).decode("utf-8", errors="replace")
        raise APIHTTPError(exc.code, request.full_url, reason) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise OrchestratorError(f"API接続またはJSONの読み込みに失敗: {request.full_url}: {exc}") from exc
    if not isinstance(result, dict):
        raise OrchestratorError(f"APIがJSONオブジェクトを返しませんでした: {request.full_url}")
    return result


def _positive_number(value: Any, label: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise OrchestratorError(f"{label} は正の数値にしてください")
    return float(value)
