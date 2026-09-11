"""Fast owner-retrieval evaluation with shared prompt computation.

The legacy evaluator is deliberately simple and scores every owner candidate by
re-running the full prompt.  That is useful as a reference implementation but
becomes very expensive for 8-16 KiB extrapolation prompts.  This module keeps the
same candidate score definition while evaluating each prompt exactly once, then
branches the recurrent/KV state only for the few candidate-name bytes.

Progress is written to stderr so JSON stdout/output-file behavior remains clean.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import sys
import time
from pathlib import Path

import torch

from .data import json_text
from .long_memory_benchmark import (
    DEFAULT_COUNTERFACTUAL_SEED,
    NAMES,
    OwnerExample,
    _checkpoint_info,
    load_validation,
    make_counterfactuals,
)
from .model import BOS, PAD, FoldLanguageModel
from .runner import device_for


def _repeat_state(state: dict, repeats: int) -> dict:
    """Repeat each example state contiguously for candidate branching."""
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    repeated = {
        "position": state["position"],
        "kv": [],
    }
    for cache in state["kv"]:
        if cache is None:
            repeated["kv"].append(None)
        else:
            repeated["kv"].append(tuple(part.repeat_interleave(repeats, dim=0) for part in cache))
    for key in ("W", "b"):
        if key in state:
            repeated[key] = state[key].repeat_interleave(repeats, dim=0)
    return repeated


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _emit_progress(done: int, total: int, started: float) -> None:
    elapsed = time.perf_counter() - started
    rate = done / elapsed if elapsed > 0 else 0.0
    eta = (total - done) / rate if rate > 0 else 0.0
    pct = 100.0 * done / total
    print(
        f"[{done:>5}/{total}] {pct:6.1f}% | elapsed {_format_duration(elapsed)} "
        f"| ETA {_format_duration(eta)} | {rate:.2f} ex/s",
        file=sys.stderr,
        flush=True,
    )


@torch.inference_mode()
def evaluate_owner_candidates_shared_prefix(
    checkpoint: Path,
    examples: list[OwnerExample],
    *,
    device_name: str = "auto",
    batch_examples: int = 16,
    mistake_limit: int = 10,
    progress_every: int = 32,
    progress: bool = True,
) -> dict:
    """Score the fixed owner set while computing each long prompt only once."""
    if batch_examples <= 0 or mistake_limit < 0:
        raise ValueError("batch_examples must be positive and mistake_limit nonnegative")
    if progress_every <= 0:
        raise ValueError("progress_every must be positive")
    if not examples:
        raise ValueError("examples must be nonempty")

    ckpt, config = _checkpoint_info(checkpoint)
    device = device_for(device_name)
    torch.set_num_threads(ckpt["config"]["train"]["cpu_threads"])
    model = FoldLanguageModel(config).to(device).eval()
    model.load_state_dict(ckpt["model"])

    groups: dict[int, list[tuple[bytes, OwnerExample]]] = defaultdict(list)
    for example in examples:
        raw = example.prompt.encode("utf-8")
        groups[len(raw)].append((raw, example))

    candidate_bytes = [name.encode("utf-8") for name in NAMES]
    candidate_count = len(candidate_bytes)
    max_name_len = max(len(value) for value in candidate_bytes)
    first_bytes = torch.tensor([value[0] for value in candidate_bytes], dtype=torch.long, device=device)

    tail_len = max_name_len - 1
    tail_inputs_cpu = []
    tail_targets_cpu = []
    tail_mask_cpu = []
    for value in candidate_bytes:
        inputs = list(value[:-1]) + [PAD] * (tail_len - len(value[:-1]))
        targets = list(value[1:]) + [PAD] * (tail_len - len(value[1:]))
        mask = [1.0] * len(value[1:]) + [0.0] * (tail_len - len(value[1:]))
        tail_inputs_cpu.append(inputs)
        tail_targets_cpu.append(targets)
        tail_mask_cpu.append(mask)
    tail_inputs_template = torch.tensor(tail_inputs_cpu, dtype=torch.long, device=device)
    tail_targets_template = torch.tensor(tail_targets_cpu, dtype=torch.long, device=device)
    tail_mask_template = torch.tensor(tail_mask_cpu, dtype=torch.float32, device=device)

    correct = 0
    original_owner_predictions = 0
    total_done = 0
    margins: list[float] = []
    mistakes: list[dict] = []
    started = time.perf_counter()
    next_progress = progress_every

    for _, group in sorted(groups.items()):
        for start in range(0, len(group), batch_examples):
            batch = group[start:start + batch_examples]
            batch_size = len(batch)
            prompt_tokens = torch.tensor(
                [[BOS] + list(prefix_bytes) for prefix_bytes, _ in batch],
                dtype=torch.long,
                device=device,
            )
            prompt_logits, prompt_state = model(prompt_tokens)
            prompt_log_probs = prompt_logits[:, -1, :].float().log_softmax(-1)
            scores = prompt_log_probs[:, first_bytes].clone()

            if tail_len:
                branch_state = _repeat_state(prompt_state, candidate_count)
                tail_inputs = tail_inputs_template.repeat(batch_size, 1)
                tail_targets = tail_targets_template.repeat(batch_size, 1)
                tail_mask = tail_mask_template.repeat(batch_size, 1)
                tail_logits, _ = model(tail_inputs, branch_state)
                tail_log_probs = tail_logits.float().log_softmax(-1)
                gathered = tail_log_probs.gather(-1, tail_targets.unsqueeze(-1)).squeeze(-1)
                tail_scores = (gathered * tail_mask).sum(-1).view(batch_size, candidate_count)
                scores += tail_scores

            top_values, top_indices = scores.topk(2, dim=1)
            top_values_cpu = top_values.cpu()
            top_indices_cpu = top_indices.cpu()
            for i, (_, example) in enumerate(batch):
                predicted = NAMES[int(top_indices_cpu[i, 0])]
                margin = float(top_values_cpu[i, 0] - top_values_cpu[i, 1])
                total_done += 1
                margins.append(margin)
                if predicted == example.expected:
                    correct += 1
                if example.original_owner is not None and predicted == example.original_owner:
                    original_owner_predictions += 1
                if predicted != example.expected and len(mistakes) < mistake_limit:
                    row = {
                        "expected": example.expected,
                        "predicted": predicted,
                        "margin": margin,
                    }
                    if example.original_owner is not None:
                        row = {
                            "old_fact": example.original_owner,
                            "new_fact": example.expected,
                            "predicted": predicted,
                            "margin": margin,
                        }
                    mistakes.append(row)

            if progress and (total_done >= next_progress or total_done == len(examples)):
                if device.type == "cuda":
                    torch.cuda.synchronize(device)
                _emit_progress(total_done, len(examples), started)
                while next_progress <= total_done:
                    next_progress += progress_every

    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - started

    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_step": ckpt["step"],
        "memory": config.memory,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "local_attention_window": config.window,
        "examples": total_done,
        "correct": correct,
        "accuracy": correct / total_done,
        "chance_accuracy": 1 / len(NAMES),
        "mean_top1_margin": sum(margins) / len(margins),
        "elapsed_seconds": elapsed,
        "evaluation_mode": "shared-prefix-state-branch-v1",
        "first_mistakes": mistakes,
    }
    if any(example.original_owner is not None for example in examples):
        result["original_owner_prediction_rate"] = original_owner_predictions / total_done
    return result


def _write_result(result: dict, output: Path | None) -> None:
    text = json_text(result)
    if output is not None:
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared-prefix FOLD-R owner-retrieval evaluator")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--batch-examples", type=int, default=16)
    parser.add_argument("--counterfactual", action="store_true")
    parser.add_argument("--counterfactual-seed", type=int, default=DEFAULT_COUNTERFACTUAL_SEED)
    parser.add_argument("--progress-every", type=int, default=32)
    parser.add_argument("--quiet-progress", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    examples = load_validation(args.validation)
    replacement_counts = None
    if args.counterfactual:
        _, config = _checkpoint_info(args.checkpoint)
        examples, replacement_counts = make_counterfactuals(
            examples,
            seed=args.counterfactual_seed,
            local_window=config.window,
        )
    result = evaluate_owner_candidates_shared_prefix(
        args.checkpoint,
        examples,
        device_name=args.device,
        batch_examples=args.batch_examples,
        progress_every=args.progress_every,
        progress=not args.quiet_progress,
    )
    if replacement_counts is not None:
        result["counterfactual_seed"] = args.counterfactual_seed
        result["replacement_counts"] = replacement_counts
    _write_result(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
