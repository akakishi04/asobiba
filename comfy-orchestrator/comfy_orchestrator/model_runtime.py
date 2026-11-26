"""ComfyUI/LLM memory handoff policy shared by generation and planning."""
from __future__ import annotations

from .parameters import OrchestratorError


def release_comfy_before_llm(settings, *, comfy=None, progress=None, enabled=True):
    """Respect the configured opt-out; never unload while a remote job is active."""
    if not enabled or not settings.get("free_before_llm", True):
        return
    if comfy is None:
        from .core import ComfyUI
        comfy = ComfyUI(settings)
    if progress:
        progress("ComfyUI: キューを確認してLLM処理前に生成モデルを解放")
    comfy.free_if_idle()


def cancel_before_inference(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError("LLM処理を中止しました")
