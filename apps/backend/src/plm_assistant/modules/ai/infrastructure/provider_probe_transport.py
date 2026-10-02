"""One-shot pinned HTTPS transport for a fixed customer-free Provider probe."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlsplit

from plm_assistant.modules.ai.application.probe_policy import (
    PROBE_TEXT, ProviderProbePlan, ProbePolicyError,
)
from plm_assistant.modules.ai.application.probe_transport_contract import ProbeTransportError


MAX_RESPONSE_BYTES = 16_384
MAX_KEY_BYTES = 4_096
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 5.0
DNS_TIMEOUT_SECONDS = 3.0
TOTAL_NETWORK_SECONDS = 20.0
MAX_HEADER_BYTES = 8_192
_DNS_SCRIPT = (
    "import json,socket,sys\n"
    "try:\n"
    " r=socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)\n"
    " a=[x[4][0] for x in r]\n"
    " if not 1<=len(a)<=16: raise ValueError()\n"
    " print(json.dumps(a,separators=(',',':')))\n"
    "except Exception: sys.exit(2)\n"
)


class PinnedProbeConnection:
    """A TLS connection to one already-validated IP; never follows redirects."""

    def __init__(self, tls_socket: ssl.SSLSocket, *, hostname: str,
                 path: str, model_key: str, deadline: float | None = None) -> None:
        self._socket = tls_socket
        self._hostname = hostname
        self._path = path
        self._model_key = model_key
        self._deadline = deadline if deadline is not None else time.monotonic() + TOTAL_NETWORK_SECONDS
        self._used = False

    def _recv(self, size: int) -> bytes:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE")
        self._socket.settimeout(min(READ_TIMEOUT_SECONDS, remaining))
        return self._socket.recv(size)

    def _response_body(self) -> bytearray:
        received = bytearray()
        head = bytearray()
        body = bytearray()
        result = bytearray()
        complete = False
        try:
            while b"\r\n\r\n" not in received:
                if len(received) > MAX_HEADER_BYTES:
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                part = self._recv(min(4096, MAX_HEADER_BYTES + 4 - len(received)))
                if not part:
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                received.extend(part)
            head, _, body = received.partition(b"\r\n\r\n")
            if len(head) > MAX_HEADER_BYTES:
                raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            lines = bytes(head).split(b"\r\n")
            status = lines[0].split(b" ", 2)
            if (len(status) < 2 or status[0] not in (b"HTTP/1.0", b"HTTP/1.1")
                    or len(status[1]) != 3 or not status[1].isdigit()):
                raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            if status[1] != b"200":
                raise ProbeTransportError("PROBE_HTTP_REJECTED")
            headers: dict[bytes, bytes] = {}
            for line in lines[1:]:
                if (not line or line[:1] in (b" ", b"\t") or b":" not in line):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                name, value = line.split(b":", 1)
                name = name.lower()
                if (not name or any(not (97 <= c <= 122 or 48 <= c <= 57 or c == 45)
                                    for c in name) or name in headers):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                headers[name] = value.strip().lower()
            content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip()
            length = headers.get(b"content-length", b"")
            if (content_type != b"application/json" or not length.isdigit()
                    or not 1 <= len(length) <= 5 or b"transfer-encoding" in headers
                    or headers.get(b"content-encoding", b"identity") != b"identity"):
                raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            expected = int(length)
            if not 1 <= expected <= MAX_RESPONSE_BYTES:
                raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            if len(body) > expected:
                raise ProbeTransportError("PROBE_RESPONSE_TOO_LARGE")
            result = bytearray(body)
            while len(result) < expected:
                part = self._recv(min(4096, expected - len(result)))
                if not part:
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
                result.extend(part)
            complete = True
            return result
        finally:
            received[:] = b"\x00" * len(received)
            head[:] = b"\x00" * len(head)
            body[:] = b"\x00" * len(body)
            if not complete:
                result[:] = b"\x00" * len(result)

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
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE")
            self._socket.settimeout(remaining)
            self._socket.sendall(request)
            raw = self._response_body()
            try:
                try:
                    parsed = json.loads(raw.decode("utf-8", errors="strict"))
                except (UnicodeDecodeError, ValueError):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED") from None
                if (type(parsed) is not dict or type(parsed.get("choices")) is not list
                        or not parsed["choices"] or type(parsed["choices"][0]) is not dict):
                    raise ProbeTransportError("PROBE_PROTOCOL_REJECTED")
            finally:
                raw[:] = b"\x00" * len(raw)
        except ProbeTransportError:
            raise
        except (OSError, ssl.SSLError, TimeoutError):
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
            environment = ({"SystemRoot": os.environ["SystemRoot"]}
                           if sys.platform == "win32" else {})
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-c", _DNS_SCRIPT, hostname],
                capture_output=True, timeout=DNS_TIMEOUT_SECONDS,
                check=False, env=environment, stdin=subprocess.DEVNULL,
            )
            if (completed.returncode != 0 or len(completed.stdout) > 2048
                    or completed.stderr):
                raise ProbeTransportError("PROBE_DESTINATION_UNAVAILABLE")
            addresses = json.loads(completed.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
            raise ProbeTransportError("PROBE_DESTINATION_UNAVAILABLE") from None
        if (type(addresses) is not list or not 1 <= len(addresses) <= 16
                or any(type(item) is not str or not self._allowed_address(item)
                       for item in addresses)):
            raise ProbeTransportError("PROBE_DESTINATION_REJECTED")
        return tuple(addresses)

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    def open(self, plan: ProviderProbePlan) -> PinnedProbeConnection:
        deadline = time.monotonic() + TOTAL_NETWORK_SECONDS
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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE")
            raw = socket.create_connection((addresses[0], self.PORT),
                                           timeout=min(CONNECT_TIMEOUT_SECONDS, remaining))
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE")
                raw.settimeout(min(CONNECT_TIMEOUT_SECONDS, remaining))
                tls = self._ssl_context().wrap_socket(raw, server_hostname=hostname)
            except Exception:
                raw.close()
                raise
            tls.settimeout(min(READ_TIMEOUT_SECONDS, max(.001, deadline - time.monotonic())))
            return PinnedProbeConnection(tls, hostname=hostname,
                                         path=parts.path, model_key=plan.model_key,
                                         deadline=deadline)
        except (OSError, ssl.SSLError, TimeoutError):
            raise ProbeTransportError("PROBE_NETWORK_UNAVAILABLE") from None
