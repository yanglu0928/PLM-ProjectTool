"""Pinned, bounded OpenAI-compatible Provider Adapter for approved AI envelopes."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlsplit

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionError,
    AIProviderExecutionRoute,
    AIProviderResponse,
    AIProviderResponseObservation,
    AIProviderSendProof,
    require_provider_send,
)


_MAX_KEY_BYTES = 4_096
_MAX_HEADER_BYTES = 16_384
_MAX_DNS_OUTPUT_BYTES = 2_048
_DNS_SCRIPT = (
    "import json,socket,sys\n"
    "try:\n"
    " r=socket.getaddrinfo(sys.argv[1],443,type=socket.SOCK_STREAM,"
    "proto=socket.IPPROTO_TCP)\n"
    " a=[x[4][0] for x in r]\n"
    " if not 1<=len(a)<=16: raise ValueError()\n"
    " print(json.dumps(a,separators=(',',':')))\n"
    "except Exception: sys.exit(2)\n"
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _wire_body(
    route: AIProviderExecutionRoute, envelope: AIExecutionEnvelope,
) -> bytearray:
    try:
        envelope.__post_init__()
        value = json.loads(envelope.canonical_bytes.decode("utf-8"))
        if (type(value) is not dict
                or set(value) != {
                    "messages", "model", "response_format", "schema_version",
                }
                or value["schema_version"] != "provider-neutral-chat.v1"
                or type(value["model"]) is not dict
                or value["model"] != {
                    "key": route.provider_model_key,
                    "revision": route.model_revision,
                }
                or type(value["response_format"]) is not dict
                or set(value["response_format"]) != {
                    "schema_ref", "schema_version", "type",
                }
                or value["response_format"]["type"] != "structured_json"
                or type(value["response_format"]["schema_ref"]) is not str
                or type(value["response_format"]["schema_version"]) is not int
                or type(value["messages"]) is not list
                or len(value["messages"]) != 2
                or tuple(item.get("role") if type(item) is dict else None
                         for item in value["messages"])
                != ("system", "user")
                or any(set(item) != {"content", "role"}
                       or type(item["content"]) is not str
                       or not item["content"]
                       for item in value["messages"])):
            raise ValueError()
        return bytearray(_canonical_json({
            "messages": value["messages"],
            "model": route.provider_model_key,
            "response_format": {"type": "json_object"},
            "stream": False,
        }))
    except Exception:
        raise AIProviderExecutionError("AI_PROVIDER_ENVELOPE_REJECTED") from None


class _PinnedOpenAIConnection:
    def __init__(
        self, tls_socket: ssl.SSLSocket, *, hostname: str, path: str,
        route: AIProviderExecutionRoute, deadline: float,
        monotonic: Callable[[], float],
    ) -> None:
        self._socket = tls_socket
        self._hostname = hostname
        self._path = path
        self._route = route
        self._deadline = deadline
        self._monotonic = monotonic
        self._used = False

    def _remaining(self) -> float:
        value = self._deadline - self._monotonic()
        if value <= 0:
            raise AIProviderExecutionError("AI_PROVIDER_NETWORK_UNAVAILABLE")
        return value

    def _recv(self, size: int) -> bytes:
        self._socket.settimeout(min(
            self._route.read_timeout_seconds, self._remaining(),
        ))
        return self._socket.recv(size)

    def _response_body(self) -> bytearray:
        received, head, body, result = (
            bytearray(), bytearray(), bytearray(), bytearray(),
        )
        complete = False
        try:
            while b"\r\n\r\n" not in received:
                if len(received) > _MAX_HEADER_BYTES:
                    raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
                part = self._recv(min(
                    4096, _MAX_HEADER_BYTES + 4 - len(received),
                ))
                if not part:
                    raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
                received.extend(part)
            head, _, body = received.partition(b"\r\n\r\n")
            if len(head) > _MAX_HEADER_BYTES:
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
            lines = bytes(head).split(b"\r\n")
            status = lines[0].split(b" ", 2)
            if (len(status) < 2 or status[0] not in (b"HTTP/1.0", b"HTTP/1.1")
                    or len(status[1]) != 3 or not status[1].isdigit()):
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
            if status[1] != b"200":
                raise AIProviderExecutionError("AI_PROVIDER_HTTP_REJECTED")
            headers: dict[bytes, bytes] = {}
            for line in lines[1:]:
                if not line or line[:1] in (b" ", b"\t") or b":" not in line:
                    raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
                name, value = line.split(b":", 1)
                name = name.lower()
                if (not name or name in headers
                        or any(not (97 <= item <= 122 or 48 <= item <= 57
                                   or item == 45) for item in name)):
                    raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
                headers[name] = value.strip().lower()
            content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip()
            length = headers.get(b"content-length", b"")
            if (content_type != b"application/json" or not length.isdigit()
                    or not 1 <= len(length) <= 9
                    or b"transfer-encoding" in headers
                    or headers.get(b"content-encoding", b"identity") != b"identity"):
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
            expected = int(length)
            if not 1 <= expected <= self._route.max_response_bytes:
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_TOO_LARGE")
            if len(body) > expected:
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
            result = bytearray(body)
            while len(result) < expected:
                part = self._recv(min(4096, expected - len(result)))
                if not part:
                    raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED")
                result.extend(part)
            complete = True
            return result
        finally:
            received[:] = b"\x00" * len(received)
            head[:] = b"\x00" * len(head)
            body[:] = b"\x00" * len(body)
            if not complete:
                result[:] = b"\x00" * len(result)

    def send(self, envelope: AIExecutionEnvelope, key: memoryview) -> AIProviderResponse:
        if self._used:
            raise AIProviderExecutionError("AI_PROVIDER_REQUEST_REJECTED")
        self._used = True
        if (type(key) is not memoryview or not 1 <= len(key) <= _MAX_KEY_BYTES
                or any(not 33 <= value <= 126 for value in key)):
            raise AIProviderExecutionError("AI_PROVIDER_SECRET_REJECTED")
        body = _wire_body(self._route, envelope)
        request = bytearray()
        raw = bytearray()
        started = self._monotonic()
        try:
            request.extend(
                f"POST {self._path} HTTP/1.1\r\nHost: {self._hostname}\r\n"
                "Content-Type: application/json\r\nAccept: application/json\r\n"
                f"Content-Length: {len(body)}\r\nAuthorization: Bearer ".encode(
                    "ascii",
                )
            )
            request.extend(key)
            request.extend(b"\r\nConnection: close\r\n\r\n")
            request.extend(body)
            self._socket.settimeout(self._remaining())
            self._socket.sendall(request)
            raw = self._response_body()
            try:
                value = json.loads(raw.decode("utf-8"))
                choices = value.get("choices") if type(value) is dict else None
                first = choices[0] if type(choices) is list and choices else None
                message = first.get("message") if type(first) is dict else None
                if (type(message) is not dict
                        or type(message.get("content")) is not str):
                    raise ValueError()
                finish = first.get("finish_reason")
                finish_reason = {
                    "stop": "STOP", "length": "LENGTH",
                    "tool_calls": "TOOL_CALL", "function_call": "TOOL_CALL",
                    "content_filter": "CONTENT_FILTER",
                }.get(finish, "UNKNOWN")
                usage = value.get("usage")
                input_tokens = None
                output_tokens = None
                if usage is not None:
                    if type(usage) is not dict:
                        raise ValueError()
                    input_tokens = usage.get("prompt_tokens")
                    output_tokens = usage.get("completion_tokens")
                    if any(type(item) is not int or item < 0
                           for item in (input_tokens, output_tokens)):
                        raise ValueError()
            except (UnicodeDecodeError, ValueError, TypeError, KeyError, IndexError):
                raise AIProviderExecutionError("AI_PROVIDER_RESPONSE_REJECTED") from None
            observation = AIProviderResponseObservation(
                hashlib.sha256(raw).digest(), len(raw), input_tokens,
                output_tokens,
                max(0, int((self._monotonic() - started) * 1000)),
                finish_reason,
            )
            response = AIProviderResponse(raw, observation)
            raw = bytearray()
            return response
        except AIProviderExecutionError:
            raise
        except (OSError, ssl.SSLError, TimeoutError):
            raise AIProviderExecutionError("AI_PROVIDER_NETWORK_UNAVAILABLE") from None
        finally:
            body[:] = b"\x00" * len(body)
            request[:] = b"\x00" * len(request)
            raw[:] = b"\x00" * len(raw)


class PinnedHttpsOpenAICompatibleAdapter:
    """Port 443, global-IP pinning, system CA, no proxy and no redirects."""

    PORT = 443

    def __init__(
        self, *,
        address_resolver: Callable[[str, float], tuple[str, ...]] | None = None,
        connector: Callable[[str, int, float], socket.socket] | None = None,
        ssl_context_factory: Callable[[], ssl.SSLContext] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolver = address_resolver or self._isolated_addresses
        self._connector = connector or (
            lambda address, port, timeout: socket.create_connection(
                (address, port), timeout=timeout,
            )
        )
        self._ssl = ssl_context_factory or self._ssl_context
        self._monotonic = monotonic

    @staticmethod
    def _allowed_address(value: str) -> bool:
        try:
            return ipaddress.ip_address(value).is_global
        except ValueError:
            return False

    @staticmethod
    def _isolated_addresses(hostname: str, timeout: float) -> tuple[str, ...]:
        try:
            environment = ({"SystemRoot": os.environ["SystemRoot"]}
                           if sys.platform == "win32" else {})
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-c", _DNS_SCRIPT, hostname],
                capture_output=True, timeout=timeout, check=False,
                env=environment, stdin=subprocess.DEVNULL,
            )
            if (completed.returncode != 0
                    or len(completed.stdout) > _MAX_DNS_OUTPUT_BYTES
                    or completed.stderr):
                raise AIProviderExecutionError("AI_PROVIDER_DESTINATION_UNAVAILABLE")
            addresses = json.loads(completed.stdout)
        except AIProviderExecutionError:
            raise
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
            raise AIProviderExecutionError(
                "AI_PROVIDER_DESTINATION_UNAVAILABLE",
            ) from None
        if type(addresses) is not list:
            raise AIProviderExecutionError("AI_PROVIDER_DESTINATION_REJECTED")
        return tuple(addresses)

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    def _send_over_pinned_tls(
        self, route: AIProviderExecutionRoute,
        operation: Callable[[ssl.SSLSocket, str, str, float], AIProviderResponse],
    ) -> AIProviderResponse:
        """Shared no-proxy/no-redirect transport for approved AI operations."""
        deadline = self._monotonic() + route.total_timeout_seconds
        parts = urlsplit(route.endpoint_url)
        hostname = parts.hostname
        if not hostname:
            raise AIProviderExecutionError("AI_PROVIDER_DESTINATION_REJECTED")
        try:
            addresses = self._resolver(
                hostname, min(route.connect_timeout_seconds,
                              max(.001, deadline - self._monotonic())),
            )
        except AIProviderExecutionError:
            raise
        except Exception:
            raise AIProviderExecutionError(
                "AI_PROVIDER_DESTINATION_UNAVAILABLE",
            ) from None
        if (type(addresses) is not tuple or not 1 <= len(addresses) <= 16
                or any(type(value) is not str
                       or not self._allowed_address(value) for value in addresses)):
            raise AIProviderExecutionError("AI_PROVIDER_DESTINATION_REJECTED")
        last_failure = False
        for address in addresses:
            raw: socket.socket | None = None
            tls: ssl.SSLSocket | None = None
            try:
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    break
                raw = self._connector(
                    address, self.PORT,
                    min(route.connect_timeout_seconds, remaining),
                )
                raw.settimeout(min(
                    route.connect_timeout_seconds,
                    max(.001, deadline - self._monotonic()),
                ))
                context = self._ssl()
                if (not isinstance(context, ssl.SSLContext)
                        or context.minimum_version < ssl.TLSVersion.TLSv1_2
                        or context.check_hostname is not True
                        or context.verify_mode != ssl.CERT_REQUIRED):
                    raise AIProviderExecutionError(
                        "AI_PROVIDER_TLS_POLICY_REJECTED",
                    )
                tls = context.wrap_socket(raw, server_hostname=hostname)
                raw = None
                return operation(tls, hostname, parts.path, deadline)
            except AIProviderExecutionError:
                raise
            except (OSError, ssl.SSLError, TimeoutError):
                last_failure = True
            finally:
                if tls is not None:
                    tls.close()
                if raw is not None:
                    raw.close()
        if last_failure or self._monotonic() >= deadline:
            raise AIProviderExecutionError("AI_PROVIDER_NETWORK_UNAVAILABLE")
        raise AIProviderExecutionError("AI_PROVIDER_DESTINATION_UNAVAILABLE")

    def send(
        self, *, route: AIProviderExecutionRoute, proof: AIProviderSendProof,
        envelope: AIExecutionEnvelope, key: memoryview,
    ) -> AIProviderResponse:
        now = datetime.now(timezone.utc)
        require_provider_send(proof, route, envelope, now=now)
        return self._send_over_pinned_tls(
            route,
            lambda tls, hostname, path, deadline: _PinnedOpenAIConnection(
                tls, hostname=hostname, path=path, route=route,
                deadline=deadline, monotonic=self._monotonic,
            ).send(envelope, key),
        )
