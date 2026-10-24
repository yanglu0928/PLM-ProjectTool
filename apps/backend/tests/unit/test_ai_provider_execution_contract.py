from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    AIProviderSendProof,
    provider_route_fingerprint,
    require_provider_send,
    safe_https_endpoint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind


class AIProviderExecutionContractTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 3, 16, tzinfo=timezone.utc)
        self.route = AIProviderExecutionRoute(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            ProviderKind.OPENAI_COMPATIBLE, "endpoint.execution.v1",
            "https://api.example.test/v1/chat/completions",
            uuid.uuid4(), uuid.uuid4(), "chat-model", "PROVIDER_MANAGED",
            "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
            1_000_000, 3, 10, 20,
        )
        self.envelope = AIExecutionEnvelope(
            uuid.uuid4(), b"c" * 32, "provider-neutral-json.v1", 1,
            (b"s" * 32,), b'{"ok":true}', 1, 11,
            "utf8-byte-upper-bound.v1", 1,
        )
        self.proof = AIProviderSendProof(
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), 1, 7,
            self.envelope.content_plan_id, uuid.uuid4(), b"g" * 32,
            provider_route_fingerprint(self.route),
            self.envelope.payload_fingerprint, self.envelope.payload_bytes,
            self.envelope.input_tokens, self.now + timedelta(minutes=5),
        )

    def test_route_and_exact_envelope_are_authorized(self):
        self.assertIs(require_provider_send(
            self.proof, self.route, self.envelope, now=self.now), self.proof)
        self.assertNotIn(self.route.endpoint_url, repr(self.route))
        self.assertNotIn(str(self.route.secret_ref), repr(self.route))

    def test_route_payload_expiry_and_count_drift_fail_closed(self):
        cases = (
            (self.proof, replace(self.route, secret_version_id=uuid.uuid4()),
             self.envelope, self.now),
            (replace(self.proof, payload_fingerprint=b"z" * 32), self.route,
             self.envelope, self.now),
            (replace(self.proof, payload_bytes=self.proof.payload_bytes + 1),
             self.route, self.envelope, self.now),
            (self.proof, self.route, self.envelope,
             self.proof.valid_until + timedelta(seconds=1)),
        )
        for proof, route, envelope, now in cases:
            with self.subTest(proof=proof, route=route, now=now), \
                    self.assertRaises(AIProviderExecutionError):
                require_provider_send(proof, route, envelope, now=now)

    def test_endpoint_rejects_credentials_ports_queries_and_private_hosts(self):
        rejected = (
            "http://api.example.test/v1/chat", "https://user@api.example.test/v1/chat",
            "https://api.example.test:8443/v1/chat",
            "https://api.example.test/v1/chat?key=x",
            "https://127.0.0.1/v1/chat", "https://localhost/v1/chat",
            "https://api.example.test/../private",
        )
        self.assertTrue(safe_https_endpoint(
            "https://api.example.test/v1/chat/completions"))
        self.assertTrue(all(not safe_https_endpoint(value) for value in rejected))

    def test_response_memory_is_hidden_and_zeroed_on_close(self):
        body = bytearray(b'{"choices":[{"message":{"content":"result"}}]}')
        observation = AIProviderResponseObservation(
            hashlib.sha256(body).digest(), len(body), 11, 5, 25, "STOP",
        )
        response = AIProviderResponse(body, observation)
        self.assertEqual(bytes(response.view()), bytes(body))
        self.assertNotIn("result", repr(response))
        response.close()
        self.assertEqual(body, bytearray(len(body)))
        with self.assertRaises(AIProviderExecutionError):
            response.view()

    def test_response_digest_and_metadata_are_validated(self):
        body = bytearray(b"{}")
        bad = AIProviderResponseObservation(b"x" * 32, 2, None, None, 0, "UNKNOWN")
        with self.assertRaises(AIProviderExecutionError):
            AIProviderResponse(body, bad)
        with self.assertRaises(AIProviderExecutionError):
            AIProviderResponseObservation(
                hashlib.sha256(body).digest(), 2, None, None, -1, "OTHER")


if __name__ == "__main__":
    unittest.main()
