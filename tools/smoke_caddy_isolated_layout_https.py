"""Full-hash-check the P25 isolated layout, then test real loopback HTTPS through it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_caddy_windows_offline_input import EXE_SHA256, digest
from build_windows_unified_caddy_candidate import KIND, TEMPLATE_SHA256
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping, plan_install
from smoke_caddy_same_origin_https import fetch, free_port, host_status, synthetic_certificate, wait_ready
from smoke_packaged_http_frontend import _ready as api_ready, parse_assets
from smoke_staged_caddy_template import render
from verify_windows_unified_extract import verify as verify_stage


def verify_layout(candidate: Path, stage: Path, layout: Path) -> dict:
    # The root must be an existing direct ASCII Temp child, never the formal install root.
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    layout = layout.resolve(strict=True)
    stage = stage.resolve(strict=True)
    if (layout.parent != temp or stage.parent != temp or not str(layout).isascii()
            or not str(stage).isascii() or layout == stage
            or not layout.name.startswith("plm-install-rehearsal-")):
        raise ValueError("isolated layout/stage root rejected")
    plan = plan_install(candidate, "C:\\PLMTool")
    if plan["install_root_exists"]:
        raise ValueError("formal install root exists; isolated proof cannot stand in for upgrade")
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != 21110:
        raise ValueError("source stage count changed")
    hashes = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        value, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("source stage manifest rejected")
        hashes[name] = value
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("source stage metadata differs")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if len(hashes) != 21110 or mapping_sha256 != plan["mapping_sha256"]:
        raise ValueError("isolated mapping differs from candidate")
    landed = {str(path.relative_to(layout)).replace("\\", "/").casefold()
              for path in layout.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("isolated layout file set differs")
    for source, target in mapping.items():
        expected = hashes[source] if source in hashes else digest_path(stage / source)
        if digest_path(layout / target) != expected:
            raise ValueError("isolated layout file hash differs")
    return {"mapping_sha256": mapping_sha256, "file_count": len(mapping)}


def smoke(candidate: Path, stage: Path, layout: Path, *, layout_verifier=verify_layout) -> dict:
    verified = layout_verifier(candidate, stage, layout)
    layout = layout.resolve(strict=True)
    runtime = layout / "runtime/python"
    frontend = layout / "app/frontend/dist"
    caddy = layout / "runtime/caddy/caddy.exe"
    template = layout / "config/Caddyfile.template"
    if digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256:
        raise ValueError("layout Caddy/template identity changed")
    index = frontend / "index.html"
    assets = parse_assets(index.read_text(encoding="utf-8"))
    api_port, https_port = free_port(), free_port()
    while api_port == https_port:
        https_port = free_port()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    children: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryDirectory(prefix="plm-caddy-layout-https-") as directory:
        root = Path(directory)
        cert, key, config = root / "synthetic-cert.pem", root / "synthetic-key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(render(template.read_text(encoding="ascii"), cert=cert, key=key,
                                 frontend=frontend, api_port=api_port, https_port=https_port), encoding="ascii")
        validated = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                   capture_output=True, text=True, errors="replace", timeout=15, env=env)
        if validated.returncode:
            raise ValueError("rendered layout Caddyfile invalid")
        context = ssl.create_default_context(cafile=str(cert))
        try:
            api = subprocess.Popen([str(runtime / "python.exe"), "-I", "-B", "-m", "uvicorn",
                                    "plm_assistant.entrypoints.api:create_app", "--factory",
                                    "--host", "127.0.0.1", "--port", str(api_port), "--no-access-log"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=env)
            children.append(api)
            status, body, _ = api_ready(f"http://127.0.0.1:{api_port}/health/ready", api)
            if status != 200 or body != b'{"status":"UP"}':
                raise ValueError("layout API not ready")
            proxy = subprocess.Popen([str(caddy), "run", "--config", str(config)],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, env=env)
            children.append(proxy)
            base = f"https://localhost:{https_port}"
            wait_ready(base + "/", context, proxy)
            index_status, page, _ = fetch(base + "/", context)
            if index_status != 200 or page != index.read_bytes():
                raise ValueError("layout HTTPS index differs")
            for asset in assets:
                status, body, _ = fetch(base + asset, context)
                if status != 200 or hashlib.sha256(body).digest() != hashlib.sha256(
                        (frontend / asset.removeprefix("/")).read_bytes()).digest():
                    raise ValueError("layout HTTPS asset differs")
            health, health_body, _ = fetch(base + "/health/ready", context)
            absent, absent_body, _ = fetch(base + "/api/v1/projects", context)
            deep, deep_body, _ = fetch(base + "/projects/synthetic-deep-link", context)
            wrong_host, _ = host_status(https_port, context, ["untrusted.example.test"])
            if (health != 200 or health_body != b'{"status":"UP"}' or absent != 404
                    or b"<html" in absent_body.lower() or deep != 200 or deep_body != page
                    or wrong_host != 421):
                raise ValueError("layout HTTPS route rejected")
            return {"status": "NON_RELEASE_CADDY_LAYOUT_HTTPS_PASS", "release_eligible": False,
                    "mapping_sha256": verified["mapping_sha256"], "verified_file_count": verified["file_count"],
                    "frontend_asset_count": len(assets), "health_ready": health,
                    "default_api_route": absent, "spa_deep_link": deep, "wrong_host_status": wrong_host,
                    "synthetic_tls_only": True, "formal_install_performed": False,
                    "services_changed": False, "children_stopped": True}
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.stage, args.layout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
