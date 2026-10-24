"""Loopback-only synthetic TLS proof; never resolves or calls a vendor."""

from __future__ import annotations

import json
import ssl
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from plm_assistant.modules.ai.application.probe_policy import ProviderProbePlan
from plm_assistant.modules.ai.application.probe_transport_contract import ProbeTransportError
from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.ai.application.run_provider_probe import ProviderProbeExecutionError, ProviderProbeRunner
from plm_assistant.modules.ai.infrastructure.provider_probe_transport import PinnedHttpsProbeTransport
from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.platform.application.secret_access import (
    SecretConsumer, SecretEnvelope, SecretPurpose, SecretRef, SecretResolver, SecretState,
)


SYNTHETIC_KEY = b"synthetic-loopback-token"


def create_certificates(directory: Path) -> tuple[Path, Path, Path]:
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic Probe Root")])
    ca_cert = (
        x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "probe.example.test")])
    leaf_cert = (
        x509.CertificateBuilder().subject_name(leaf_name).issuer_name(ca_name)
        .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("probe.example.test")]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    ca_path, cert_path, key_path = (directory / "ca.pem", directory / "server.pem", directory / "server-key.pem")
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(leaf_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    return ca_path, cert_path, key_path


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    mode = "ok"
    captured = []

    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("content-length", "0")))
        Handler.captured.append((self.path, self.headers.get("Host"),
                                 self.headers.get("Authorization"), raw))
        if Handler.mode == "slow":
            time.sleep(6)
        if Handler.mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "https://other.example.test/v1/chat")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if Handler.mode == "oversize":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "99999")
            self.end_headers()
            return
        body = b'{"choices":[{}]}' if Handler.mode != "invalid" else b"bad"
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass


class SyntheticLoopbackTransport(PinnedHttpsProbeTransport):
    """Validation-only override, never imported by product code."""

    def __init__(self, port: int, ca_path: Path):
        self.PORT = port
        self.ca_path = ca_path

    def _addresses(self, _):
        return ("127.0.0.1",)

    def _ssl_context(self):
        context = ssl.create_default_context(cafile=str(self.ca_path))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context


class UntrustedLoopbackTransport(SyntheticLoopbackTransport):
    def _ssl_context(self):
        return PinnedHttpsProbeTransport._ssl_context()


class Preflight:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def preflight(self, **_):
        self.calls += 1
        return self.snapshot


class Store:
    def __init__(self, envelope):
        self.envelope = envelope

    def load(self, _):
        return self.envelope


class Decryptor:
    def __init__(self):
        self.buffers = []

    def decrypt(self, _):
        value = bytearray(SYNTHETIC_KEY)
        self.buffers.append(value)
        return value


class Audit:
    def record_access(self, **_):
        pass


def main():
    with tempfile.TemporaryDirectory(prefix="plm-probe-tls-") as temp:
        ca_path, cert_path, key_path = create_certificates(Path(temp))
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(str(cert_path), str(key_path))
        server.socket = server_context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            transport = SyntheticLoopbackTransport(server.server_port, ca_path)
            trace = uuid.uuid4()
            plan = ProviderProbePlan(
                uuid.uuid4(), 1, "trusted.synthetic",
                "https://probe.example.test/v1/chat", "synthetic-chat", uuid.uuid4(),
            )
            claim = AIProviderTestClaim(
                uuid.uuid4(), plan.provider_id, uuid.uuid4(), 1,
                uuid.uuid4(), uuid.uuid4(), trace, b"p" * 32, 1, 1,
            )
            preflight = Preflight(ProviderTestPreflightSnapshot(claim, plan))
            decryptor = Decryptor()
            envelope = SecretEnvelope(
                SecretRef(plan.secret_ref), SecretPurpose.AI_PROVIDER_KEY,
                SecretState.ACTIVE, SecretConsumer.AI_PROVIDER_ADAPTER,
                1, b"synthetic-cipher", b"{}", "synthetic-only",
                claim.secret_version_id,
            )
            runner = ProviderProbeRunner(
                preflight=preflight, secrets=SecretResolver(Store(envelope), decryptor, Audit()),
                transport=transport,
            )

            def run():
                return runner.run(job_id=claim.job_id, fencing_token=1,
                                  worker_ref="synthetic-worker", trace_id=trace)

            observed = run()
            assert observed.job_id == claim.job_id and preflight.calls == 3
            path, host, authorization, raw = Handler.captured[-1]
            assert (path, host, authorization) == (
                "/v1/chat", "probe.example.test", "Bearer " + SYNTHETIC_KEY.decode(),
            )
            parsed = json.loads(raw)
            assert parsed == {"model": "synthetic-chat",
                              "messages": [{"role": "user", "content": "ping"}],
                              "max_tokens": 1, "stream": False}
            assert all(not any(buffer) for buffer in decryptor.buffers)
            before_untrusted = len(Handler.captured)
            try:
                UntrustedLoopbackTransport(server.server_port, ca_path).open(plan)
            except ProbeTransportError as exc:
                assert exc.code == "PROBE_NETWORK_UNAVAILABLE"
            else:
                raise AssertionError("untrusted TLS certificate accepted")
            assert len(Handler.captured) == before_untrusted
            for mode, code in (("redirect", "PROBE_HTTP_REJECTED"),
                               ("oversize", "PROBE_PROTOCOL_REJECTED"),
                               ("invalid", "PROBE_PROTOCOL_REJECTED"),
                               ("slow", "PROBE_NETWORK_UNAVAILABLE")):
                Handler.mode = mode
                before = len(Handler.captured)
                try:
                    run()
                except ProviderProbeExecutionError as exc:
                    assert exc.code == code, (mode, exc.code)
                else:
                    raise AssertionError(f"{mode} response accepted")
                assert len(Handler.captured) == before + 1
            assert all(not any(buffer) for buffer in decryptor.buffers)
            print("PASS: loopback TLS hostname/certificate, fixed probe, no redirects, bounded/invalid/timeout failure, zeroized synthetic Key")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
