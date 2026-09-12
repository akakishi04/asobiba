from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import random
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
DEFAULT_SEED = 20260913
DEFAULT_OUTPUT = Path("runs/hf-baselines/baseline.json")

MODEL_ALIASES: dict[str, str] = {
    "tinystories-1m": "roneneldan/TinyStories-1M",
    "tinystories-3m": "roneneldan/TinyStories-3M",
    "tinystories-8m": "roneneldan/TinyStories-8M",
    "pythia-14m": "EleutherAI/pythia-14m",
    "pythia-31m": "EleutherAI/pythia-31m",
}

DEFAULT_MODELS = (
    "tinystories-1m",
    "pythia-14m",
    "pythia-31m",
)

# Deliberately tiny and self-contained. For meaningful comparisons, pass the same
# held-out text to every model with --text-file.
SMOKE_TEXT = (
    "Once upon a time, a small robot found a red box beside the road. "
    "It opened the box carefully and discovered a note inside. "
    "The note said that the safest path home followed the river. "
    "The robot remembered the instruction and continued its journey."
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark small Hugging Face causal language models without keeping "
            "their weights in the repository or persistent cache by default."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="Model aliases or Hugging Face repository ids.",
    )
    parser.add_argument(
        "--text-file",
        type=Path,
        help="UTF-8 evaluation text. If omitted, a tiny built-in smoke text is used.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON result path. The default is under ignored runs/.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Explicit Hugging Face cache directory. Without this, a temp directory is used.",
    )
    parser.add_argument(
        "--keep-cache",
        action="store_true",
        help="Keep the cache after the run. Requires --cache-dir for an explicit location.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda", "mps"),
        default="auto",
    )
    parser.add_argument(
        "--dtype",
        choices=("auto", "float32", "float16", "bfloat16"),
        default="auto",
    )
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--stride", type=int, default=256)
    parser.add_argument("--max-eval-tokens", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument(
        "--generation-prompt",
        default="Once upon a time",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--revision",
        default=None,
        help="Optional Hugging Face git revision applied to every requested model.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at the first model failure instead of recording the error and continuing.",
    )
    parser.add_argument(
        "--include-generated-text",
        action="store_true",
        help="Store generated text in the JSON in addition to its token-id hash.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve arguments and model ids without importing ML libraries or downloading weights.",
    )
    args = parser.parse_args(argv)

    if args.max_length < 2:
        parser.error("--max-length must be >= 2")
    if args.stride < 1 or args.stride > args.max_length:
        parser.error("--stride must be in [1, --max-length]")
    if args.max_eval_tokens < 2:
        parser.error("--max-eval-tokens must be >= 2")
    if args.max_new_tokens < 1:
        parser.error("--max-new-tokens must be >= 1")
    if args.keep_cache and args.cache_dir is None:
        parser.error("--keep-cache requires --cache-dir")

    return args


def resolve_model_id(name: str) -> str:
    return MODEL_ALIASES.get(name.lower(), name)


def load_eval_text(path: Path | None) -> str:
    if path is None:
        return SMOKE_TEXT
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"evaluation text is empty: {path}")
    return text


@contextmanager
def isolated_hf_cache(cache_dir: Path | None, keep_cache: bool) -> Iterable[Path]:
    temp: tempfile.TemporaryDirectory[str] | None = None
    if cache_dir is None:
        temp = tempfile.TemporaryDirectory(prefix="fold-hf-baseline-")
        cache_path = Path(temp.name)
    else:
        cache_path = cache_dir.expanduser().resolve()
        cache_path.mkdir(parents=True, exist_ok=True)

    env_names = ("HF_HOME", "HF_HUB_CACHE", "TRANSFORMERS_CACHE")
    previous = {name: os.environ.get(name) for name in env_names}
    os.environ["HF_HOME"] = str(cache_path)
    os.environ["HF_HUB_CACHE"] = str(cache_path / "hub")
    os.environ["TRANSFORMERS_CACHE"] = str(cache_path / "transformers")

    try:
        yield cache_path
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        if temp is not None and not keep_cache:
            temp.cleanup()


def _import_ml() -> tuple[Any, Any, Any, str]:
    try:
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Missing benchmark dependencies. Install torch plus transformers before running "
            "this script. No extra dependency is needed for --dry-run."
        ) from exc
    return torch, AutoModelForCausalLM, AutoTokenizer, transformers.__version__


def choose_device(torch: Any, requested: str) -> Any:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    if requested == "mps":
        mps = getattr(torch.backends, "mps", None)
        if mps is None or not mps.is_available():
            raise RuntimeError("MPS requested but unavailable")
    return torch.device(requested)


def choose_dtype(torch: Any, requested: str, device: Any) -> Any:
    if requested == "auto":
        return torch.float16 if device.type == "cuda" else torch.float32
    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[requested]


def synchronize(torch: Any, device: Any) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps" and hasattr(torch.mps, "synchronize"):
        torch.mps.synchronize()


def configure_seed(torch: Any, seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def count_parameters(model: Any) -> tuple[int, int, int]:
    total = 0
    trainable = 0
    bytes_loaded = 0
    for parameter in model.parameters():
        count = parameter.numel()
        total += count
        if parameter.requires_grad:
            trainable += count
        bytes_loaded += count * parameter.element_size()
    return total, trainable, bytes_loaded


def model_context_limit(model: Any, tokenizer: Any, requested: int) -> int:
    candidates: list[int] = [requested]
    config_limit = getattr(model.config, "max_position_embeddings", None)
    if isinstance(config_limit, int) and config_limit > 0:
        candidates.append(config_limit)
    tokenizer_limit = getattr(tokenizer, "model_max_length", None)
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < 1_000_000:
        candidates.append(tokenizer_limit)
    return max(2, min(candidates))


def evaluate_nll(
    *,
    torch: Any,
    model: Any,
    tokenizer: Any,
    text: str,
    device: Any,
    max_length: int,
    stride: int,
    max_eval_tokens: int,
) -> dict[str, Any]:
    encoded = tokenizer(text, return_tensors="pt", add_special_tokens=False)
    token_ids = encoded["input_ids"]
    if token_ids.shape[1] < 2:
        raise ValueError("evaluation text produced fewer than two tokens")

    token_ids = token_ids[:, : max_eval_tokens + 1]
    sequence_length = int(token_ids.shape[1])
    context_limit = model_context_limit(model, tokenizer, max_length)
    stride = min(stride, context_limit)

    total_nll = 0.0
    predicted_tokens = 0
    windows = 0
    previous_end = 0

    synchronize(torch, device)
    start = time.perf_counter()
    with torch.inference_mode():
        for begin in range(0, sequence_length, stride):
            end = min(begin + context_limit, sequence_length)
            target_length = end - previous_end
            if target_length <= 0:
                break

            input_ids = token_ids[:, begin:end].to(device)
            labels = input_ids.clone()
            if target_length < labels.shape[1]:
                labels[:, :-target_length] = -100

            outputs = model(input_ids=input_ids, labels=labels)
            valid = int((labels[:, 1:] != -100).sum().item())
            if valid > 0:
                total_nll += float(outputs.loss.detach().cpu()) * valid
                predicted_tokens += valid
                windows += 1

            previous_end = end
            if end >= sequence_length:
                break

    synchronize(torch, device)
    elapsed = time.perf_counter() - start
    if predicted_tokens == 0:
        raise RuntimeError("no prediction targets were evaluated")

    mean_nll = total_nll / predicted_tokens
    perplexity = math.exp(mean_nll) if mean_nll < 700 else math.inf
    return {
        "source_tokens": sequence_length,
        "predicted_tokens": predicted_tokens,
        "windows": windows,
        "context_length": context_limit,
        "stride": stride,
        "nll_nats": total_nll,
        "mean_nll_per_model_token": mean_nll,
        "perplexity_model_token": perplexity,
        "elapsed_seconds": elapsed,
        "predicted_tokens_per_second": predicted_tokens / elapsed if elapsed > 0 else None,
        "comparability_note": (
            "Per-token NLL/perplexity depends on each model tokenizer; use the same raw text "
            "and do not treat tokenizer-specific perplexities as perfectly interchangeable."
        ),
    }


def benchmark_generation(
    *,
    torch: Any,
    model: Any,
    tokenizer: Any,
    prompt: str,
    device: Any,
    max_new_tokens: int,
    include_text: bool,
) -> dict[str, Any]:
    batch = tokenizer(prompt, return_tensors="pt")
    batch = {key: value.to(device) for key, value in batch.items()}
    input_tokens = int(batch["input_ids"].shape[1])

    eos_token_id = tokenizer.eos_token_id
    pad_token_id = tokenizer.pad_token_id
    if pad_token_id is None:
        pad_token_id = eos_token_id

    synchronize(torch, device)
    start = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **batch,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            use_cache=True,
            pad_token_id=pad_token_id,
            eos_token_id=eos_token_id,
        )
    synchronize(torch, device)
    elapsed = time.perf_counter() - start

    generated_ids = generated[0].detach().cpu().tolist()
    new_token_count = max(0, len(generated_ids) - input_tokens)
    digest = hashlib.sha256(
        json.dumps(generated_ids, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result: dict[str, Any] = {
        "prompt_tokens": input_tokens,
        "generated_tokens": new_token_count,
        "elapsed_seconds": elapsed,
        "generated_tokens_per_second": new_token_count / elapsed if elapsed > 0 else None,
        "generated_token_ids_sha256": digest,
    }
    if include_text:
        result["text"] = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return result


def cuda_peak(torch: Any, device: Any) -> dict[str, int] | None:
    if device.type != "cuda":
        return None
    return {
        "allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "reserved_bytes": int(torch.cuda.max_memory_reserved(device)),
    }


def device_metadata(torch: Any, device: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "type": device.type,
        "torch_version": torch.__version__,
        "cuda_runtime": getattr(torch.version, "cuda", None),
    }
    if device.type == "cuda":
        metadata["name"] = torch.cuda.get_device_name(device)
        metadata["capability"] = list(torch.cuda.get_device_capability(device))
    return metadata


def benchmark_model(
    *,
    torch: Any,
    AutoModelForCausalLM: Any,
    AutoTokenizer: Any,
    transformers_version: str,
    model_id: str,
    cache_path: Path,
    text: str,
    device: Any,
    dtype: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)

    common: dict[str, Any] = {
        "cache_dir": str(cache_path),
        "trust_remote_code": False,
    }
    if args.revision is not None:
        common["revision"] = args.revision

    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id, **common)
    major_version = int(transformers_version.split(".", 1)[0])
    dtype_kwargs = {"dtype": dtype} if major_version >= 5 else {"torch_dtype": dtype}
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        **dtype_kwargs,
        **common,
    )
    model.to(device)
    model.eval()
    synchronize(torch, device)
    load_seconds = time.perf_counter() - load_start

    try:
        total_parameters, trainable_parameters, parameter_bytes = count_parameters(model)
        eval_result = evaluate_nll(
            torch=torch,
            model=model,
            tokenizer=tokenizer,
            text=text,
            device=device,
            max_length=args.max_length,
            stride=args.stride,
            max_eval_tokens=args.max_eval_tokens,
        )
        generation_result = benchmark_generation(
            torch=torch,
            model=model,
            tokenizer=tokenizer,
            prompt=args.generation_prompt,
            device=device,
            max_new_tokens=args.max_new_tokens,
            include_text=args.include_generated_text,
        )
        return {
            "model_id": model_id,
            "requested_revision": args.revision,
            "resolved_commit": getattr(model.config, "_commit_hash", None),
            "architectures": getattr(model.config, "architectures", None),
            "vocab_size": getattr(model.config, "vocab_size", None),
            "parameter_count": total_parameters,
            "trainable_parameter_count": trainable_parameters,
            "parameter_storage_bytes_loaded_dtype": parameter_bytes,
            "loaded_dtype": str(dtype).replace("torch.", ""),
            "load_seconds_including_download": load_seconds,
            "evaluation": eval_result,
            "generation": generation_result,
            "cuda_peak_memory": cuda_peak(torch, device),
        }
    finally:
        del model
        del tokenizer
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()


def error_record(model_id: str, exc: BaseException) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def write_result(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model_ids = [resolve_model_id(name) for name in args.models]

    if args.dry_run:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "dry_run": True,
            "models": model_ids,
            "output": str(args.output),
            "cache_mode": "persistent" if args.keep_cache else "temporary",
            "cache_dir": str(args.cache_dir) if args.cache_dir else None,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    text = load_eval_text(args.text_file)
    with isolated_hf_cache(args.cache_dir, args.keep_cache) as cache_path:
        torch, AutoModelForCausalLM, AutoTokenizer, transformers_version = _import_ml()
        device = choose_device(torch, args.device)
        dtype = choose_dtype(torch, args.dtype, device)
        configure_seed(torch, args.seed)

        results: list[dict[str, Any]] = []
        for model_id in model_ids:
            try:
                results.append(
                    benchmark_model(
                        torch=torch,
                        AutoModelForCausalLM=AutoModelForCausalLM,
                        AutoTokenizer=AutoTokenizer,
                        transformers_version=transformers_version,
                        model_id=model_id,
                        cache_path=cache_path,
                        text=text,
                        device=device,
                        dtype=dtype,
                        args=args,
                    )
                )
            except Exception as exc:
                if args.fail_fast:
                    raise
                results.append(error_record(model_id, exc))

        payload = {
            "schema_version": SCHEMA_VERSION,
            "benchmark": "hf-small-causal-lm-baseline",
            "seed": args.seed,
            "evaluation_source": (
                str(args.text_file) if args.text_file is not None else "builtin-smoke-text"
            ),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "transformers_version": transformers_version,
                "device": device_metadata(torch, device),
            },
            "cache_policy": {
                "temporary_by_default": args.cache_dir is None,
                "keep_cache": args.keep_cache,
            },
            "results": results,
        }
        write_result(args.output, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
