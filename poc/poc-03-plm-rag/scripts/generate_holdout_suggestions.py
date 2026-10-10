from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = POC_DIR.parents[1]
sys.path.insert(0, str(POC_DIR / "src"))
sys.path.insert(0, str(REPO_ROOT / "poc" / "poc-04-ai-gateway" / "src"))

from poc03_rag.holdout_review import (  # noqa: E402
    PROMPT_ID,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_suggestion_payload,
    sanitized_suggestion_report,
    suggestion_schema,
    validate_suggestion,
)
from poc04_gateway import (  # noqa: E402
    AIError,
    AIRequest,
    AIResponse,
    AIService,
    ChatMessage,
    DeepSeekAdapter,
    ModelRouter,
    RetryPolicy,
)


RECOVERY_PROMPT = SYSTEM_PROMPT + "\n上一次响应为空或格式无效。必须直接返回单个JSON对象，不要解释，不要使用代码块。"


class CountingAdapter:
    provider_id = "deepseek"

    def __init__(self, adapter: DeepSeekAdapter) -> None:
        self.adapter = adapter
        self.request_count = 0

    def complete(self, request: AIRequest) -> AIResponse:
        self.request_count += 1
        return self.adapter.complete(request)

    def stream(self, request: AIRequest):
        return self.adapter.stream(request)

    def close(self) -> None:
        self.adapter.close()


def parse_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = value.removeprefix("```json").removeprefix("```")
        value = value.removesuffix("```").strip()
    start = value.find("{")
    end = value.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("response does not contain a JSON object")
    parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response JSON must be an object")
    return parsed


def request_suggestion(
    service: AIService,
    candidate: dict[str, Any],
    *,
    model: str,
) -> tuple[dict[str, Any], bool]:
    payload = json.dumps(build_suggestion_payload(candidate), ensure_ascii=False)
    try:
        response = service.complete(
            AIRequest(
                task_type="HOLDOUT_REVIEW_PREFILL",
                provider="deepseek",
                model=model,
                messages=(
                    ChatMessage("system", SYSTEM_PROMPT),
                    ChatMessage("user", payload),
                ),
                output_schema=suggestion_schema(),
                max_tokens=1024,
                temperature=0.0,
                thinking="disabled",
                metadata={"prompt_id": PROMPT_ID, "prompt_version": PROMPT_VERSION},
            )
        )
        return validate_suggestion(candidate, dict(response.structured or {})), False
    except (AIError, ValueError) as first_error:
        if isinstance(first_error, AIError) and first_error.code not in {
            "AI_JSON_INVALID",
            "AI_SCHEMA_INVALID",
        }:
            raise

    last_error: Exception | None = None
    for recovery_attempt in range(1, 4):
        response = service.complete(
            AIRequest(
                task_type="HOLDOUT_REVIEW_PREFILL_RECOVERY",
                provider="deepseek",
                model=model,
                messages=(
                    ChatMessage("system", RECOVERY_PROMPT),
                    ChatMessage("user", payload),
                ),
                max_tokens=2048,
                temperature=0.0,
                thinking="disabled",
                metadata={
                    "prompt_id": f"{PROMPT_ID}-plain-recovery",
                    "prompt_version": PROMPT_VERSION,
                    "recovery_attempt": recovery_attempt,
                },
            )
        )
        try:
            return validate_suggestion(candidate, parse_json_object(response.text)), True
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error
    raise RuntimeError("DeepSeek did not return a grounded constrained suggestion") from last_error


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_cache(path: Path, lock_fingerprint: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (
            row.get("prompt_id") == PROMPT_ID
            and row.get("prompt_version") == PROMPT_VERSION
            and row.get("lock_fingerprint") == lock_fingerprint
        ):
            rows[str(row["candidate_id"])] = row
    return rows


def append_cache(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate DeepSeek prefill suggestions for the locked POC-03 holdout")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--prior-failed-attempts", type=int, default=0)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required")
    lock = load_json(args.lock)
    if lock.get("status") != "LOCKED_PENDING_HUMAN_REVIEW":
        raise ValueError("holdout lock is not ready for review")
    candidates = list(lock.get("candidates") or [])
    if len(candidates) != 50:
        raise ValueError(f"expected 50 locked candidates, got {len(candidates)}")
    lock_fingerprint = str(lock.get("lock_fingerprint") or "")
    cached = load_cache(args.cache, lock_fingerprint)
    results: dict[str, dict[str, Any]] = {}
    cached_count = 0
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        row = cached.get(candidate_id)
        if row and row.get("content_sha256") == candidate.get("text_sha256"):
            results[candidate_id] = validate_suggestion(candidate, row)
            cached_count += 1

    router = ModelRouter()
    adapter = CountingAdapter(DeepSeekAdapter(api_key=api_key, base_url=args.base_url, timeout_seconds=90))
    router.register(adapter)
    service = AIService(
        router,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=1, max_delay_seconds=4),
    )
    recovery_count = 0
    try:
        pending = [candidate for candidate in candidates if str(candidate["candidate_id"]) not in results]
        for index, candidate in enumerate(pending, start=1):
            item, used_recovery = request_suggestion(service, candidate, model=args.model)
            recovery_count += used_recovery
            cache_row = {
                **item,
                "prompt_id": PROMPT_ID,
                "prompt_version": PROMPT_VERSION,
                "lock_fingerprint": lock_fingerprint,
                "content_sha256": candidate["text_sha256"],
                "model": args.model,
                "format_recovery": used_recovery,
                "generated_at": datetime.now().astimezone().isoformat(),
            }
            append_cache(args.cache, cache_row)
            results[item["candidate_id"]] = item
            print(f"DeepSeek suggestions: {index}/{len(pending)}", flush=True)
    finally:
        router.close()

    ordered = [results[str(candidate["candidate_id"])] for candidate in candidates]
    report = sanitized_suggestion_report(
        ordered,
        expected_count=len(candidates),
        api_call_count=args.prior_failed_attempts + adapter.request_count,
        cached_count=cached_count,
    )
    report["summary"]["format_recovery_count"] = recovery_count + sum(
        bool(row.get("format_recovery")) for row in cached.values()
    )
    report["summary"]["prior_failed_request_attempts"] = args.prior_failed_attempts
    report["generated_at"] = datetime.now().astimezone().isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"lock_fingerprint": lock_fingerprint, "suggestions": ordered}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
