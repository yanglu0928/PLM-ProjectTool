"""Windows 11 local synthetic TLS proof for the OpenAI-compatible Adapter."""

from __future__ import annotations

import json
import socket
import ssl
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope
from plm_assistant.modules.ai.application.provider_execution_contract import (
    AIProviderExecutionRoute,
    AIProviderSendProof,
    provider_route_fingerprint,
)
from plm_assistant.modules.ai.domain.provider_configuration import ProviderKind
from plm_assistant.modules.ai.infrastructure.openai_compatible_adapter import (
    PinnedHttpsOpenAICompatibleAdapter,
)


HOSTNAME = "api.example.test"


def certificate(root: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOSTNAME)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(minutes=10))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(HOSTNAME)]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = root / "cert.pem", root / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    return cert_path, key_path


def fixture():
    route = AIProviderExecutionRoute(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        ProviderKind.OPENAI_COMPATIBLE, "endpoint.synthetic-tls.v1",
        f"https://{HOSTNAME}/v1/chat/completions",
        uuid.uuid4(), uuid.uuid4(), "synthetic-chat", "PROVIDER_MANAGED",
        "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED", 65_536, 3, 5, 10,
    )
    canonical = json.dumps({
        "messages": [
            {"content": "system synthetic", "role": "system"},
            {"content": "user synthetic", "role": "user"},
        ],
        "model": {"key": "synthetic-chat", "revision": "PROVIDER_MANAGED"},
        "response_format": {
            "schema_ref": "synthetic-output.v1", "schema_version": 1,
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
        datetime.now(timezone.utc) + timedelta(minutes=2),
    )
    return route, envelope, proof


def read_request(connection: ssl.SSLSocket) -> tuple[bytes, bytes]:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        part = connection.recv(4096)
        assert part
        data.extend(part)
    head, _, body = data.partition(b"\r\n\r\n")
    lengths = [line.split(b":", 1)[1].strip() for line in head.split(b"\r\n")
               if line.lower().startswith(b"content-length:")]
    assert len(lengths) == 1 and lengths[0].isdigit()
    expected = int(lengths[0])
    while len(body) < expected:
        part = connection.recv(4096)
        assert part
        body.extend(part)
    return bytes(head), bytes(body)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="plm-ai-adapter-tls-") as temporary:
        root = Path(temporary)
        cert_path, key_path = certificate(root)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.minimum_version = ssl.TLSVersion.TLSv1_2
        server_context.load_cert_chain(cert_path, key_path)
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        observed: dict[str, object] = {}
        failures: list[BaseException] = []

        def serve() -> None:
            try:
                raw, _ = listener.accept()
                with raw, server_context.wrap_socket(raw, server_side=True) as tls:
                    head, body = read_request(tls)
                    observed["head"] = head
                    observed["body"] = json.loads(body)
                    response = json.dumps({
                        "choices": [{
                            "message": {"content": '{"synthetic":true}'},
                            "finish_reason": "stop",
                        }],
                        "usage": {"prompt_tokens": 20, "completion_tokens": 3},
                    }, separators=(",", ":")).encode()
                    tls.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                        + f"Content-Length: {len(response)}\r\nConnection: close\r\n\r\n".encode()
                        + response
                    )
            except BaseException as error:
                failures.append(error)
            finally:
                listener.close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()

        def client_context() -> ssl.SSLContext:
            context = ssl.create_default_context(cafile=str(cert_path))
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            return context

        adapter = PinnedHttpsOpenAICompatibleAdapter(
            address_resolver=lambda hostname, timeout: ("8.8.8.8",),
            connector=lambda address, requested_port, timeout: socket.create_connection(
                ("127.0.0.1", port), timeout=timeout,
            ),
            ssl_context_factory=client_context,
        )
        route, envelope, proof = fixture()
        key = bytearray(b"synthetic-key-no-provider")
        response = adapter.send(
            route=route, proof=proof, envelope=envelope, key=memoryview(key),
        )
        thread.join(timeout=5)
        assert not thread.is_alive() and not failures, failures
        head = observed["head"]
        body = observed["body"]
        assert head.startswith(b"POST /v1/chat/completions HTTP/1.1\r\n")
        assert f"Host: {HOSTNAME}".encode() in head
        assert b"Proxy-Authorization" not in head and b"http://" not in head
        assert b"Authorization: Bearer synthetic-key-no-provider" in head
        assert body == {
            "messages": [
                {"content": "system synthetic", "role": "system"},
                {"content": "user synthetic", "role": "user"},
            ],
            "model": "synthetic-chat",
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        assert response.observation.finish_reason == "STOP"
        assert response.observation.input_tokens == 20
        assert response.observation.output_tokens == 3
        assert b"synthetic" in bytes(response.view())
        response.close()
        assert ip_address("8.8.8.8").is_global
        assert key == bytearray(b"synthetic-key-no-provider")
        key[:] = b"\x00" * len(key)
    print(
        "AI_04_A06_P06_P04_OPENAI_ADAPTER_PASS: Windows11 local synthetic TLS "
        "completed one pinned origin-form OpenAI-compatible request using the exact approved "
        "messages/model, strict certificate hostname verification, no proxy/redirect, bounded "
        "Content-Length response and zeroed response ownership; no real Provider or customer data"
    )


if __name__ == "__main__":
    main()
