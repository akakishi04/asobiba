"""python -m fold_lm: explicit offline commands; never starts training on import."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import sys


def parser():
    p = argparse.ArgumentParser(description="FOLD-R local small-model training prototype")
    p.add_argument("--debug", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create ignored data/raw and runs directories")
    sub.add_parser("doctor", help="Print Python/PyTorch/device information")
    s = sub.add_parser("sample-data", help="Generate synthetic smoke-test data, not a research benchmark")
    s.add_argument("--output", type=Path, default=Path("data/raw/sample.jsonl"))
    s.add_argument("--documents", type=int, default=1000)
    s.add_argument("--seed", type=int, default=20260909)
    s = sub.add_parser("prepare", help="Prepare local TXT/JSONL, deduplicate, then split by document")
    s.add_argument("--input", type=Path, default=Path("data/raw"))
    s.add_argument("--val-input", type=Path)
    s.add_argument("--output", type=Path, default=Path("data/processed"))
    s.add_argument("--val-ratio", type=float, default=0.1)
    s.add_argument("--seed", type=int, default=20260909)
    s = sub.add_parser("train", help="Train from scratch, or resume --resume last.pt")
    s.add_argument("--config", type=Path)
    s.add_argument("--data", type=Path)
    s.add_argument("--out", type=Path)
    s.add_argument("--resume", type=Path)
    s.add_argument("--max-steps", type=int, help="Total optimizer-step target, not additional steps")
    s.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    s = sub.add_parser("evaluate", help="Evaluate a checkpoint on its held-out validation data")
    s.add_argument("--checkpoint", type=Path, required=True)
    s.add_argument("--data", type=Path)
    s.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    s.add_argument("--max-batches", type=int, default=0, help="0 evaluates the whole validation split")
    s = sub.add_parser("generate", help="Generate UTF-8 bytes from a locally trained checkpoint")
    s.add_argument("--checkpoint", type=Path, required=True)
    group = s.add_mutually_exclusive_group()
    group.add_argument("--prompt", default="")
    group.add_argument("--prompt-file", type=Path)
    s.add_argument("--max-new-tokens", type=int, default=200)
    s.add_argument("--temperature", type=float, default=0.8)
    s.add_argument("--top-k", type=int, default=40)
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            for path in (Path("data/raw"), Path("runs")):
                path.mkdir(parents=True, exist_ok=True)
            print("Created data/raw and runs. Put UTF-8 .txt/.jsonl files in data/raw.")
        elif args.command == "sample-data":
            if args.documents < 2:
                raise ValueError("Need at least two documents")
            rng = random.Random(args.seed)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as f:
                for i in range(args.documents):
                    a, ab, bc = rng.randint(-20, 20), rng.randint(1, 9), rng.randint(1, 9)
                    text = (f"Example {i}: A={a}. B=A+{ab}. C=B+{bc}. "
                            f"Question: C? Answer: {a + ab + bc}.\n")
                    if i % 2:
                        text = (f"例{i}。Aは{a}。BはAより{ab}大きい。CはBより{bc}大きい。"
                                f"質問：Cはいくつ？ 答え：{a + ab + bc}。")
                    f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            print(f"Wrote {args.documents} synthetic documents to {args.output}")
        elif args.command == "prepare":
            from .data import prepare, json_text
            print(json_text(prepare(args.input, args.output, val_source=args.val_input,
                                    val_ratio=args.val_ratio, seed=args.seed)))
        elif args.command == "doctor":
            import platform
            import torch
            print(json.dumps({"python": platform.python_version(), "torch": str(torch.__version__),
                              "cuda_available": torch.cuda.is_available(),
                              "cuda_runtime": torch.version.cuda,
                              "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}, indent=2))
        elif args.command == "train":
            from .runner import train
            train(config_path=args.config, data=args.data, out=args.out, resume=args.resume,
                  max_steps=args.max_steps, device_name=args.device)
        elif args.command == "evaluate":
            from .runner import evaluate_checkpoint
            print(json.dumps(evaluate_checkpoint(args.checkpoint, args.data, args.device,
                                                  args.max_batches), indent=2))
        elif args.command == "generate":
            from .runner import generate
            prompt = args.prompt_file.read_text(encoding="utf-8-sig") if args.prompt_file else args.prompt
            text = generate(args.checkpoint, prompt, max_new_tokens=args.max_new_tokens,
                            temperature=args.temperature, top_k=args.top_k,
                            seed=args.seed, device_name=args.device)
            print(prompt + text)
    except KeyboardInterrupt:
        print("Interrupted. Resume from last.pt, the last completely saved optimizer step.", file=sys.stderr)
        raise SystemExit(130)
    except (ValueError, TypeError, KeyError, OSError, ImportError, RuntimeError) as exc:
        if args.debug:
            raise
        print(f"ERROR: {exc}", file=sys.stderr)
        if isinstance(exc, ImportError):
            print("Install dependencies with: python -m pip install -r requirements-training.txt", file=sys.stderr)
        if "out of memory" in str(exc).lower():
            print("Reduce train.batch_size / train.seq_len, or use the smoke configuration.", file=sys.stderr)
        raise SystemExit(1)
