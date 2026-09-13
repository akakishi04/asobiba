"""C91 selected hidden=4 router large-width runtime/VRAM gate."""
from __future__ import annotations
import argparse, gc, hashlib, json, statistics, time
from pathlib import Path
import torch
from fold_lm.v05_benchmarks.gate_d_c91_large_router_helpers import HIDDEN_WIDTH, WIDTHS, measure

EXPERIMENT_ID = "C91-v5d-selected-router-large-width-runtime-vram"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261141, 20261142, 20261143)
MIN_ACC = 0.995
MIN_RECALL = 0.99
MAX_RUNTIME = 0.80
MAX_ROUTER_CORE = 0.01
MAX_ROUTER_VRAM_GIB = 0.05
GIB = 1024 ** 3


def _sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _stats(xs):
    return {"mean": statistics.mean(xs), "median": statistics.median(xs), "min": min(xs), "max": max(xs)}


def run(protected_result_path: Path, c90_summary_path: Path, output_dir: Path):
    c90 = json.loads(c90_summary_path.read_text(encoding="utf-8"))
    s90 = c90.get("summary", {})
    if c90.get("experiment_id") != "C90-v5d-router-hidden-width-frontier" or c90.get("status") != "PASS":
        raise RuntimeError("C91 requires valid C90")
    if not bool(s90.get("router_capacity_gate_passed")) or int(s90.get("selected_hidden_width", -1)) != HIDDEN_WIDTH:
        raise RuntimeError("C91 requires selected hidden_width=4")
    if not torch.cuda.is_available():
        raise RuntimeError("C91 requires CUDA")
    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    records = []
    total = len(WIDTHS) * len(SEEDS)
    done = 0
    for width in WIDTHS:
        for seed in SEEDS:
            gc.collect(); torch.cuda.empty_cache()
            row = measure(width, device, seed)
            row["seed"] = seed
            records.append(row); done += 1
            print(f"[C91] width={width} seed={seed} ({done}/{total}) action={row['action_accuracy']:.6f} device={row['learned_over_fixed_device']['median']:.4f} wall={row['learned_over_fixed_wall']['median']:.4f} router/core={row['router_over_core_persistent_ratio']:.6f} vram={row['router_device_free_vram_cost_bytes']/GIB:.4f}GiB", flush=True)
    after = _sha(protected_result_path)
    if after != before:
        raise RuntimeError("protected C37 result changed during C91")
    acc = [float(r["action_accuracy"]) for r in records]
    rec = [float(r["minimum_class_recall"]) for r in records]
    dev = [float(r["learned_over_fixed_device"]["median"]) for r in records]
    wall = [float(r["learned_over_fixed_wall"]["median"]) for r in records]
    rc = [float(r["router_over_core_persistent_ratio"]) for r in records]
    vg = [float(r["router_device_free_vram_cost_bytes"])/GIB for r in records]
    summary = {
        "widths": list(WIDTHS), "fresh_seeds": list(SEEDS), "selected_hidden_width": HIDDEN_WIDTH,
        "action_accuracy": _stats(acc), "minimum_class_recall": _stats(rec),
        "learned_over_fixed_device": _stats(dev), "learned_over_fixed_wall": _stats(wall),
        "router_over_core_persistent_ratio": _stats(rc), "router_device_free_vram_cost_gib": _stats(vg),
        "all_outputs_allclose": all(bool(r["output_allclose"]) for r in records),
        "minimum_action_accuracy": MIN_ACC, "minimum_class_recall_required": MIN_RECALL,
        "maximum_runtime_ratio": MAX_RUNTIME, "maximum_router_core_persistent_ratio": MAX_ROUTER_CORE,
        "maximum_router_device_free_cost_gib": MAX_ROUTER_VRAM_GIB,
    }
    summary["selected_router_large_width_gate_passed"] = (
        min(acc) >= MIN_ACC and min(rec) >= MIN_RECALL and summary["all_outputs_allclose"]
        and max(dev) <= MAX_RUNTIME and max(wall) <= MAX_RUNTIME
        and max(rc) <= MAX_ROUTER_CORE and max(vg) <= MAX_ROUTER_VRAM_GIB
    )
    report = {"experiment_id": EXPERIMENT_ID, "stage": "V5-D", "status": "PASS", "records": records,
              "summary": summary, "C90_summary_sha256": _sha(c90_summary_path),
              "C37_result_sha256_before": before, "C37_result_sha256_after": after,
              "production_runtime_modified": False, "gate_d_candidate": True}
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    p.add_argument("--c90-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(argv)
    started = time.perf_counter()
    r = run(a.protected_result, a.c90_summary, a.output_dir)
    d = dict(r); d["records"] = "omitted; see summary.json"; d["elapsed_seconds"] = time.perf_counter()-started
    print("\n=== C91 RESULT ==="); print(json.dumps(d, indent=2, allow_nan=False)); return 0

if __name__ == "__main__": raise SystemExit(main())
