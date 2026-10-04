from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.embedding_probe import (  # noqa: E402
    EmbeddingProbeError,
    probe_openai_compatible_embedding,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe an OpenAI-compatible embedding endpoint without persisting secrets or vectors."
    )
    parser.add_argument("--provider", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dimension", required=True, type=int)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--api-key-env",
        default="PLM_POC_EMBEDDING_API_KEY",
        help="Environment variable containing the provider API key.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"Required environment variable is not set: {args.api_key_env}", file=sys.stderr)
        return 2
    try:
        result = probe_openai_compatible_embedding(
            provider=args.provider,
            base_url=args.base_url,
            api_key=api_key,
            model=args.model,
            dimension=args.dimension,
        )
    except EmbeddingProbeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    report = {
        "schema_version": "poc-03.embedding-probe-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "PASS",
        "result": result.to_sanitized_dict(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
