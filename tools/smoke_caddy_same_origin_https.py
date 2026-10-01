"""Isolated Caddy HTTPS static/API routing PoC against the pinned NON-RELEASE layout.

Uses a temporary synthetic certificate and loopback ports only. No SCM/DB changes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# The embeddable Python runtime uses a fixed ._pth and omits the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from audit_caddy_windows_offline_input import EXE_SHA256, audit as audit_caddy, digest
from smoke_packaged_http_frontend import _ready as api_ready, parse_assets
from smoke_packaged_pg18_migration import verify_layout


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def caddyfile(frontend: Path, cert: Path, key: Path, api_port: int, https_port: int) -> str:
    for path in (frontend, cert, key):
        if not path.is_absolute() or not str(path).isascii() or any(char in str(path) for char in "\r\n{}\""):
            raise ValueError("Caddy PoC paths must be absolute ASCII and safe")
    if not all(1 <= port <= 65535 for port in (api_port, https_port)) or api_port == https_port:
        raise ValueError("invalid isolated ports")
    return ("{\n    admin off\n    auto_https disable_redirects\n}\n"
            f"https://localhost:{https_port} {{\n"
            f"    tls \"{cert}\" \"{key}\"\n"
            "    @api path /api/v1 /api/v1/* /health /health/*\n"
            "    handle @api {\n"
            f"        reverse_proxy 127.0.0.1:{api_port}\n"
            "    }\n"
            "    @unknown_api path /api /api/*\n"
            "    handle @unknown_api {\n"
            "        respond \"Not Found\" 404\n"
            "    }\n"
            "    handle {\n"
            f"        root * \"{frontend}\"\n"
            "        try_files {path} /index.html\n"
            "        file_server\n"
            "    }\n}\n")


def synthetic_certificate(cert: Path, key: Path) -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = dt.datetime.now(dt.timezone.utc)
    signed = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(private.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - dt.timedelta(minutes=1))
              .not_valid_after(now + dt.timedelta(hours=2))
              .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
              .sign(private, hashes.SHA256()))
    key.write_bytes(private.private_bytes(serialization.Encoding.PEM,
                                          serialization.PrivateFormat.TraditionalOpenSSL,
                                          serialization.NoEncryption()))
    cert.write_bytes(signed.public_bytes(serialization.Encoding.PEM))


def fetch(url: str, context: ssl.SSLContext) -> tuple[int, bytes, dict[str, str]]:
    request = Request(url)
    try:
        with urlopen(request, context=context, timeout=3) as response:
            return response.status, response.read(), {k.lower(): v for k, v in response.headers.items()}
    except HTTPError as error:
        return error.code, error.read(), {k.lower(): v for k, v in error.headers.items()}


def wrong_host_status(port: int, context: ssl.SSLContext) -> int:
    connection = http.client.HTTPSConnection("localhost", port, context=context, timeout=3)
    try:
        connection.putrequest("GET", "/", skip_host=True)
        connection.putheader("Host", "untrusted.example.test")
        connection.endheaders()
        response = connection.getresponse()
        response.read()
        return response.status
    finally:
        connection.close()


def wait_ready(url: str, context: ssl.SSLContext, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Caddy exited before isolated HTTPS readiness")
        try:
            if fetch(url, context)[0] == 200:
                return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(.1)
    raise TimeoutError("isolated HTTPS boundary did not become ready")


def smoke(layout: Path, candidate: Path, caddy_inputs: Path) -> dict:
    audit_caddy(caddy_inputs)
    caddy = caddy_inputs / "expanded/caddy.exe"
    if not caddy.is_file() or digest(caddy) != EXE_SHA256:
        raise ValueError("extracted Caddy executable differs from official pinned ZIP")
    count = verify_layout(layout, candidate)
    layout = layout.resolve(strict=True)
    frontend = layout / "app/frontend/dist"
    index = frontend / "index.html"
    assets = parse_assets(index.read_text(encoding="utf-8"))
    runtime = layout / "runtime/python"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    api_port, https_port = free_port(), free_port()
    while https_port == api_port:
        https_port = free_port()
    children: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="plm-caddy-https-") as temporary:
        root = Path(temporary)
        cert, key, config = root / "synthetic-cert.pem", root / "synthetic-key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(caddyfile(frontend, cert, key, api_port, https_port), encoding="ascii")
        checked = subprocess.run([str(caddy), "validate", "--config", str(config), "--adapter", "caddyfile"],
                                 capture_output=True, text=True, errors="replace", timeout=15, check=False)
        if checked.returncode:
            raise ValueError(f"isolated Caddyfile rejected: {checked.stderr[-400:]}")
        context = ssl.create_default_context(cafile=str(cert))
        try:
            api = subprocess.Popen([str(runtime / "python.exe"), "-I", "-B", "-m", "uvicorn",
                                    "plm_assistant.entrypoints.api:create_app", "--factory",
                                    "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=env)
            children.append(api)
            api_status, api_body, _ = api_ready(f"http://127.0.0.1:{api_port}/health/ready", api)
            if api_status != 200 or api_body != b'{"status":"UP"}':
                raise ValueError("packaged API not ready before HTTPS proxy")
            caddy_process = subprocess.Popen([str(caddy), "run", "--config", str(config), "--adapter", "caddyfile"],
                                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                             stderr=subprocess.DEVNULL, env=env)
            children.append(caddy_process)
            base = f"https://localhost:{https_port}"
            wait_ready(base + "/", context, caddy_process)
            status, page, _ = fetch(base + "/", context)
            if status != 200 or hashlib.sha256(page).digest() != hashlib.sha256(index.read_bytes()).digest():
                raise ValueError("HTTPS index differs from pinned frontend")
            for asset in assets:
                code, body, _ = fetch(base + asset, context)
                if code != 200 or body != (frontend / asset.removeprefix("/")).read_bytes():
                    raise ValueError("HTTPS frontend asset mismatch")
            deep_status, deep_body, _ = fetch(base + "/projects/synthetic-deep-link", context)
            ready_status, ready_body, headers = fetch(base + "/health/ready", context)
            live_status, live_body, _ = fetch(base + "/health/live", context)
            absent_api, absent_body, _ = fetch(base + "/api/v1/projects", context)
            unknown_api, unknown_body, _ = fetch(base + "/api/v2/synthetic", context)
            bad_host = wrong_host_status(https_port, context)
            if (deep_status != 200 or deep_body != page or ready_status != 200
                    or ready_body != b'{"status":"UP"}' or headers.get("cache-control") != "no-store"
                    or live_status != 200 or live_body != b'{"status":"UP"}'
                    or absent_api != 404 or b"<html" in absent_body.lower()
                    or unknown_api != 404 or b"<html" in unknown_body.lower()):
                raise ValueError("HTTPS same-origin route or host boundary rejected: "
                                 f"deep={deep_status}, ready={ready_status}, live={live_status}, "
                                 f"api={absent_api}, unknown_api={unknown_api}, bad_host={bad_host}, "
                                 f"ready_body={ready_body[:80]!r}, live_body={live_body[:80]!r}")
            return {"status": "SYNTHETIC_CADDY_HTTPS_ROUTING_PASS_HOST_OPEN", "release_eligible": False,
                    "payload_file_count": count, "frontend_asset_count": len(assets),
                    "health_ready": 200, "health_live": 200, "default_api_route": absent_api,
                    "unknown_api_route": unknown_api, "spa_deep_link": deep_status,
                    "untrusted_host_status": bad_host, "host_rejection_verified": False,
                    "synthetic_tls_only": True,
                    "production_login_verified": False, "sse_verified": False,
                    "children_stopped": True}
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"isolated HTTPS child did not stop: {child.pid}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--caddy-inputs", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.layout, args.candidate, args.caddy_inputs), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
