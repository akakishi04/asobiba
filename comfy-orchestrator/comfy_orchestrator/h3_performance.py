"""Explicit, opt-in one-pass performance profiles for the H3 v1 hybrid.

Source: sepiablue-ai/minimax_h3_workflows/10eros_max_speedup_8-7-6step.json.
Only the native INT8 HQ I2VA path at 124f was benchmarked upstream.
Other quantizations, reference-only conditioning and lengths are experimental.
"""
from __future__ import annotations

from .parameters import OrchestratorError

H3_PERFORMANCE_LABELS = {
    "standard": "標準 (LCM)",
    "euler_dense": "Euler Dense (比較用)",
    "kitchen_int8": "Kitchen INT8",
    "sol": "Sol Attention + VAE",
}
H3_SOL_VAE = "minimax_h3_sol_vae_int8_convrot.safetensors"


def validate_h3_hybrid_steps(value, performance="standard") -> None:
    if not isinstance(performance, str) or performance not in H3_PERFORMANCE_LABELS:
        raise OrchestratorError("未対応のH3高速化設定です")
    valid = (8, 9, 10, 11, 12) if performance == "standard" else (6, 7, 8) if performance == "sol" else (8,)
    if isinstance(value, bool) or not isinstance(value, int) or value not in valid:
        raise OrchestratorError("H3のStepsは " + "/".join(map(str, valid)) + " から指定してください")


def _append(graph, kind, inputs):
    node_id = 910
    while str(node_id) in graph:
        node_id += 1
    key = str(node_id)
    graph[key] = {"class_type": kind, "inputs": inputs}
    return [key, 0]


def apply_h3_hybrid_performance(graph: dict, performance: str, steps: int) -> None:
    """Mutate an already copied, validated native H3 graph. Keep its bindings."""
    validate_h3_hybrid_steps(steps, performance)
    graph["9"]["inputs"].update(scheduler="simple", steps=steps, denoise=1)
    if performance == "standard":
        graph["17"]["inputs"]["sampler_name"] = "lcm"
        return
    graph["17"]["inputs"]["sampler_name"] = "euler"
    model = _append(graph, "MiniMaxH3SigmaShift", {
        "model": ["6", 0], "shift_video": 12.0, "shift_audio": 3.0,
    })
    if performance in ("kitchen_int8", "sol"):
        model = _append(graph, "ModelAttentionBackend", {
            "model": model, "attention": "comfy kitchen attention",
        })
    if performance == "sol":
        model = _append(graph, "BlockSparseAttention", {
            "model": model, "selection": "sol-attn", "selection.tau": 1.3,
            "start_percent": 0.10, "end_percent": 1.0, "dense_blocks": "0,1",
            "min_tokens": 12288, "extra_tokens": 256,
            "sink_conditioning": "exact_kv_and_rows", "verbose": False,
        })
        decode = graph.get("10", {})
        if decode.get("class_type") != "VAEDecode" or decode.get("inputs", {}).get("vae") != ["11", 0]:
            raise OrchestratorError("Sol VAEには標準H3動画デコードノードが必要です")
        # Keep the conditioning encoder and audio VAE untouched.
        decode["inputs"]["vae"] = _append(graph, "VAELoader", {"vae_name": H3_SOL_VAE})
    for target in ("9", "16"):
        graph[target]["inputs"]["model"] = model.copy()
