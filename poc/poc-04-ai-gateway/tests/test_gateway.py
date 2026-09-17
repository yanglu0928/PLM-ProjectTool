from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import httpx

POC_DIR = Path(__file__).resolve().parents[1]
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


def request(*, schema: dict | None = None) -> AIRequest:
    return AIRequest(
        task_type="DOCUMENT_PARSE",
        provider="deepseek",
        model="deepseek-flash",
        messages=(ChatMessage("user", "Return a JSON result when requested."),),
        output_schema=schema,
    )


def response(text: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={
            "model": "deepseek-flash",
            "choices": [
                {
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        },
    )


class BrokenSseStream(httpx.SyncByteStream):
    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
        raise httpx.ReadTimeout("stream interrupted")


class GatewayTests(unittest.TestCase):
    def service(self, handler) -> tuple[AIService, ModelRouter]:
        router = ModelRouter()
        router.register(
            DeepSeekAdapter(api_key="test-only", transport=httpx.MockTransport(handler))
        )
        return (
            AIService(
                router,
                retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0),
                sleep=lambda _: None,
            ),
            router,
        )

    def test_text_completion(self) -> None:
        service, router = self.service(lambda _: response("ok"))
        try:
            self.assertEqual(service.complete(request()).text, "ok")
        finally:
            router.close()

    def test_streaming_sse(self) -> None:
        body = "\n".join(
            [
                'data: {"choices":[{"delta":{"content":"PLM"}}]}',
                'data: {"choices":[{"delta":{"content":" Gateway"}}]}',
                "data: [DONE]",
                "",
            ]
        )
        service, router = self.service(
            lambda _: httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
        )
        try:
            self.assertEqual("".join(service.stream(request())), "PLM Gateway")
        finally:
            router.close()

    def test_structured_output_schema(self) -> None:
        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"const": "ok"}},
            "additionalProperties": False,
        }
        service, router = self.service(lambda _: response('{"status":"ok"}'))
        try:
            self.assertEqual(service.complete(request(schema=schema)).structured, {"status": "ok"})
        finally:
            router.close()

    def test_schema_failure(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return response('{"status":"wrong"}')

        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"const": "ok"}},
        }
        service, router = self.service(handler)
        try:
            with self.assertRaisesRegex(AIError, "schema validation") as raised:
                service.complete(request(schema=schema))
            self.assertEqual(raised.exception.code, "AI_SCHEMA_INVALID")
            self.assertEqual(calls, 3)
        finally:
            router.close()

    def test_invalid_json_recovers_on_retry(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return response("") if calls == 1 else response('{"status":"ok"}')

        schema = {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"const": "ok"}},
        }
        service, router = self.service(handler)
        try:
            self.assertEqual(service.complete(request(schema=schema)).structured, {"status": "ok"})
            self.assertEqual(calls, 2)
        finally:
            router.close()

    def test_timeout_retries_three_times(self) -> None:
        calls = 0

        def handler(incoming: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout("test timeout", request=incoming)

        service, router = self.service(handler)
        try:
            with self.assertRaises(AIError) as raised:
                service.complete(request())
            self.assertEqual(raised.exception.code, "AI_TIMEOUT")
            self.assertEqual(calls, 3)
        finally:
            router.close()

    def test_503_is_retried(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(503) if calls == 1 else response("recovered")

        service, router = self.service(handler)
        try:
            self.assertEqual(service.complete(request()).text, "recovered")
            self.assertEqual(calls, 2)
        finally:
            router.close()

    def test_401_is_not_retried(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(401)

        service, router = self.service(handler)
        try:
            with self.assertRaises(AIError) as raised:
                service.complete(request())
            self.assertEqual(raised.exception.code, "AI_AUTH_FAILED")
            self.assertEqual(calls, 1)
        finally:
            router.close()

    def test_429_is_retried(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(429) if calls == 1 else response("recovered")

        service, router = self.service(handler)
        try:
            self.assertEqual(service.complete(request()).text, "recovered")
            self.assertEqual(calls, 2)
        finally:
            router.close()

    def test_structured_request_sets_json_object_mode(self) -> None:
        captured: dict = {}

        def handler(incoming: httpx.Request) -> httpx.Response:
            captured.update(json.loads(incoming.content))
            return response('{"status":"ok"}')

        schema = {"type": "object"}
        service, router = self.service(handler)
        try:
            service.complete(request(schema=schema))
            self.assertEqual(captured["response_format"], {"type": "json_object"})
        finally:
            router.close()

    def test_stream_is_not_retried_after_output_started(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                stream=BrokenSseStream(),
                headers={"content-type": "text/event-stream"},
            )

        service, router = self.service(handler)
        try:
            with self.assertRaises(AIError) as raised:
                list(service.stream(request()))
            self.assertEqual(raised.exception.code, "AI_STREAM_INTERRUPTED")
            self.assertEqual(calls, 1)
        finally:
            router.close()


if __name__ == "__main__":
    unittest.main()
