"""Diagnose Caddy's observed Host over synthetic loopback HTTPS; no package changes."""

from __future__ import annotations

import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_caddy_windows_offline_input import EXE_SHA256, audit, digest
from smoke_caddy_same_origin_https import synthetic_certificate


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(port: int, context: ssl.SSLContext, hosts: list[str]) -> tuple[int, str]:
    connection = http.client.HTTPSConnection("localhost", port, timeout=3, context=context)
    try:
        connection.putrequest("GET", "/", skip_host=True)
        for value in hosts:
            connection.putheader("Host", value)
        connection.endheaders()
        response = connection.getresponse()
        return response.status, response.read(256).decode("utf-8", errors="replace")
    finally:
        connection.close()


def probe(caddy_inputs: Path) -> dict:
    audit(caddy_inputs)
    caddy = caddy_inputs / "expanded/caddy.exe"
    if digest(caddy) != EXE_SHA256:
        raise ValueError("Caddy input changed")
    port = _port()
    with tempfile.TemporaryDirectory(prefix="plm-caddy-host-") as temp:
        root = Path(temp)
        cert, key, config = root / "cert.pem", root / "key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(
            "{\n admin off\n auto_https disable_redirects\n}\n"
            f"https://localhost:{port} {{\n tls \"{cert}\" \"{key}\"\n"
            " respond \"{http.request.host}\" 200\n}\n"
            f"https://:{port} {{\n tls \"{cert}\" \"{key}\"\n"
            " respond \"Misdirected Request\" 421\n}\n", encoding="ascii")
        validate = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                  capture_output=True, text=True, timeout=15)
        if validate.returncode:
            raise ValueError("synthetic Caddyfile invalid")
        env = dict(os.environ)
        child = subprocess.Popen([str(caddy), "run", "--config", str(config)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=env)
        context = ssl.create_default_context(cafile=str(cert))
        try:
            deadline = time.monotonic() + 10
            while True:
                if child.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("Caddy host diagnostic did not become ready")
                try:
                    good = _request(port, context, [f"localhost:{port}"])
                    break
                except (OSError, ssl.SSLError):
                    time.sleep(.1)
            wrong = _request(port, context, ["untrusted.example.test"])
            duplicate = _request(port, context, [f"localhost:{port}", "untrusted.example.test"])
            return {"good": {"status": good[0], "observed_host": good[1]},
                    "wrong": {"status": wrong[0], "observed_host": wrong[1]},
                    "duplicate": {"status": duplicate[0], "observed_host": duplicate[1]},
                    "synthetic_only": True, "release_eligible": False}
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=15)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: probe_caddy_host_boundary.py <pinned-caddy-inputs>")
    print(json.dumps(probe(Path(sys.argv[1])), ensure_ascii=False, indent=2))
