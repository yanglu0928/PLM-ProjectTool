"""Probe packaged public health HTTP and frontend assets on loopback only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from smoke_packaged_pg18_migration import verify_layout


ASSET_RE = re.compile(r'(?:src|href)="(/assets/[A-Za-z0-9_.-]+)"')


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def parse_assets(index: str) -> list[str]:
    paths = ASSET_RE.findall(index)
    if len(paths) != 2 or len(set(paths)) != 2 or not any(path.endswith(".js") for path in paths) or not any(path.endswith(".css") for path in paths):
        raise ValueError("packaged frontend entry assets rejected")
    return paths


def _fetch(url: str) -> tuple[int, bytes, dict[str, str]]:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status, response.read(), {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as error:
        return error.code, error.read(), {key.lower(): value for key, value in error.headers.items()}


def _ready(url: str, process: subprocess.Popen[bytes], *, seconds: float = 30) -> tuple[int, bytes, dict[str, str]]:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("isolated packaged HTTP child exited before readiness")
        try:
            return _fetch(url)
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(.1)
    raise TimeoutError("isolated packaged HTTP child did not bind loopback")


def smoke(root: Path, candidate: Path) -> dict:
    count = verify_layout(root, candidate)
    root = root.resolve(strict=True)
    runtime = root / "runtime/python"
    frontend = root / "app/frontend/dist"
    index_file = frontend / "index.html"
    assets = parse_assets(index_file.read_text(encoding="utf-8"))
    for path in assets:
        if not (frontend / path.removeprefix("/")).is_file():
            raise ValueError("packaged frontend asset missing")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    api_port, web_port = _port(), _port()
    if api_port == web_port:
        web_port = _port()
    children: list[subprocess.Popen[bytes]] = []
    try:
        api = subprocess.Popen([str(runtime / "python.exe"), "-I", "-B", "-m", "uvicorn",
                                "plm_assistant.entrypoints.api:create_app", "--factory",
                                "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env=env)
        children.append(api)
        web = subprocess.Popen([str(runtime / "python.exe"), "-I", "-B", "-m", "http.server",
                                str(web_port), "--bind", "127.0.0.1", "--directory", str(frontend)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env=env)
        children.append(web)
        api_url = f"http://127.0.0.1:{api_port}"
        web_url = f"http://127.0.0.1:{web_port}"
        ready_status, ready_body, ready_headers = _ready(api_url + "/health/ready", api)
        live_status, live_body, _ = _fetch(api_url + "/health/live")
        absent_status, _, _ = _fetch(api_url + "/api/v1/projects")
        if (ready_status != 200 or live_status != 200 or ready_body != b'{"status":"UP"}'
                or live_body != b'{"status":"UP"}' or ready_headers.get("cache-control") != "no-store"
                or absent_status != 404):
            raise ValueError("packaged default health surface rejected")
        index_status, index_bytes, _ = _ready(web_url + "/index.html", web)
        if index_status != 200 or hashlib.sha256(index_bytes).digest() != hashlib.sha256(index_file.read_bytes()).digest():
            raise ValueError("packaged frontend index differs over loopback")
        for path in assets:
            status, served, _ = _fetch(web_url + path)
            source = (frontend / path.removeprefix("/")).read_bytes()
            if status != 200 or hashlib.sha256(served).digest() != hashlib.sha256(source).digest():
                raise ValueError("packaged frontend asset differs over loopback")
        return {"status": "SYNTHETIC_PACKAGED_PUBLIC_HTTP_FRONTEND_PASS", "release_eligible": False,
                "payload_file_count": count, "api_health_ready": 200, "api_health_live": 200,
                "default_project_route": 404, "frontend_asset_count": len(assets),
                "loopback_only": True, "production_api_started": False,
                "https_verified": False, "children_stopped": True}
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"isolated HTTP child did not stop: {child.pid}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(smoke(args.root, args.candidate), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
