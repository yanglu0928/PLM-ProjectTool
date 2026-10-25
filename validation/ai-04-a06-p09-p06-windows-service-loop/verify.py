"""Windows 11 proof of the real service loop against a local synthetic TLS peer."""

from __future__ import annotations

import importlib.util
import json
import socket
import ssl
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from psycopg.types.json import Jsonb

from plm_assistant.entrypoints import service_windows
from plm_assistant.entrypoints import windows_ai_provider_worker as entry
from plm_assistant.modules.ai.infrastructure.openai_compatible_adapter import (
    PinnedHttpsOpenAICompatibleAdapter,
)
from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer,
    SecretPurpose,
    SecretRef,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
    BootstrapSettings,
)
from plm_assistant.modules.platform.infrastructure.secret_crypto import (
    AesGcmSecretCrypto,
)


HOSTNAME = "provider.synthetic.test"
PROVIDER_KEY = b"synthetic-task-key-not-for-network"


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedActor:
    def __init__(self, actor_id: uuid.UUID) -> None:
        self.actor_id = actor_id

    def assert_current(self) -> uuid.UUID:
        return self.actor_id


class SyntheticKeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def resolve_key(self, key_ref: str) -> bytes:
        assert key_ref == entry.SECRET_MASTER_KEY_REF
        self.calls += 1
        return b"w" * 32


class LocalTLSProvider:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.received = threading.Event()
        self.errors: list[BaseException] = []
        self.request: dict[str, object] | None = None
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(1)
        self._server.settimeout(10)
        self.port = self._server.getsockname()[1]
        self.ca_path, self.cert_path, self.key_path = self._certificates()
        self._thread = threading.Thread(
            target=self._serve, name="synthetic-ai-provider", daemon=False,
        )

    def _certificates(self) -> tuple[Path, Path, Path]:
        now = datetime.now(timezone.utc)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(
            NameOID.COMMON_NAME, "PLM synthetic validation CA",
        )])
        ca = (
            x509.CertificateBuilder()
            .subject_name(ca_name).issuer_name(ca_name)
            .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .add_extension(x509.KeyUsage(
                digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=None, decipher_only=None,
            ), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                ca_key.public_key(),
            ), False)
            .sign(ca_key, hashes.SHA256())
        )
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOSTNAME)])
        server = (
            x509.CertificateBuilder()
            .subject_name(server_name).issuer_name(ca.subject)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOSTNAME)]), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=True, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=None, decipher_only=None,
            ), True)
            .add_extension(x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
            ]), False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                server_key.public_key(),
            ), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                ca_key.public_key(),
            ), False)
            .sign(ca_key, hashes.SHA256())
        )
        ca_path, cert_path, key_path = (
            self.root / "ca.pem", self.root / "server.pem",
            self.root / "server-key.pem",
        )
        ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        cert_path.write_bytes(server.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        return ca_path, cert_path, key_path

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.close()
        self._thread.join(10)
        if self._thread.is_alive():
            raise AssertionError("synthetic TLS Provider did not stop")
        if self.errors:
            raise self.errors[0]

    def connector(self, _address: str, _port: int, timeout: float):
        return socket.create_connection(("127.0.0.1", self.port), timeout=timeout)

    def client_context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(cafile=str(self.ca_path))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context

    def _serve(self) -> None:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(str(self.cert_path), str(self.key_path))
            raw, _ = self._server.accept()
            with raw, context.wrap_socket(raw, server_side=True) as peer:
                received = bytearray()
                while b"\r\n\r\n" not in received:
                    part = peer.recv(4096)
                    assert part and len(received) + len(part) <= 262144
                    received.extend(part)
                head, _, body = received.partition(b"\r\n\r\n")
                lines = bytes(head).split(b"\r\n")
                assert lines[0] == b"POST /v1/chat/completions HTTP/1.1"
                headers = {}
                for line in lines[1:]:
                    name, value = line.split(b":", 1)
                    headers[name.lower()] = value.strip()
                assert headers[b"host"] == HOSTNAME.encode("ascii")
                assert headers[b"authorization"] == b"Bearer " + PROVIDER_KEY
                expected = int(headers[b"content-length"])
                while len(body) < expected:
                    part = peer.recv(expected - len(body))
                    assert part
                    body.extend(part)
                assert len(body) == expected
                self.request = json.loads(bytes(body).decode("utf-8"))
                assert self.request["model"] == "content-plan-chat"
                assert self.request["stream"] is False
                assert len(self.request["messages"]) == 2
                content = json.dumps({
                    "schema_ref": "gap-output.v1", "schema_version": 1,
                    "items": [{
                        "category": "PENDING_CONFIRMATION",
                        "title": "合成服务循环",
                        "summary": "仅验证本机 TLS 与生产 Worker。",
                        "rationale": "输入和响应均为合成数据。",
                        "recommendation": "后续仍需人工确认正式业务事实。",
                        "source_ordinals": [1],
                    }],
                }, ensure_ascii=False, separators=(",", ":"))
                response = json.dumps({
                    "choices": [{
                        "message": {"content": content},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 40, "completion_tokens": 20},
                }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                peer.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(response)}\r\n".encode("ascii")
                    + b"Connection: close\r\n\r\n" + response
                )
                received[:] = b"\x00" * len(received)
                body[:] = b"\x00" * len(body)
            self.received.set()
        except BaseException as error:
            self.errors.append(error)
            self.received.set()


def validate(context: dict[str, object]) -> None:
    schema = load_helper(
        "ai-04-a06-p04-p02-content-plan-schema", "p09p06_schema_helper",
    )
    key_provider = SyntheticKeyProvider()
    crypto = AesGcmSecretCrypto(key_provider, key_ref=entry.SECRET_MASTER_KEY_REF)
    plaintext = bytearray(PROVIDER_KEY)
    with schema.connect(context["database"]) as db:
        task = db.execute(
            "SELECT task_type,prompt_policy_ref,prompt_policy_version,"
            "prompt_template_ref,output_schema_ref,context_policy_ref "
            "FROM plm.ai_tasks WHERE ai_task_id=%s",
            (context["ai_task_id"],),
        ).fetchone()
        route = db.execute(
            "SELECT c.endpoint_policy_ref,c.data_region,c.egress_class,"
            "m.provider_model_key,c.secret_ref,c.created_by "
            "FROM plm.ai_provider_config_versions c JOIN plm.ai_models m "
            "ON m.ai_provider_id=c.ai_provider_id WHERE c.config_version_no=1",
        ).fetchone()
        username = "service-loop-system-" + uuid.uuid4().hex[:12]
        actor_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username),
        ).fetchone()[0]
        secret_version = uuid.uuid4()
        draft = crypto.encrypt(
            secret_ref=SecretRef(route[4]), purpose=SecretPurpose.AI_PROVIDER_KEY,
            consumer=SecretConsumer.AI_PROVIDER_ADAPTER, version_no=1,
            plaintext=plaintext,
        )
        assert not any(plaintext)
        with db.transaction():
            db.execute(
                "INSERT INTO plm.plt_secret_versions(secret_version_id,secret_record_id,"
                "version_no,encrypted_payload,encryption_metadata,key_provider_ref,"
                "created_by,activated_at) VALUES (%s,%s,1,%s,%s,%s,%s,"
                "statement_timestamp())",
                (secret_version, route[4], draft.encrypted_payload,
                 Jsonb(json.loads(draft.encryption_metadata)),
                 draft.key_provider_ref, route[5]),
            )
            db.execute(
                "UPDATE plm.plt_secret_records SET secret_state='ACTIVE',"
                "current_version_ref=%s,lock_version=lock_version+1,"
                "updated_at=statement_timestamp() WHERE secret_record_id=%s",
                (secret_version, route[4]),
            )
    settings = BootstrapSettings(
        data_root=context["result_root"],
        ai_task_policies=({
            "reference": task[1], "policy_version": task[2],
            "task_type": task[0], "prompt_template_id": str(task[3]),
            "purpose_ref": "project-gap-analysis.v1",
            "output_schema_ref": task[4], "context_policy_ref": task[5],
            "parameter_fields": [{
                "name": "language", "value_type": "STRING", "required": True,
                "max_length": 16, "minimum": None, "maximum": None,
                "allowed_values": [],
            }],
        },),
        ai_execution_policies=({
            "reference": route[0], "kind": "OPENAI_COMPATIBLE",
            "endpoint_url": f"https://{HOSTNAME}/v1/chat/completions",
            "data_region": route[1], "egress_class": route[2],
            "allowed_model_keys": [route[3]], "max_response_bytes": 1_000_000,
            "connect_timeout_seconds": 3, "read_timeout_seconds": 10,
            "total_timeout_seconds": 20,
        },),
    )
    tls_root = Path(tempfile.mkdtemp(prefix="plm-ai-provider-tls-"))
    provider = LocalTLSProvider(tls_root)
    database = None
    stop, ready = threading.Event(), threading.Event()
    service_errors: list[BaseException] = []
    try:
        with patch.object(entry, "read_database_url", return_value=context["url"]), \
             patch.object(
                 entry, "create_windows_worker_license_services",
                 return_value=SimpleNamespace(guard=context["guard"]),
             ), \
             patch.object(entry, "create_windows_system_actor",
                          return_value=FixedActor(actor_id)), \
             patch.object(entry, "WindowsSecretKeyProvider",
                          return_value=key_provider):
            database, loop = entry.create_windows_ai_provider_loop(settings)
        loop._task._sender._adapter = PinnedHttpsOpenAICompatibleAdapter(
            address_resolver=lambda hostname, _timeout: (
                "93.184.216.34",
            ) if hostname == HOSTNAME else (),
            connector=provider.connector,
            ssl_context_factory=provider.client_context,
        )
        provider.start()

        def run_service() -> None:
            try:
                service_windows.run_ai_provider_loop_service(
                    database, loop, context["result_root"], stop, ready.set,
                )
            except BaseException as error:
                service_errors.append(error)

        service = threading.Thread(
            target=run_service, name="synthetic-ai-provider-service", daemon=False,
        )
        service.start()
        assert ready.wait(5)
        assert provider.received.wait(10)
        deadline = time.monotonic() + 10
        terminal = None
        while time.monotonic() < deadline:
            with schema.connect(context["database"]) as db:
                terminal = db.execute(
                    "SELECT t.task_state,t.suggestion_state,i.invocation_state,"
                    "j.state,l.state FROM plm.ai_tasks t JOIN plm.ai_invocations i "
                    "ON i.ai_invocation_id=t.current_invocation_ref JOIN plm.job_jobs j "
                    "ON j.job_id=t.job_ref JOIN plm.job_leases l ON l.job_id=j.job_id "
                    "AND l.fencing_token=j.fencing_token WHERE t.ai_task_id=%s",
                    (context["ai_task_id"],),
                ).fetchone()
            if terminal == (
                    "SUCCEEDED", "AVAILABLE", "SUCCEEDED", "SUCCEEDED", "RELEASED"):
                break
            time.sleep(.05)
        assert terminal == (
            "SUCCEEDED", "AVAILABLE", "SUCCEEDED", "SUCCEEDED", "RELEASED",
        )
        stop.set()
        service.join(10)
        assert not service.is_alive() and not service_errors
        assert provider.request is not None
        with schema.connect(context["database"]) as db:
            facts = db.execute(
                "SELECT (SELECT count(*) FROM plm.ai_invocations WHERE ai_task_id=%s),"
                "(SELECT count(*) FROM plm.ai_suggestion_payloads s JOIN "
                "plm.ai_invocations i ON i.suggestion_payload_ref=s.suggestion_payload_id "
                "WHERE i.ai_task_id=%s),"
                "(SELECT count(*) FROM plm.aud_events WHERE trace_id=(SELECT trace_id "
                "FROM plm.ai_tasks WHERE ai_task_id=%s) AND "
                "action='AI_PROVIDER_SECRET_ACCESS' AND outcome='SUCCESS')",
                (context["ai_task_id"], context["ai_task_id"],
                 context["ai_task_id"]),
            ).fetchone()
        assert facts == (1, 1, 1)
        assert key_provider.calls >= 2
        assert not any((context["result_root"] / ".plm-runtime-processes").glob("*.json"))
    finally:
        stop.set()
        try:
            provider.close()
        finally:
            if database is not None:
                try:
                    database.dispose()
                except Exception:
                    pass
            for path in (provider.key_path, provider.cert_path, provider.ca_path):
                if path.is_file() and path.parent == tls_root:
                    path.unlink()
            if tls_root.is_dir() and tls_root.parent == Path(tempfile.gettempdir()):
                tls_root.rmdir()
    print(
        "AI_04_A06_P09_P06_WINDOWS_SERVICE_LOOP_PASS: Windows11/PostgreSQL18.6 "
        "real SCM loop lifecycle, AES-GCM Secret resolver/audit, production pinned "
        "HTTPS Adapter and local CA-validated synthetic TLS Provider completed one "
        "business Task with one Invocation/Suggestion/send; cooperative stop drained, "
        "runtime marker removed and database disposed; zero real Provider or customer "
        "data egress"
    )


def main() -> None:
    composition = load_helper(
        "ai-04-a06-p04-p04-a06-windows-composition", "p09p06_composition",
    )
    composition.main(after_validation=validate)


if __name__ == "__main__":
    main()
