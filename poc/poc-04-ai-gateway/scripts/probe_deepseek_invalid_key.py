from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    router = ModelRouter()
    router.register(
        DeepSeekAdapter(api_key="poc-invalid-key-never-a-secret", timeout_seconds=15)
    )
    service = AIService(
        router,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    started = time.perf_counter()
    try:
        service.complete(
            AIRequest(
                task_type="DOCUMENT_PARSE",
                provider="deepseek",
                model="deepseek-flash",
                messages=(ChatMessage("user", "Connectivity probe"),),
                max_tokens=1,
            )
        )
    except AIError as exc:
        report = {
            "status": "PASS" if exc.code == "AI_AUTH_FAILED" else "FAIL",
            "expected_error": "AI_AUTH_FAILED",
            "actual_error": exc.code,
            "http_status": exc.status_code,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "secret_value_recorded": False,
        }
    else:
        report = {
            "status": "FAIL",
            "expected_error": "AI_AUTH_FAILED",
            "actual_error": None,
            "duration_seconds": round(time.perf_counter() - started, 3),
            "secret_value_recorded": False,
        }
    finally:
        router.close()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
