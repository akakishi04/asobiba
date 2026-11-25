"""Shared validation primitives for model adapters and the orchestrator."""
from __future__ import annotations

from typing import Any


class OrchestratorError(RuntimeError):
    """An actionable configuration, protocol or execution error."""


PARAMS = {
    "positive_prompt": ("string", None, None),
    "negative_prompt": ("string", None, None),
    "width": ("integer", 64, 4096),
    "height": ("integer", 64, 4096),
    "steps": ("integer", 1, 150),
    "cfg": ("number", 0, 30),
    "seed": ("integer", 0, 9223372036854775807),
    "frames": ("integer", 1, 1000),
    "fps": ("integer", 1, 120),
    "denoise": ("number", 0, 1),
    "control_strength": ("number", 0, 2),
}
def check_param(name: str, value: Any) -> None:
    if name not in PARAMS:
        raise OrchestratorError(f"未対応の生成パラメータ: {name}")
    typ, lower, upper = PARAMS[name]
    if typ == "string":
        if not isinstance(value, str) or len(value) > 5000:
            raise OrchestratorError(f"{name} は5000文字以内の文字列です")
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (typ == "integer" and not isinstance(value, int)):
        raise OrchestratorError(f"{name} は{typ}型にしてください")
    if not lower <= value <= upper:
        raise OrchestratorError(f"{name} の範囲は {lower}～{upper} です")
    if name in ("width", "height") and value % 8:
        raise OrchestratorError(f"{name} は8の倍数にしてください")


