from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable

import httpx

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


OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["status", "items"],
    "properties": {
        "status": {"const": "ok"},
        "items": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


class BrokenSseStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        raise httpx.ReadTimeout("simulated stream interruption")


def ai_request(*, structured: bool = False) -> AIRequest:
    return AIRequest(
        task_type="DOCUMENT_PARSE",
        provider="deepseek",
        model="deepseek-flash",
        messages=(ChatMessage("user", "Return the requested result in JSON when required."),),
        output_schema=OUTPUT_SCHEMA if structured else None,
        max_tokens=128,
    )


def completion(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "deepseek-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11},
        },
    )


def run_scenario(name: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        details = action()
    except Exception as exc:  # evidence intentionally excludes provider body and secrets
        return {
            "name": name,
            "status": "FAIL",
            "duration_seconds": round(time.perf_counter() - started, 6),
            "error_type": type(exc).__name__,
            "error_code": getattr(exc, "code", None),
        }
    return {
        "name": name,
        "status": "PASS",
        "duration_seconds": round(time.perf_counter() - started, 6),
        **details,
    }


def with_service(handler, action: Callable[[AIService], dict[str, Any]]) -> dict[str, Any]:
    router = ModelRouter()
    router.register(DeepSeekAdapter(api_key="mock-only", transport=httpx.MockTransport(handler)))
    service = AIService(
        router,
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0),
        sleep=lambda _: None,
    )
    try:
        return action(service)
    finally:
        router.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)

    scenarios: list[dict[str, Any]] = []

    scenarios.append(
        run_scenario(
            "text_completion",
            lambda: with_service(
                lambda _: completion("PLM gateway ready"),
                lambda service: {
                    "text_match": service.complete(ai_request()).text == "PLM gateway ready"
                },
            ),
        )
    )

    stream_body = "\n".join(
        [
            'data: {"choices":[{"delta":{"content":"PLM"}}]}',
            'data: {"choices":[{"delta":{"content":" Gateway"}}]}',
            "data: [DONE]",
            "",
        ]
    )
    scenarios.append(
        run_scenario(
            "sse_stream",
            lambda: with_service(
                lambda _: httpx.Response(
                    200, text=stream_body, headers={"content-type": "text/event-stream"}
                ),
                lambda service: {
                    "chunk_text_match": "".join(service.stream(ai_request())) == "PLM Gateway"
                },
            ),
        )
    )

    scenarios.append(
        run_scenario(
            "structured_json",
            lambda: with_service(
                lambda _: completion('{"status":"ok","items":["A","B"]}'),
                lambda service: {
                    "schema_match": service.complete(ai_request(structured=True)).structured
                    == {"status": "ok", "items": ["A", "B"]}
                },
            ),
        )
    )

    def retry_scenario(status_code: int, expected_code: str) -> dict[str, Any]:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(status_code) if calls == 1 else completion("recovered")

        return with_service(
            handler,
            lambda service: {
                "recovered": service.complete(ai_request()).text == "recovered",
                "attempts": calls,
                "expected_initial_error": expected_code,
            },
        )

    scenarios.append(
        run_scenario(
            "retry_503",
            lambda: retry_scenario(503, "AI_PROVIDER_UNAVAILABLE"),
        )
    )
    scenarios.append(
        run_scenario("rate_limit_429", lambda: retry_scenario(429, "AI_RATE_LIMIT"))
    )

    def expected_error_scenario(status_code: int, expected_code: str) -> dict[str, Any]:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(status_code)

        def action(service: AIService) -> dict[str, Any]:
            try:
                service.complete(ai_request())
            except AIError as exc:
                return {
                    "error_code_match": exc.code == expected_code,
                    "attempts": calls,
                    "non_retryable": not exc.retryable,
                }
            raise AssertionError("expected AIError")

        return with_service(handler, action)

    scenarios.append(
        run_scenario(
            "invalid_key_401",
            lambda: expected_error_scenario(401, "AI_AUTH_FAILED"),
        )
    )

    def timeout_scenario() -> dict[str, Any]:
        calls = 0

        def handler(incoming: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("simulated", request=incoming)

        def action(service: AIService) -> dict[str, Any]:
            try:
                service.complete(ai_request())
            except AIError as exc:
                return {"error_code_match": exc.code == "AI_TIMEOUT", "attempts": calls}
            raise AssertionError("expected AIError")

        return with_service(handler, action)

    scenarios.append(run_scenario("timeout", timeout_scenario))

    def interrupted_stream_scenario() -> dict[str, Any]:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                stream=BrokenSseStream(),
                headers={"content-type": "text/event-stream"},
            )

        def action(service: AIService) -> dict[str, Any]:
            try:
                list(service.stream(ai_request()))
            except AIError as exc:
                return {
                    "error_code_match": exc.code == "AI_STREAM_INTERRUPTED",
                    "single_attempt": calls == 1,
                }
            raise AssertionError("expected AIError")

        return with_service(handler, action)

    scenarios.append(run_scenario("stream_interrupted_no_retry", interrupted_stream_scenario))

    def json_retry_recovery_scenario() -> dict[str, Any]:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return completion("")
            return completion('{"status":"ok","items":["A"]}')

        return with_service(
            handler,
            lambda service: {
                "schema_match": service.complete(ai_request(structured=True)).structured
                == {"status": "ok", "items": ["A"]},
                "attempts": calls,
            },
        )

    scenarios.append(run_scenario("json_retry_recovery", json_retry_recovery_scenario))

    def schema_failure_scenario() -> dict[str, Any]:
        def action(service: AIService) -> dict[str, Any]:
            try:
                service.complete(ai_request(structured=True))
            except AIError as exc:
                return {"error_code_match": exc.code == "AI_SCHEMA_INVALID"}
            raise AssertionError("expected AIError")

        return with_service(
            lambda _: completion('{"status":"wrong","items":[]}'), action
        )

    scenarios.append(run_scenario("schema_failure", schema_failure_scenario))

    service_source = (POC_DIR / "src" / "poc04_gateway" / "gateway.py").read_text(
        encoding="utf-8"
    ).lower()
    scenarios.append(
        run_scenario(
            "business_provider_boundary",
            lambda: {
                "gateway_has_no_vendor_url": "api.deepseek.com" not in service_source,
                "gateway_has_no_vendor_sdk": "openai" not in service_source,
            },
        )
    )

    for scenario in scenarios:
        booleans = [value for value in scenario.values() if isinstance(value, bool)]
        if scenario["status"] == "PASS" and booleans and not all(booleans):
            scenario["status"] = "FAIL"

    environment = {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python_version": platform.python_version(),
        "packages": {"httpx": version("httpx"), "jsonschema": version("jsonschema")},
        "secret_values_recorded": False,
        "validation_mode": "deterministic_mock_transport",
    }
    overall_pass = all(scenario["status"] == "PASS" for scenario in scenarios)
    report = {
        "status": "PASS" if overall_pass else "FAIL",
        "environment": environment,
        "scenario_count": len(scenarios),
        "passed_count": sum(scenario["status"] == "PASS" for scenario in scenarios),
        "scenarios": scenarios,
        "live_deepseek": "SEE_SEPARATE_LIVE_VALIDATION_RESULT",
    }
    (args.evidence_dir / "environment.json").write_text(
        json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.evidence_dir / "validation-result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
