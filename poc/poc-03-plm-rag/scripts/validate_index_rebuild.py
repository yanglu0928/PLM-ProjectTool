from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.index_binding import (  # noqa: E402
    EmbeddingModelBinding,
    IndexBinding,
)
from poc03_rag.index_rebuild import (  # noqa: E402
    IndexRebuildError,
    validate_model_change_rebuild,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a full embedding index rebuild.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", default="PLM_POC_EMBEDDING_API_KEY")
    parser.add_argument("--record-count", type=int, default=120)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"Required environment variable is not set: {args.api_key_env}", file=sys.stderr)
        return 2
    if not 100 <= args.record_count <= 200:
        print("record-count must be between 100 and 200", file=sys.stderr)
        return 2

    old_binding = IndexBinding(
        index_id="plm-rag-poc03-qwen37-1024-v1",
        index_version="v1",
        embedding=EmbeddingModelBinding(
            provider="aliyun-model-studio-openai-compatible",
            model="qwen3.7-text-embedding",
            dimension=1024,
        ),
    )
    new_binding = IndexBinding(
        index_id="plm-rag-poc03-text-embedding-v4-768-v2",
        index_version="v2",
        embedding=EmbeddingModelBinding(
            provider="aliyun-model-studio-openai-compatible",
            model="text-embedding-v4",
            dimension=768,
        ),
    )
    texts = [
        f"PLM PoC synthetic rebuild record {number:04d}; no customer content."
        for number in range(1, args.record_count + 1)
    ]
    try:
        result = validate_model_change_rebuild(
            old_binding=old_binding,
            new_binding=new_binding,
            texts=texts,
            base_url=args.base_url,
            api_key=api_key,
            max_batch_size=10,
        )
    except IndexRebuildError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    report = {
        "schema_version": "poc-03.index-rebuild-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": "PASS",
        "input_source": "SYNTHETIC_NON_CUSTOMER",
        "result": result.to_sanitized_dict(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
