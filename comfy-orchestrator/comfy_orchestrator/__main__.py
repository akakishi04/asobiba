"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import OrchestratorError, execute, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="自然文 -> Ollama -> アンロード -> ComfyUI")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="設定ファイルのパス")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="設定とワークフローの結線をオフライン検証")
    run = sub.add_parser("run", help="自然文からComfyUI実行")
    run.add_argument("text", help="日本語などの自然文指示")
    run.add_argument("--image", type=Path, help="参照画像。画像対応Ollamaモデルとimageバインディングが必要")
    run.add_argument("--dry-run", action="store_true", help="LLM解釈まで実行しComfyUIには投入しない")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate":
            print(f"設定: OK / ワークフロー: {len(config['workflows'])}件")
            if not config["workflows"]:
                print("ワークフロー未登録。登録後に再検証してください")
        else:
            result = execute(config, args.config, args.text, args.image, args.dry_run)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OrchestratorError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
