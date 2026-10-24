"""Synthetic SSE transport proof through pinned Caddy HTTPS, not product AI SSE."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threading import Event, Thread

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import uvicorn
from fastapi.responses import StreamingResponse

from audit_caddy_windows_offline_input import EXE_SHA256, audit as audit_caddy, digest
from smoke_caddy_same_origin_https import caddyfile, synthetic_certificate
from smoke_packaged_pg18_migration import verify_layout
from plm_assistant.entrypoints.api import create_app


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def smoke(layout: Path, candidate: Path, caddy_inputs: Path) -> dict:
    count = verify_layout(layout, candidate)
    audit_caddy(caddy_inputs)
    caddy = caddy_inputs / "expanded/caddy.exe"
    if digest(caddy) != EXE_SHA256:
        raise ValueError("pinned Caddy executable changed")
    frontend = layout.resolve(strict=True) / "app/frontend/dist"
    api_port, https_port = free_port(), free_port()
    while api_port == https_port:
        https_port = free_port()
    disconnected = Event()
    app = create_app()

    @app.get("/api/v1/test/synthetic-sse")
    async def synthetic_sse() -> StreamingResponse:
        async def events():
            try:
                yield b"id: 1\nevent: synthetic\ndata: first\n\n"
                await asyncio.sleep(30)
                yield b"id: 2\nevent: synthetic\ndata: late\n\n"
            finally:
                disconnected.set()

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    with tempfile.TemporaryDirectory(prefix="plm-caddy-sse-") as directory:
        root = Path(directory)
        cert, key, config = root / "cert.pem", root / "key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(caddyfile(frontend, cert, key, api_port, https_port), encoding="ascii")
        validated = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                   capture_output=True, text=True, timeout=15)
        if validated.returncode:
            raise ValueError("synthetic SSE Caddyfile invalid")
        sock = socket.socket()
        sock.bind(("127.0.0.1", api_port))
        sock.listen(128)
        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                                               proxy_headers=False, lifespan="on",
                                               timeout_graceful_shutdown=5))
        thread = Thread(target=lambda: server.run(sockets=[sock]), daemon=False)
        child = None
        try:
            thread.start()
            deadline = time.monotonic() + 20
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("owned SSE upstream did not start")
                time.sleep(.05)
            env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PLM_")}
            child = subprocess.Popen([str(caddy), "run", "--config", str(config)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, env=env)
            with httpx.Client(base_url=f"https://localhost:{https_port}", verify=str(cert),
                              timeout=httpx.Timeout(3.0, read=3.0), trust_env=False) as client:
                deadline = time.monotonic() + 20
                while True:
                    if child.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("owned SSE HTTPS boundary did not start")
                    try:
                        if client.get("/health/ready").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(.05)
                rejected = client.get("/api/v1/test/synthetic-sse", headers={
                    "Host": "untrusted.example.test"})
                if rejected.status_code != 421:
                    raise ValueError("untrusted Host reached SSE endpoint")
                started = time.monotonic()
                with client.stream("GET", "/api/v1/test/synthetic-sse",
                                   headers={"Accept": "text/event-stream"}) as response:
                    if response.status_code != 200:
                        raise ValueError("SSE HTTPS request rejected")
                    if not response.headers.get("content-type", "").startswith("text/event-stream"):
                        raise ValueError("SSE content type changed by boundary")
                    if response.headers.get("cache-control") != "no-cache":
                        raise ValueError("SSE no-cache header changed by boundary")
                    lines = response.iter_lines()
                    first_event = [next(lines) for _ in range(4)]
                    first_latency = time.monotonic() - started
                    if first_event != ["id: 1", "event: synthetic", "data: first", ""] or first_latency >= 3:
                        raise ValueError("SSE first event buffered or altered")
                if not disconnected.wait(5):
                    raise ValueError("upstream SSE generator not canceled on client disconnect")
            return {"status": "SYNTHETIC_CADDY_SSE_TRANSPORT_PASS", "release_eligible": False,
                    "payload_file_count": count, "first_event_complete": True,
                    "first_event_latency_under_3s": True, "wrong_host_status": 421,
                    "upstream_disconnect_observed": True, "product_sse_verified": False,
                    "synthetic_tls_only": True, "children_stopped": True}
        finally:
            if child:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=15)
            server.should_exit = True
            if thread.ident is not None:
                thread.join(timeout=15)
                if thread.is_alive():
                    raise RuntimeError("owned SSE upstream did not stop")
            sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--caddy-inputs", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.layout, args.candidate, args.caddy_inputs), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
