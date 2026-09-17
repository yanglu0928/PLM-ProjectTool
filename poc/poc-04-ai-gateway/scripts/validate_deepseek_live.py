from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc04_gateway import (  # noqa: E402
    AIError,
    AIRequest,
    AIService,
    ChatMessage,
    DeepSeekAdapter,
    ModelRouter,
    RetryPolicy,
)


STRUCTURED_SCHEMA = {
    "type": "object",
    "required": ["status", "items"],
    "properties": {
        "status": {"const": "ok"},
        "items": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "additionalProperties": False,
}


def run_case(name: str, action: Callable[[], bool]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        matched = action()
    except AIError as exc:
        return {
            "name": name,
            "status": "FAIL",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "error_code": exc.code,
            "http_status": exc.status_code,
        }
    except Exception as exc:
        return {
            "name": name,
            "status": "FAIL",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "error_type": type(exc).__name__,
        }
    return {
        "name": name,
        "status": "PASS" if matched else "FAIL",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "expected_output_match": matched,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
    parser.add_argument(
        "--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key.strip():
        report = {
            "status": "NOT_RUN_MISSING_SECRET",
            "model": args.model,
            "base_url": args.base_url,
            "secret_value_recorded": False,
            "response_content_recorded": False,
            "scenarios": [],
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    router = ModelRouter()
    router.register(
        DeepSeekAdapter(
            api_key=api_key,
            base_url=args.base_url,
            timeout_seconds=60,
        )
    )
    service = AIService(
        router,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4),
    )
    try:
        text_request = AIRequest(
            task_type="DOCUMENT_PARSE",
            provider="deepseek",
            model=args.model,
            messages=(ChatMessage("user", "Reply with exactly POC04_OK and nothing else."),),
            max_tokens=32,
        )
        stream_request = AIRequest(
            task_type="DOCUMENT_PARSE",
            provider="deepseek",
            model=args.model,
            messages=(ChatMessage("user", "Reply with exactly POC04_STREAM_OK and nothing else."),),
            max_tokens=32,
        )
        structured_request = AIRequest(
            task_type="DOCUMENT_PARSE",
            provider="deepseek",
            model=args.model,
            messages=(
                ChatMessage(
                    "user",
                    'Return JSON exactly matching this example: {"status":"ok","items":["POC04"]}',
                ),
            ),
            output_schema=STRUCTURED_SCHEMA,
            max_tokens=64,
        )
        scenarios = [
            run_case(
                "live_text",
                lambda: service.complete(text_request).text.strip() == "POC04_OK",
            ),
            run_case(
                "live_sse_stream",
                lambda: "".join(service.stream(stream_request)).strip() == "POC04_STREAM_OK",
            ),
            run_case(
                "live_structured_json",
                lambda: service.complete(structured_request).structured
                == {"status": "ok", "items": ["POC04"]},
            ),
        ]
    finally:
        router.close()

    overall_pass = all(scenario["status"] == "PASS" for scenario in scenarios)
    report = {
        "status": "PASS" if overall_pass else "FAIL",
        "model": args.model,
        "base_url": args.base_url,
        "secret_value_recorded": False,
        "response_content_recorded": False,
        "scenarios": scenarios,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
