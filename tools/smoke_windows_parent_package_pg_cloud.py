"""Run a bounded PostgreSQL component lifecycle smoke from a parent candidate on hosted Windows."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import socket
import sys
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name
            or any(part in ("", ".", "..") for part in parts)):
        raise ValueError("unsafe parent package path")
    return name


DATABASE_CREDENTIAL_TARGET = "PLMProjectTool/Database"


def database_credential_present() -> bool:
    if sys.platform != "win32":
        raise ValueError("Windows credential preflight required")
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                 ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = ctypes.c_int
    library.CredFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    found = library.CredReadW(DATABASE_CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer))
    if found:
        library.CredFree(pointer)
        return True
    if ctypes.get_last_error() != 1168:
        raise ValueError("database credential existence check unavailable")
    return False


def free_loopback_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def probe_packaged_production_entrypoint(root: Path) -> str:
    if database_credential_present():
        return "SKIPPED_EXISTING_CREDENTIAL_UNSCOPED"
    runtime = root / "payload" / "runtime"
    python = runtime / "python.exe"
    if not python.is_file() or python.is_symlink():
        raise ValueError("packaged Python runtime missing for startup probe")
    probe = root / "startup-preflight"
    probe.mkdir()
    data = probe / "data"
    data.mkdir()
    if not str(probe).isascii():
        raise ValueError("startup probe root must be ASCII")
    port = free_loopback_port()
    config = probe / "bootstrap.yaml"
    config.write_text(
        f'bind_host: "127.0.0.1"\nbind_port: {port}\n'
        f'data_root: "{data.as_posix()}"\nlog_level: "ERROR"\n'
        'trusted_origins: ["https://localhost"]\n', encoding="ascii")
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    windir = os.environ.get("WINDIR")
    if not windir:
        raise ValueError("Windows system directory unavailable")
    env["PATH"] = os.pathsep.join(
        (str(runtime), str(Path(windir) / "System32"), windir))
    launch = subprocess.run(
        [str(python), "-I", "-B", "-m",
         "plm_assistant.entrypoints.serve_windows", str(config), "--platform-write"],
        capture_output=True, text=True, errors="replace", timeout=30, env=env)
    if (launch.returncode != 1 or launch.stdout.strip()
            or launch.stderr.strip() !=
            "Production server unavailable; configuration or credential rejected."):
        raise ValueError("packaged production entrypoint did not fail closed")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
    return "FAIL_CLOSED_MISSING_ACCOUNT_DATABASE_CREDENTIAL"


def probe_packaged_startup_guard(root: Path) -> str:
    script = root / "payload" / "start-trial.ps1"
    if not script.is_file() or script.is_symlink():
        raise ValueError("packaged startup guard missing")
    shell = shutil.which("pwsh")
    if not shell:
        raise ValueError("PowerShell 7 unavailable on hosted Windows runner")
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    result = subprocess.run([shell, "-NoLogo", "-NoProfile", "-NonInteractive",
                             "-File", str(script)], cwd=str(script.parent),
                            capture_output=True, text=True, errors="replace",
                            timeout=20, env=env)
    if (result.returncode != 1 or result.stdout.strip()
            or result.stderr.strip() !=
            "Packaged production startup blocked; trust prerequisites are not ready."):
        diagnostic = (f"exit={result.returncode}; stdout={result.stdout[-500:]!r}; "
                      f"stderr={result.stderr[-1200:]!r}")
        raise ValueError("startup guard did not preserve fixed fail-closed response: " + diagnostic)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", free_loopback_port()))
    return "FAIL_CLOSED_MISSING_FORMAL_PRODUCT_TRUST"


def smoke_packaged_web(root: Path) -> dict:
    caddy = root / "payload" / "runtime" / "caddy" / "caddy.exe"
    frontend = root / "payload" / "frontend" / "dist"
    if not caddy.is_file() or caddy.is_symlink() or not (frontend / "index.html").is_file():
        raise ValueError("packaged Caddy or frontend index missing")
    api_port, web_port = free_loopback_port(), free_loopback_port()
    while api_port == web_port:
        web_port = free_loopback_port()
    data = root / "web-smoke"
    data.mkdir()
    handler = ("from http.server import BaseHTTPRequestHandler, HTTPServer\n"
               "class H(BaseHTTPRequestHandler):\n"
               " def do_GET(self):\n"
               "  self.send_response(200); self.end_headers(); self.wfile.write(b'api-probe-ok')\n"
               "HTTPServer(('127.0.0.1'," + str(api_port) + "),H).serve_forever()\n")
    api = subprocess.Popen([sys.executable, "-I", "-c", handler], cwd=str(data),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    caddyfile = data / "Caddyfile"
    caddyfile.write_text(
        "{\n  admin off\n  auto_https off\n}\n"
        "http://127.0.0.1:%d {\n"
        "  @api path /api/v1/*\n"
        "  handle @api {\n    reverse_proxy 127.0.0.1:%d\n  }\n"
        "  handle {\n    root * \"%s\"\n    try_files {path} /index.html\n    file_server\n  }\n}\n"
        % (web_port, api_port, frontend.as_posix()), encoding="utf-8")
    edge = subprocess.Popen([str(caddy), "run", "--config", str(caddyfile), "--adapter", "caddyfile"],
                            cwd=str(data), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % web_port
    try:
        deadline = time.monotonic() + 30
        last_error = None
        while time.monotonic() < deadline:
            if edge.poll() is not None or api.poll() is not None:
                raise RuntimeError("Caddy/API loopback smoke process exited")
            try:
                with urllib.request.urlopen(base + "/__spa_fallback_probe__", timeout=2) as response:
                    page = response.read()
                    if response.status != 200 or not page:
                        raise ValueError("SPA fallback did not serve the frontend")
                with urllib.request.urlopen(base + "/api/v1/probe", timeout=2) as response:
                    if response.status != 200 or response.read() != b"api-probe-ok":
                        raise ValueError("API reverse proxy did not return the loopback probe")
                return {"status": "LOOPBACK_WEB_STATIC_AND_API_PROXY_PASS_LIMITED",
                        "caddy_version": "2.11.4", "listener": "127.0.0.1",
                        "production_api_started": False, "https_tested": False}
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_error = exc
                time.sleep(.25)
        raise RuntimeError("loopback web smoke timed out: %s" % last_error)
    finally:
        for process in (edge, api):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def run_checked(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"cloud smoke command failed ({Path(args[0]).name}): {result.stderr[-2000:]}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--verification-summary", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args()

    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    root = args.work_root.resolve()
    if (root.parent != runner_temp or root.drive.casefold() == "c:"
            or root.exists() or args.archive.is_symlink()
            or not args.archive.is_file()):
        raise ValueError("smoke root must be a new runner-temp directory on a non-C drive")
    parent = json.loads(args.verification_summary.read_text(encoding="utf-8-sig"))
    if (parent.get("status") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS"
            or parent.get("release_eligible") is not False
            or parent.get("legal_clearance") is not False
            or parent.get("archive_sha256") != sha_file(args.archive)):
        raise ValueError("parent artifact summary or archive identity rejected")

    with zipfile.ZipFile(args.archive) as z:
        infos = z.infolist()
        names = [safe_name(i.filename) for i in infos]
        if len(names) != len(set(n.casefold() for n in names)):
            raise ValueError("parent archive has duplicate/case-conflicting paths")
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos):
            raise ValueError("parent archive symlink rejected")
        manifest = json.loads(z.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
                or manifest.get("release_eligible") is not False
                or manifest.get("legal_clearance") is not False
                or manifest.get("workflow_run") != parent.get("workflow_run")
                or manifest.get("source_commit") != parent.get("source_commit")):
            raise ValueError("parent manifest identity mismatch")
        startup = manifest.get("startup_preflight")
        expected_startup = {
            "formal_startup_ready": False,
            "packaged_product_public_key_resource_present": False,
            "blocker_codes": ["FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED"],
        }
        if startup != expected_startup or parent.get("startup_preflight") != startup:
            raise ValueError("parent package startup preflight is missing, mismatched or unexpectedly ready")
        sums = z.read("payload-sha256sums.txt")
        if sha(sums) != manifest.get("payload_sha256sums_sha256"):
            raise ValueError("parent payload checksum list identity mismatch")
        expected = {}
        for line in sums.decode("ascii").splitlines():
            digest, name = line.split("  ", 1)
            safe_name(name)
            if name in expected or len(digest) != 64:
                raise ValueError("invalid parent payload checksum list")
            expected[name] = digest
        if len(expected) != manifest.get("payload_file_count"):
            raise ValueError("parent payload count mismatch")
        if set(names) != set(expected) | {"manifest.json", "payload-sha256sums.txt"}:
            raise ValueError("parent archive inventory differs from checksum list")
        root.mkdir()
        # Mirror a real package extraction: the launcher consumes the archive-level manifest.
        (root / "manifest.json").write_bytes(z.read("manifest.json"))
        (root / "payload-sha256sums.txt").write_bytes(sums)
        for name, digest in expected.items():
            info = z.getinfo(name)
            target = root.joinpath(*PurePosixPath(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with z.open(info) as src, target.open("xb") as dst:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    dst.write(block)
                    h.update(block)
            if h.hexdigest() != digest:
                raise ValueError("parent extraction hash mismatch: " + name)

    pg = root / "payload" / "pgsql"
    initdb, pg_ctl, psql = (pg / "bin" / name for name in
                            ("initdb.exe", "pg_ctl.exe", "psql.exe"))
    if not all(p.is_file() and not p.is_symlink() for p in (initdb, pg_ctl, psql)):
        raise ValueError("PostgreSQL executables missing from parent package")
    if not (pg / "lib" / "vector.dll").is_file():
        raise ValueError("pgvector extension binary missing")

    try:
        startup_entrypoint_probe = probe_packaged_production_entrypoint(root)
        startup_guard_probe = probe_packaged_startup_guard(root)
        web_service_smoke = smoke_packaged_web(root)
    except Exception:
        if root.exists():
            if root.parent != runner_temp or root.drive.casefold() == "c:":
                raise RuntimeError("refusing to clean smoke root outside runner D-drive temp")
            shutil.rmtree(root)
        raise

    data_dir = root / "pgdata"
    log_path = root / "postgres.log"
    started = False
    start_attempted = False
    port_sock = socket.socket()
    port_sock.bind(("127.0.0.1", 0))
    port = port_sock.getsockname()[1]
    port_sock.close()
    result = {}
    try:
        init = run_checked([str(initdb), "-D", str(data_dir), "-U", "postgres",
                            "--auth-local=trust", "--auth-host=trust", "--no-locale", "-E", "UTF8"], 180)
        start_attempted = True
        start_output = root / "pgctl-start.txt"
        with start_output.open("w", encoding="utf-8") as output:
            try:
                start = subprocess.run(
                    [str(pg_ctl), "-D", str(data_dir), "-l", str(log_path),
                     "-o", f"-h 127.0.0.1 -p {port} -c listen_addresses=127.0.0.1",
                     "-w", "start"],
                    stdout=output, stderr=subprocess.STDOUT, text=True,
                    timeout=180, check=False,
                )
            except subprocess.TimeoutExpired:
                output.flush()
                tail = start_output.read_text(encoding="utf-8", errors="replace")[-2000:]
                raise RuntimeError("temporary pg_ctl start timed out: " + tail) from None
        if start.returncode:
            tail = start_output.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError("temporary pg_ctl start failed: " + tail)
        started = True
        psql_args = [str(psql), "-h", "127.0.0.1", "-p", str(port),
                     "-U", "postgres", "-d", "postgres", "-X", "-A", "-t",
                     "-q", "-v", "ON_ERROR_STOP=1", "-c"]
        version = run_checked(psql_args + ["SELECT current_setting('server_version');"],
                              60).stdout.strip()
        run_checked(psql_args + ["CREATE EXTENSION vector;"], 60)
        vector_version = run_checked(
            psql_args + ["SELECT extversion FROM pg_extension WHERE extname='vector';"],
            60).stdout.strip()
        if version != "18.6" or vector_version != "0.8.6":
            raise ValueError("PostgreSQL/pgvector runtime identity mismatch: "
                             + version + "/" + vector_version)
        result = {
            "status": "PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED",
            "source_commit": parent["source_commit"], "workflow_run": parent["workflow_run"],
            "parent_archive_sha256": parent["archive_sha256"],
            "postgresql_version": version, "pgvector_version": vector_version,
            "listen_host": "127.0.0.1", "temporary_database_only": True,
            "production_installation": False, "product_api_started": False,
            "license_trust_used": False, "runner_drive": root.drive,
            "parent_payload_file_count": len(expected),
            "startup_preflight": startup,
            "startup_entrypoint_probe": startup_entrypoint_probe,
            "startup_guard_probe": startup_guard_probe,
            "web_service_smoke": web_service_smoke,
        }
    finally:
        if start_attempted and data_dir.is_dir():
            status = None
            for _ in range(20):
                status = subprocess.run([str(pg_ctl), "-D", str(data_dir), "status"],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, timeout=30, check=False)
                if status.returncode == 0:
                    break
                time.sleep(.5)
            if status is not None and status.returncode == 0:
                stop = subprocess.run(
                    [str(pg_ctl), "-D", str(data_dir), "-m", "fast", "-w", "stop"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, timeout=90, check=False,
                )
                if stop.returncode:
                    raise RuntimeError("temporary PostgreSQL did not stop cleanly: "
                                       + stop.stdout[-1000:])
            elif started:
                raise RuntimeError("temporary PostgreSQL state became uncertain")
        if root.exists():
            if root.parent != runner_temp or root.drive.casefold() == "c:":
                raise RuntimeError("refusing to clean outside runner temp/non-C drive")
            shutil.rmtree(root)

    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
