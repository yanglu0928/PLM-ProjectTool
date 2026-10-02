"""One-shot pinned HTTPS transport for a fixed customer-free Provider probe."""

from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlsplit

from plm_assistant.modules.ai.application.probe_policy import (
    PROBE_TEXT, ProviderProbePlan, ProbePolicyError,
)
from plm_assistant.modules.ai.application.probe_transport_contract import ProbeTransportError


MAX_RESPONSE_BYTES = 16_384
MAX_KEY_BYTES = 4_096
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 5.0


class PinnedProbeConnection:
    """A TLS connection to one already-validated IP; never follows redirects."""

    def __init__(self, tls_socket: ssl.SSLSocket, *, hostname: str,
                 path: str, model_key: str) -> None:
        self._socket = tls_socket
        self._hostname = hostname
        self._path = path
        self._model_key = model_key
        self._used = False

    def __enter__(self) -> PinnedProbeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        self._socket.close()

    def send_fixed_probe(self, key: memoryview) -> None:
        if self._used:
            raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
        self._used = True
        if (type(key) is not memoryview or not 1 <= len(key) <= MAX_KEY_BYTES
                or any(not 33 <= byte <= 126 for byte in key)):
            raise ProbeTransportError("PROBE_SECRET_REJECTED")
        body = json.dumps({
            "model": self._model_key,
            "messages": [{"role": "user", "content": PROBE_TEXT}],
            "max_tokens": 1,
            "stream": False,
        }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        request = bytearray()
        try:
            request.extend(
                f"POST {self._path} HTTP/1.1\r\nHost: {self._hostname}\r\n"
                "Content-Type: application/json\r\nAccept: application/json\r\n"
                f"Content-Length: {len(body)}\r\nAuthorization: Bearer ".encode("ascii")
            )
            request.extend(key)
            request.extend(b"\r\nConnection: close\r\n\r\n")
            request.extend(body)
            self._socket.sendall(request)
            response = http.client.HTTPResponse(self._socket)
            try:
                response.begin()
                if response.status != 200:
                    raise ProbeTransportError("PROBE_HTTP_REJECTED")
                content_types = [value for name, value in response.getheaders()
                                 if name.lower() == "content-type"]
                encodings = [value for name, value in response.getheaders()
                             if name.lower() == "content-encoding"]
                if (len(content_types) != 1
                        or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
                        or encodings and encodings != ["identity"]
                        or response.length is not None and response.length > MAX_RESPONSE_BYTES):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ProbeTransportError("PROBE_RESPONSE_TOO_LARGE")
                try:
                    parsed = json.loads(raw.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, ValueError):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED") from None
                if (type(parsed) is not dict or type(parsed.get("choices")) is not list
                        or not parsed["choices"] or type(parsed["choices"][0]) is not dict):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            finally:
                response.close()
        except ProbeTransportError:
            raise
        except (OSError, ssl.SSLError, http.client.HTTPException, TimeoutError):
            raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE") from None
        finally:
            request[:] = b"\x00" * len(request)


class PinnedHttpsProbeTransport:
    """Production defaults: global-IP DNS only, port 443, system CA, no proxy."""

    PORT = 443

    @staticmethod
    def _allowed_address(value: str) -> bool:
        try:
            return ipaddress.ip_address(value).is_global
        except ValueError:
            return False

    def _addresses(self, hostname: str) -> tuple[str, ...]:
        try:
            records = socket.getaddrinfo(hostname, self.PORT, type=socket.SOCK_STREAM,
                                         proto=socket.IPPROTO_TCP)
        except OSError:
            raise ProbeTransportError("PROBE_DESTINATION_UNAVAILABLE") from None
        addresses = tuple(record[4][0] for record in records)
        if not addresses or any(not self._allowed_address(item) for item in addresses):
            raise ProbeTransportError("PROBE_DESTINATION_REJECTED")
        return addresses

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    def open(self, plan: ProviderProbePlan) -> PinnedProbeConnection:
        if type(plan) is not ProviderProbePlan:
            raise ProbeTransportError("PROBE_DESTINATION_REJECTED")
        try:
            plan.__post_init__()
        except ProbePolicyError:
            raise ProbeTransportError("PROBE_DESTINATION_REJECTED") from None
        parts = urlsplit(plan.endpoint_url)
        hostname = parts.hostname
        if not hostname:
            raise ProbeTransportError("PROBE_DESTINATION_REJECTED")
        addresses = self._addresses(hostname)
        try:
            raw = socket.create_connection((addresses[0], self.PORT),
                                           timeout=CONNECT_TIMEOUT_SECONDS)
            try:
                tls = self._ssl_context().wrap_socket(raw, server_hostname=hostname)
            except Exception:
                raw.close()
                raise
            tls.settimeout(READ_TIMEOUT_SECONDS)
            return PinnedProbeConnection(tls, hostname=hostname,
                                         path=parts.path, model_key=plan.model_key)
        except (OSError, ssl.SSLError, TimeoutError):
            raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE") from None
