"""C82: production Shared-Basis serialized-checkpoint artifact gate.

C81 accepted the actual production GEMM-native forward/resident-memory gate at
large widths. C82 isolates the remaining production storage question: does the
real ``torch.save(state_dict)`` artifact preserve the expected Shared-Basis size
advantage, and does it round-trip exactly without storing materialized effective
routed weights?

The benchmark uses width3072 as a representative large shape. Artifacts are
written, measured, hashed, reloaded with ``weights_only=True``, checked tensor by
tensor, and deleted to avoid leaving multi-GB temporary files behind.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

import torch

from fold_lm.v05.modules import LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_large_shape_runtime import (
    PROFILES,
    _allocate_shared,
    _make_dense_reference,
    _storage_bytes,
)

EXPERIMENT_ID = "C82-shared-basis-production-serialized-artifact"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
WIDTH = 3072
SLOTS = 20
MODULES = 2
HIDDEN_MULT = 2
MAX_SERIALIZED_RATIO = 0.83


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _rank(profile: str) -> int:
    numerator, denominator = PROFILES[profile]
    value = WIDTH * numerator
    if value % denominator:
        raise RuntimeError(f"non-integral C82 rank for profile={profile}")
    return value // denominator


def _state_dict_exact(module, loaded: dict[str, torch.Tensor]) -> bool:
    source = module.state_dict()
    if set(source) != set(loaded):
        return False
    for key, tensor in source.items():
        candidate = loaded[key]
        if tuple(candidate.shape) != tuple(tensor.shape) or candidate.dtype != tensor.dtype:
            return False
        if not torch.equal(candidate, tensor.detach().cpu()):
            return False
    return True


def _save_measure_reload(module, path: Path) -> dict:
    torch.save(module.state_dict(), path)
    size = int(path.stat().st_size)
    digest = _sha256(path)
    loaded = torch.load(path, map_location="cpu", weights_only=True)
    exact = _state_dict_exact(module, loaded)
    keys = sorted(str(key) for key in loaded)
    del loaded
    path.unlink()
    return {
        "serialized_bytes": size,
        "sha256": digest,
        "roundtrip_exact": exact,
        "state_dict_keys": keys,
    }


def run(*, protected_result_path: Path, c81_summary_path: Path, output_dir: Path) -> dict:
    c81 = json.loads(c81_summary_path.read_text(encoding="utf-8"))
    if c81.get("experiment_id") != "C81-shared-basis-production-large-shape-runtime":
        raise RuntimeError("C82 requires C81 summary")
    if c81.get("status") != "PASS" or not bool(
        c81.get("summary", {}).get("production_runtime_gate_passed")
    ):
        raise RuntimeError("C82 requires accepted C81 production runtime gate")

    protected_before = _sha256(protected_result_path)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config = LearnedCoreConfig(
        width=WIDTH, slots=SLOTS, modules=MODULES, hidden_mult=HIDDEN_MULT
    )

    first_rank = _rank("lean")
    first_shared = _allocate_shared(config, first_rank, device)
    dense = _make_dense_reference(first_shared, device)
    dense_resident = _storage_bytes(dense)
    dense_info = _save_measure_reload(dense, output_dir / "dense-state.pt")
    del dense, first_shared
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    records = []
    for index, profile in enumerate(PROFILES, start=1):
        rank = _rank(profile)
        shared = _allocate_shared(config, rank, device)
        shared_resident = _storage_bytes(shared)
        info = _save_measure_reload(shared, output_dir / f"shared-{profile}.pt")
        serialized_ratio = info["serialized_bytes"] / dense_info["serialized_bytes"]
        resident_ratio = shared_resident / dense_resident
        forbidden = [
            key for key in info["state_dict_keys"]
            if "module_set" in key or "materialized" in key or "effective_weight" in key
        ]
        record = {
            "profile": profile,
            "rank": rank,
            "rank_fraction": rank / WIDTH,
            "dense_serialized_bytes": dense_info["serialized_bytes"],
            "shared_serialized_bytes": info["serialized_bytes"],
            "serialized_ratio": serialized_ratio,
            "dense_resident_bytes": dense_resident,
            "shared_resident_bytes": shared_resident,
            "resident_ratio": resident_ratio,
            "dense_roundtrip_exact": dense_info["roundtrip_exact"],
            "shared_roundtrip_exact": info["roundtrip_exact"],
            "shared_artifact_sha256": info["sha256"],
            "forbidden_materialized_state_keys": forbidden,
        }
        records.append(record)
        print(
            f"[C82] profile={profile} rank={rank} "
            f"serialized={serialized_ratio:.4f} resident={resident_ratio:.4f} "
            f"roundtrip={bool(info['roundtrip_exact'])} ({index}/{len(PROFILES)})",
            flush=True,
        )
        del shared
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C82")

    all_serialized = all(float(row["serialized_ratio"]) <= MAX_SERIALIZED_RATIO for row in records)
    all_roundtrip = bool(dense_info["roundtrip_exact"]) and all(
        bool(row["shared_roundtrip_exact"]) for row in records
    )
    no_materialized = all(not row["forbidden_materialized_state_keys"] for row in records)
    summary = {
        "width": WIDTH,
        "profiles": {name: list(value) for name, value in PROFILES.items()},
        "serialized_ratio_ceiling": MAX_SERIALIZED_RATIO,
        "dense_serialized_bytes": dense_info["serialized_bytes"],
        "dense_artifact_sha256": dense_info["sha256"],
        "all_serialized_ratios_within_ceiling": all_serialized,
        "all_state_dict_roundtrips_exact": all_roundtrip,
        "no_materialized_effective_weight_keys": no_materialized,
        "records": records,
        "production_serialized_artifact_gate_passed": (
            all_serialized and all_roundtrip and no_materialized
        ),
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "actual production state_dict serialized-artifact gate",
        "summary": summary,
        "C81_summary_sha256": _sha256(c81_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "default_dense_runtime_changed": False,
        "gate_c_candidate": False,
        "limitations": [
            "C82 measures width3072 rather than retaining multi-GB width5120 checkpoint files",
            "temporary artifacts are deleted after size/hash/round-trip verification",
            "state_dict serialization uses the installed PyTorch torch.save format",
            "C82 is a storage artifact gate, not a fresh quality/runtime experiment",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c81-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c81_summary_path=args.c81_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["summary"] = dict(result["summary"])
    display["summary"]["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C82 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
