from __future__ import annotations

import hashlib
import json
import time
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderSendProof,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.openai_compatible_adapter import (
    PinnedHttpsOpenAICompatibleAdapter,
    _PinnedOpenAIConnection,
)


class _Socket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent_copy = b""
        self.sent_buffer = None
        self.timeout = None
        self.closed = False

    def settimeout(self, value):
        self.timeout = value

    def recv(self, size):
        value, self.response = self.response[:size], self.response[size:]
        return value

    def sendall(self, value):
        self.sent_copy = bytes(value)
        self.sent_buffer = value

    def close(self):
        self.closed = True


def _fixture(response: bytes):
    now = datetime.now(timezone.utc)
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.execution.v1",
        "https://api.example.test/v1/chat/completions",
        uuid.uuid4(), uuid.uuid4(), "chat-model", "PROVIDER_MANAGED",
        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", 1_000_000, 3, 10, 20,
    )
    canonical = json.dumps({
        "messages": [
            {"content": "system text", "role": "system"},
            {"content": "user text", "role": "user"},
        ],
        "model": {"key": "chat-model", "revision": "PROVIDER_MANAGED"},
        "response_format": {
            "schema_ref": "gap-output.v1", "schema_version": 1,
            "type": "structured_json",
        },
        "schema_version": "provider-neutral-chat.v1",
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    envelope = AIExecutionEnvelope(
        uuid.uuid4(), b"c" * 32, "provider-neutral-json.v1", 1,
        (b"s" * 32,), canonical, 1, 20, "utf8-byte-upper-bound.v1", 1,
    )
    proof = AIProviderSendProof(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, 7,
        envelope.content_plan_id, uuid.uuid4(), b"g" * 32,
        provider_route_fingerprint(route), envelope.payload_fingerprint,
        envelope.payload_bytes, envelope.input_tokens,
        now + timedelta(minutes=5),
    )
    return now, route, envelope, proof, _Socket(response)


class OpenAICompatibleAdapterTests(unittest.TestCase):
    def test_request_preserves_messages_and_uses_exact_route_model(self):
        payload = json.dumps({
            "choices": [{
                "message": {"content": '{"ok":true}'},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4},
        }, separators=(",", ":")).encode()
        response = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            + f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload
        )
        _, route, envelope, _, sock = _fixture(response)
        result = _PinnedOpenAIConnection(
            sock, hostname="api.example.test", path="/v1/chat/completions",
            route=route, deadline=time.monotonic() + 20,
            monotonic=time.monotonic,
        ).send(envelope, memoryview(bytearray(b"synthetic-key")))
        head, body = sock.sent_copy.split(b"\r\n\r\n", 1)
        sent = json.loads(body)
        original = json.loads(envelope.canonical_bytes)
        self.assertEqual(sent["messages"], original["messages"])
        self.assertEqual(sent["model"], route.provider_model_key)
        self.assertEqual(sent["response_format"], {"type": "json_object"})
        self.assertFalse(sent["stream"])
        self.assertIn(b"Authorization: Bearer synthetic-key", head)
        self.assertTrue(all(value == 0 for value in sock.sent_buffer))
        self.assertEqual(result.observation.finish_reason, "STOP")
        self.assertEqual((result.observation.input_tokens,
                          result.observation.output_tokens), (20, 4))
        self.assertEqual(hashlib.sha256(result.view()).digest(),
                         result.observation.response_fingerprint)
        result.close()

    def test_redirect_ambiguous_oversize_and_bad_json_fail_closed(self):
        cases = (
            b"HTTP/1.1 302 Found\r\nContent-Length: 1\r\n\r\nx",
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Content-Length: 1000001\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Content-Length: 2\r\n\r\n{}",
        )
        for response in cases:
            _, route, envelope, _, sock = _fixture(response)
            with self.subTest(response=response[:20]), \
                    self.assertRaises(AIProviderExecutionError):
                _PinnedOpenAIConnection(
                    sock, hostname="api.example.test", path="/v1/chat",
                    route=route, deadline=time.monotonic() + 20,
                    monotonic=time.monotonic,
                ).send(envelope, memoryview(bytearray(b"synthetic-key")))
            self.assertTrue(all(value == 0 for value in sock.sent_buffer))

    def test_key_and_envelope_route_drift_fail_before_send(self):
        _, route, envelope, _, sock = _fixture(b"")
        connection = _PinnedOpenAIConnection(
            sock, hostname="api.example.test", path="/v1/chat", route=route,
            deadline=time.monotonic() + 20, monotonic=time.monotonic,
        )
        with self.assertRaises(AIProviderExecutionError):
            connection.send(envelope, memoryview(bytearray(b"bad\r\nkey")))
        self.assertIsNone(sock.sent_buffer)
        _, route, envelope, _, sock = _fixture(b"")
        with self.assertRaises(AIProviderExecutionError):
            _PinnedOpenAIConnection(
                sock, hostname="api.example.test", path="/v1/chat",
                route=replace(route, provider_model_key="other-model"),
                deadline=time.monotonic() + 20, monotonic=time.monotonic,
            ).send(envelope, memoryview(bytearray(b"synthetic-key")))
        self.assertIsNone(sock.sent_buffer)

    def test_any_private_dns_candidate_rejects_before_connect(self):
        now, route, envelope, proof, _ = _fixture(b"")
        connected = []
        adapter = PinnedHttpsOpenAICompatibleAdapter(
            address_resolver=lambda *_: ("8.8.8.8", "127.0.0.1"),
            connector=lambda *args: connected.append(args),
        )
        self.assertLess(now, proof.valid_until)
        with self.assertRaises(AIProviderExecutionError) as caught:
            adapter.send(
                route=route, proof=proof, envelope=envelope,
                key=memoryview(bytearray(b"synthetic-key")),
            )
        self.assertEqual(caught.exception.code, "AI_PROVIDER_DESTINATION_REJECTED")
        self.assertEqual(connected, [])

    def test_real_isolated_dns_rejects_loopback(self):
        adapter = PinnedHttpsOpenAICompatibleAdapter()
        addresses = adapter._isolated_addresses("localhost", 3)
        self.assertTrue(addresses)
        self.assertTrue(all(not adapter._allowed_address(item) for item in addresses))


if __name__ == "__main__":
    unittest.main()
