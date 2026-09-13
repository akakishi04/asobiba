"""C58: matched-storage shared-basis runtime scale sweep.

C57 showed that the current fine-grained 2x2 codebook path does not scale in
runtime, even though its serialized storage ratio converges near 0.57. C58 tests
a GPU-friendly alternative with a nearly matched storage ratio and no decode:

    W_module = W_base + A_module @ B_shared

For each width, rank = width / 16. The persistent shared projection is stored as
one concatenated matrix [W_base; B_shared], so inference uses exactly two vendor
GEMM-family operations:

1. F.linear(x, [W_base; B_shared]) -> base output + shared latent;
2. torch.addmm(base_output, latent, A_module.T) -> routed module output.

With two modules and Up-like M=2W, K=W, rank=W/16, persistent module-weight
storage is exactly 57.8125% of two independent dense module matrices. This is a
runtime/storage feasibility diagnostic only; random synthetic factors do not
establish task quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

import torch
from torch.nn import functional as F

EXPERIMENT_ID = "C58-shared-basis-runtime-scale-sweep"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
DEFAULT_FIXTURE = Path("runs/fixtures/v05-c-composition-20260921.pt")
WIDTHS = (32, 64, 128, 256, 512, 1024)
ROWS = 1728
MODULES = 2
ROUNDS = 20
ITERATIONS = 200
WARMUP = 50
VARIANTS = ("dense", "shared_basis")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _measure(fn) -> float:
    start = torch.cuda.Event(enable_timing=True)
    end = torch.cuda.Event(enable_timing=True)
    torch.cuda.synchronize()
    start.record()
    for _ in range(ITERATIONS):
        fn()
    end.record()
    end.synchronize()
    return float(start.elapsed_time(end)) / ITERATIONS


def _shared_basis_forward(
    value: torch.Tensor,
    shared_projection: torch.Tensor,
    module_a: torch.Tensor,
    output_width: int,
) -> torch.Tensor:
    projected = F.linear(value, shared_projection, None)
    base_output = projected[:, :output_width]
    latent = projected[:, output_width:]
    return torch.addmm(base_output, latent, module_a.transpose(0, 1))


def _summarize(records: list[dict]) -> dict:
    points: dict[str, dict] = {}
    for width in WIDTHS:
        subset = [record for record in records if int(record["width"]) == width]
        table = {
            (int(record["module_index"]), int(record["round"]), str(record["variant"])):
                float(record["device_ms"])
            for record in subset
        }
        values = {
            variant: [
                table[module_index, round_index, variant]
                for module_index in range(MODULES)
                for round_index in range(ROUNDS)
            ]
            for variant in VARIANTS
        }
        ratios = []
        for module_index in range(MODULES):
            for round_index in range(ROUNDS):
                ratios.append(
                    table[module_index, round_index, "shared_basis"]
                    / table[module_index, round_index, "dense"]
                )
        points[str(width)] = {
            "device_ms": {name: _stats(samples) for name, samples in values.items()},
            "shared_basis_over_dense": {
                **_stats(ratios),
                "numerator_faster_samples": sum(value < 1.0 for value in ratios),
                "numerator_slower_samples": sum(value > 1.0 for value in ratios),
            },
        }
    return {"points": points}


@torch.inference_mode()
def run(*, protected: Path, fixture: Path, c57_summary: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C58 requires CUDA")

    c57 = json.loads(c57_summary.read_text(encoding="utf-8"))
    if c57.get("experiment_id") != "C57-codebook-runtime-scale-sweep" or c57.get("status") != "PASS":
        raise RuntimeError("C58 requires accepted C57 summary")
    if tuple(int(value) for value in c57.get("widths", ())) != WIDTHS:
        raise RuntimeError("C58 requires the accepted 32-1024 C57 sweep")

    protected_before = _sha256(protected)
    fixture_hash = _sha256(fixture)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    generator = torch.Generator(device="cpu").manual_seed(20260913)
    records: list[dict] = []
    structures: dict[str, dict] = {}
    max_gaps: dict[str, dict] = {}
    total = len(WIDTHS) * MODULES * ROUNDS * len(VARIANTS)
    completed = 0

    for width in WIDTHS:
        k = width
        m = 2 * width
        rank = width // 16
        if rank <= 0:
            raise RuntimeError("invalid C58 rank")

        scale = 1.0 / math.sqrt(k)
        base = torch.randn(m, k, generator=generator, dtype=torch.float32) * scale
        shared_b = torch.randn(rank, k, generator=generator, dtype=torch.float32) * (scale * 0.2)
        module_as = [
            torch.randn(m, rank, generator=generator, dtype=torch.float32) * 0.2
            for _ in range(MODULES)
        ]

        shared_projection = torch.cat((base, shared_b), dim=0).to(device)
        module_as = [value.to(device) for value in module_as]
        base = base.to(device)
        shared_b = shared_b.to(device)
        materialized = [
            base + module_a @ shared_b
            for module_a in module_as
        ]

        dense_bytes = MODULES * m * k * 4
        shared_projection_bytes = int(shared_projection.numel() * shared_projection.element_size())
        module_a_bytes = sum(int(value.numel() * value.element_size()) for value in module_as)
        representation_bytes = shared_projection_bytes + module_a_bytes
        representation_ratio = representation_bytes / dense_bytes
        expected_ratio = 0.578125
        if abs(representation_ratio - expected_ratio) > 1e-12:
            raise RuntimeError(f"unexpected C58 storage ratio: {representation_ratio}")

        structures[str(width)] = {
            "input_width": k,
            "output_width": m,
            "rank": rank,
            "rows": ROWS,
            "module_count": MODULES,
            "dense_module_bytes": dense_bytes,
            "shared_projection_bytes": shared_projection_bytes,
            "module_specific_a_bytes": module_a_bytes,
            "representation_bytes": representation_bytes,
            "representation_ratio": representation_ratio,
            "theoretical_extra_matmul_flop_fraction_vs_dense": 0.09375,
        }

        value = torch.randn(ROWS, k, generator=generator, dtype=torch.float32).to(device)
        max_gaps[str(width)] = {}

        for module_index in range(MODULES):
            dense_weight = materialized[module_index]
            module_a = module_as[module_index]
            dense_call = lambda v=value, w=dense_weight: F.linear(v, w, None)
            basis_call = lambda v=value, sp=shared_projection, a=module_a, m_=m: _shared_basis_forward(v, sp, a, m_)

            dense_out = dense_call()
            basis_out = basis_call()
            torch.cuda.synchronize()
            torch.testing.assert_close(basis_out, dense_out, rtol=1e-4, atol=2e-5)
            max_gaps[str(width)][str(module_index)] = float((basis_out - dense_out).abs().max().item())

            calls = {"dense": dense_call, "shared_basis": basis_call}
            for variant in VARIANTS:
                for _ in range(WARMUP):
                    calls[variant]()
            torch.cuda.synchronize()

            for round_index in range(ROUNDS):
                order = VARIANTS if round_index % 2 == 0 else tuple(reversed(VARIANTS))
                for variant in order:
                    timing = _measure(calls[variant])
                    records.append({
                        "width": width,
                        "module_index": module_index,
                        "round": round_index,
                        "variant": variant,
                        "device_ms": timing,
                    })
                    completed += 1
                print(
                    f"[C58] width={width} module={module_index} round={round_index + 1}/{ROUNDS} "
                    f"checked ({completed}/{total})",
                    flush=True,
                )

    protected_after = _sha256(protected)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C58")

    summary = _summarize(records)
    ratio_curve = {
        str(width): float(summary["points"][str(width)]["shared_basis_over_dense"]["median"])
        for width in WIDTHS
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "matched-storage shared-input-basis runtime scale feasibility diagnostic",
        "widths": list(WIDTHS),
        "representation": "W_module = W_base + A_module @ B_shared",
        "execution": "one shared F.linear on [W_base; B_shared] plus one addmm with A_module",
        "structures": structures,
        "summary": summary,
        "shared_basis_over_dense_median_curve": ratio_curve,
        "max_abs_output_gaps": max_gaps,
        "rounds": ROUNDS,
        "iterations_per_sample": ITERATIONS,
        "warmup": WARMUP,
        "fixture_sha256": fixture_hash,
        "C57_summary_sha256": _sha256(c57_summary),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "not_run",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "synthetic factors test runtime/storage feasibility only",
            "task quality and approximation capacity are not measured in C58",
            "float32 factors are used to keep arithmetic comparable with current V5-C diagnostics",
            "C58 cannot establish Gate C pass",
        ],
        "records": records,
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--c57-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected=args.protected_result,
        fixture=args.fixture,
        c57_summary=args.c57_summary,
        output_dir=args.output_dir,
    )
    display = {key: value for key, value in result.items() if key != "records"}
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C58 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
