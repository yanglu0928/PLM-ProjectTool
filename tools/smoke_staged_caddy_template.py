"""Render the exact staged P22 Caddy template with synthetic TLS and smoke HTTPS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_caddy_windows_offline_input import EXE_SHA256, digest
from build_windows_unified_caddy_candidate import KIND, TEMPLATE_SHA256
from smoke_caddy_same_origin_https import (
    fetch, free_port, host_status, synthetic_certificate, wait_ready,
)
from smoke_packaged_http_frontend import _ready as api_ready, parse_assets
from verify_windows_unified_caddy_candidate import verify as verify_source
from verify_windows_unified_extract import verify as verify_stage


def render(template: str, *, cert: Path, key: Path, frontend: Path,
           api_port: int, https_port: int) -> str:
    for path in (cert, key, frontend):
        if not path.is_absolute() or not str(path).isascii() or any(char in str(path) for char in '"\r\n{}'):
            raise ValueError("synthetic Caddy path rejected")
    if not all(1 <= port <= 65535 for port in (api_port, https_port)) or api_port == https_port:
        raise ValueError("synthetic Caddy ports rejected")
    substitutions = {
        "__PUBLIC_HOST__": f"localhost:{https_port}",
        "__TLS_CERT_PATH__": str(cert),
        "__TLS_KEY_PATH__": str(key),
        "__API_PORT__": str(api_port),
        "__FRONTEND_ROOT__": str(frontend),
        "https://:443 {": f"https://:{https_port} {{",
    }
    for token, value in substitutions.items():
        if token not in template:
            raise ValueError(f"staged Caddy template lacks expected token: {token}")
        template = template.replace(token, value)
    if any(token in template for token in substitutions):
        raise ValueError("staged Caddy template has unresolved token")
    return template


def smoke(stage: Path, candidate: Path) -> dict:
    source = verify_source(candidate)
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != source["payload_file_count"]:
        raise ValueError("staged payload count changed")
    stage = stage.resolve(strict=True)
    caddy = stage / "payload/web/caddy.exe"
    template = stage / "payload/config/Caddyfile.template"
    frontend = stage / "payload/frontend/dist"
    runtime = stage / "payload/runtime"
    if digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256:
        raise ValueError("staged Caddy/template identity changed")
    index = frontend / "index.html"
    assets = parse_assets(index.read_text(encoding="utf-8"))
    api_port, https_port = free_port(), free_port()
    while api_port == https_port:
        https_port = free_port()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    children: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="plm-caddy-template-") as directory:
        root = Path(directory)
        cert, key, config = root / "synthetic-cert.pem", root / "synthetic-key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(render(template.read_text(encoding="ascii"), cert=cert, key=key,
                                 frontend=frontend, api_port=api_port, https_port=https_port), encoding="ascii")
        validated = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                   capture_output=True, text=True, errors="replace", timeout=15)
        if validated.returncode:
            raise ValueError(f"rendered staged Caddyfile invalid: {validated.stderr[-400:]}")
        context = ssl.create_default_context(cafile=str(cert))
        try:
            api = subprocess.Popen([str(runtime / "python.exe"), "-I", "-B", "-m", "uvicorn",
                                    "plm_assistant.entrypoints.api:create_app", "--factory",
                                    "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=env)
            children.append(api)
            ready_status, ready_body, _ = api_ready(f"http://127.0.0.1:{api_port}/health/ready", api)
            if ready_status != 200 or ready_body != b'{"status":"UP"}':
                raise ValueError("staged packaged API not ready")
            caddy_child = subprocess.Popen([str(caddy), "run", "--config", str(config)],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, env=env)
            children.append(caddy_child)
            base = f"https://localhost:{https_port}"
            wait_ready(base + "/", context, caddy_child)
            index_status, page, _ = fetch(base + "/", context)
            if index_status != 200 or page != index.read_bytes():
                raise ValueError("staged HTTPS index differs")
            for asset in assets:
                status, body, _ = fetch(base + asset, context)
                if status != 200 or hashlib.sha256(body).digest() != hashlib.sha256(
                        (frontend / asset.removeprefix("/")).read_bytes()).digest():
                    raise ValueError("staged HTTPS frontend asset differs")
            health, health_body, _ = fetch(base + "/health/ready", context)
            absent, absent_body, _ = fetch(base + "/api/v1/projects", context)
            deep, deep_body, _ = fetch(base + "/projects/synthetic-deep-link", context)
            wrong_host, _ = host_status(https_port, context, ["untrusted.example.test"])
            if (health != 200 or health_body != b'{"status":"UP"}' or absent != 404
                    or b"<html" in absent_body.lower() or deep != 200 or deep_body != page
                    or wrong_host != 421):
                raise ValueError("rendered staged HTTPS route rejected")
            return {"status": "NON_RELEASE_STAGED_CADDY_TEMPLATE_HTTPS_PASS",
                    "release_eligible": False, "candidate_sha256": source["archive_sha256"],
                    "payload_file_count": 21110, "frontend_asset_count": len(assets),
                    "health_ready": health, "default_api_route": absent,
                    "spa_deep_link": deep, "wrong_host_status": wrong_host,
                    "synthetic_tls_only": True, "installation_performed": False,
                    "children_stopped": True}
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.stage, args.candidate), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
