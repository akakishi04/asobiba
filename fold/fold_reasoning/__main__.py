"""Offline scheduler demo and benchmark; never trains or downloads on import."""
import argparse
from pathlib import Path
import sys
import torch
from .demo import demo, benchmark, write_report


def main(argv=None):
    p = argparse.ArgumentParser(description="FOLD structural-reasoning reference scaffold")
    p.add_argument("command", choices=("demo", "benchmark"))
    p.add_argument("--budget", choices=("fast", "normal", "deep"), default="normal")
    p.add_argument("--trials", type=int, default=20)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    p.add_argument("--output", type=Path, help="New report path; existing files are not overwritten")
    args = p.parse_args(argv)
    try:
        if args.device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA requested but unavailable; use --device cpu or install a CUDA build")
        device = args.device
        report = demo(args.budget, device) if args.command == "demo" else benchmark(args.trials, device)
        print(write_report(report, args.output))
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
