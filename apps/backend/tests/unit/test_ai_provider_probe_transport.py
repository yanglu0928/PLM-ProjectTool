from __future__ import annotations

import subprocess
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.probe_transport_contract import ProbeTransportError
from plm_assistant.modules.ai.infrastructure.provider_probe_transport import (
    PinnedHttpsProbeTransport, PinnedProbeConnection,
)


class FakeSocket:
    def __init__(self, response: bytes):
        self.response = response
        self.sent = b""
        self.sent_buffer = None
        self.closed = False
        self.timeout = None

    def settimeout(self, value):
        self.timeout = value

    def recv(self, size):
        data, self.response = self.response[:size], self.response[size:]
        return data

    def sendall(self, value):
        self.sent = bytes(value)
        self.sent_buffer = value

    def makefile(self, *_):
        return io.BytesIO(self.response)

    def close(self):
        self.closed = True


def plan():
    return ProviderProbePlan(
        uuid.uuid4(), 1, "trusted.synthetic", "https://probe.example.test/v1/chat",
        "synthetic-chat", uuid.uuid4(),
    )


class ProbeTransportTests(unittest.TestCase):
    def test_dns_rejects_any_non_global_candidate(self):
        transport = PinnedHttpsProbeTransport()
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=b'["8.8.8.8","127.0.0.1"]', stderr=b"")):
            with self.assertRaises(ProbeTransportError) as caught:
                transport._addresses("probe.example.test")
            self.assertEqual(caught.exception.code, "PROBE_DESTINATION_REJECTED")
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=b'["8.8.8.8"]', stderr=b"")):
            self.assertEqual(transport._addresses("probe.example.test"), ("8.8.8.8",))

    def test_dns_timeout_and_child_failure_are_unavailable(self):
        transport = PinnedHttpsProbeTransport()
        for failure in (subprocess.TimeoutExpired("python", 3), OSError("spawn failed")):
            with patch("subprocess.run", side_effect=failure):
                with self.assertRaises(ProbeTransportError) as caught:
                    transport._addresses("probe.example.test")
                self.assertEqual(caught.exception.code, "PROBE_DESTINATION_UNAVAILABLE")

    def test_real_isolated_child_rejects_loopback(self):
        with self.assertRaises(ProbeTransportError) as caught:
            PinnedHttpsProbeTransport()._addresses("localhost")
        self.assertEqual(caught.exception.code, "PROBE_DESTINATION_REJECTED")

    def test_real_dns_child_timeout_is_reaped(self):
        with patch("plm_assistant.modules.ai.infrastructure.provider_probe_transport._DNS_SCRIPT",
                   "import time; time.sleep(5)"), \
             patch("plm_assistant.modules.ai.infrastructure.provider_probe_transport.DNS_TIMEOUT_SECONDS", .1):
            started = time.monotonic()
            with self.assertRaises(ProbeTransportError) as caught:
                PinnedHttpsProbeTransport()._addresses("localhost")
            self.assertLess(time.monotonic() - started, 2)
            self.assertEqual(caught.exception.code, "PROBE_DESTINATION_UNAVAILABLE")

    def test_fixed_request_is_single_use_bounded_and_zeroed(self):
        body = b'{"choices":[{}]}'
        sock = FakeSocket(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                          + f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        with PinnedProbeConnection(sock, hostname="probe.example.test",
                                   path="/v1/chat", model_key="synthetic-chat") as conn:
            conn.send_fixed_probe(memoryview(bytearray(b"synthetic-key")))
            self.assertIn(b"Authorization: Bearer synthetic-key\r\n", sock.sent)
            self.assertIn(b'"content":"ping"', sock.sent)
            self.assertNotIn(b"customer", sock.sent.lower())
            self.assertTrue(all(value == 0 for value in sock.sent_buffer))
            with self.assertRaises(ProbeTransportError):
                conn.send_fixed_probe(memoryview(bytearray(b"synthetic-key")))
        self.assertTrue(sock.closed)

    def test_redirect_oversize_bad_json_and_invalid_key_fail_closed(self):
        responses = (
            (b"HTTP/1.1 302 Found\r\nLocation: https://other.test/\r\nContent-Length: 0\r\n\r\n", "PROBE_HTTP_REJECTED"),
            (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 99999\r\n\r\n", "PROBE_PROTOCOL_REJECTED"),
            (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 3\r\n\r\nxxx", "PROBE_PROTOCOL_REJECTED"),
        )
        for raw, code in responses:
            with self.subTest(code=code):
                sock = FakeSocket(raw)
                with self.assertRaises(ProbeTransportError) as caught:
                    PinnedProbeConnection(sock, hostname="probe.example.test",
                                          path="/v1/chat", model_key="synthetic-chat").send_fixed_probe(
                                              memoryview(bytearray(b"synthetic-key")))
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(all(value == 0 for value in sock.sent_buffer))
        sock = FakeSocket(b"")
        with self.assertRaises(ProbeTransportError) as caught:
            PinnedProbeConnection(sock, hostname="probe.example.test",
                                  path="/v1/chat", model_key="synthetic-chat").send_fixed_probe(
                                      memoryview(bytearray(b"bad\r\nkey")))
        self.assertEqual(caught.exception.code, "PROBE_SECRET_REJECTED")
        self.assertIsNone(sock.sent_buffer)

    def test_absolute_deadline_rejects_trickled_response(self):
        class DrippingSocket(FakeSocket):
            def recv(self, size):
                time.sleep(.02)
                return super().recv(1)

        sock = DrippingSocket(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                               b"Content-Length: 16\r\n\r\n{\"choices\":[{}]}")
        with self.assertRaises(ProbeTransportError) as caught:
            PinnedProbeConnection(sock, hostname="probe.example.test",
                path="/v1/chat", model_key="synthetic-chat",
                deadline=time.monotonic() + .07).send_fixed_probe(
                    memoryview(bytearray(b"synthetic-key")))
        self.assertEqual(caught.exception.code, "PROBE_NETWORK_UNAVAILABLE")
        self.assertTrue(all(value == 0 for value in sock.sent_buffer))

    def test_unbounded_or_ambiguous_response_fails_closed(self):
        responses = (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
            b"HTTP/1.1 200 OK\r\n" + b"X-Long: " + b"a" * 8192 + b"\r\n\r\n",
        )
        for response in responses:
            with self.subTest(length=len(response)):
                sock = FakeSocket(response)
                with self.assertRaises(ProbeTransportError) as caught:
                    PinnedProbeConnection(sock, hostname="probe.example.test",
                        path="/v1/chat", model_key="synthetic-chat").send_fixed_probe(
                            memoryview(bytearray(b"synthetic-key")))
                self.assertEqual(caught.exception.code, "PROBE_PROTOCOL_REJECTED")
                self.assertTrue(all(value == 0 for value in sock.sent_buffer))


if __name__ == "__main__":
    unittest.main()
