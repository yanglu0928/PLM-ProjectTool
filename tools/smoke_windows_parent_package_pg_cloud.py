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

from stage_windows_parent_candidate_cloud import stage_candidate


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


def run_packaged_launcher(shell: str, script: Path, cwd: Path,
                          env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
            cwd=str(cwd), capture_output=True, text=True, errors="replace",
            timeout=30, env=env)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="replace")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="replace")
        raise ValueError(
            "packaged startup launcher timed out after 30 seconds; "
            f"stdout_bytes={len(stdout)}; stderr_bytes={len(stderr)}"
        ) from None


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


def probe_packaged_startup_guard(root: Path) -> dict:
    import shutil as shutil_module

    payload = root / "payload"
    script = payload / "start-trial.ps1"
    manifest_path = root / "manifest.json"
    checksums_path = root / "payload-sha256sums.txt"
    diagnostic_path = payload / "check-startup.ps1"
    if (not script.is_file() or script.is_symlink()
            or not manifest_path.is_file() or not checksums_path.is_file()
            or not diagnostic_path.is_file() or diagnostic_path.is_symlink()):
        raise ValueError("packaged startup guard or diagnostic input missing")
    shell = shutil.which("powershell")
    if not shell:
        raise ValueError("Windows PowerShell 5.1 unavailable on hosted Windows runner")
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)

    before_manifest = manifest_path.read_bytes()
    before_sums = checksums_path.read_bytes()
    before_diagnostic = sha_file(diagnostic_path)
    result = run_packaged_launcher(shell, script, root, env)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError("packaged startup launcher did not forward a JSON preflight report") from None
    expected_codes = {
        "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
        "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
        "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
        "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
        "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
        "NON_RELEASE_CANDIDATE",
    }
    if (result.returncode != 1
            or result.stderr.strip() !=
            "Packaged production startup blocked; see BLOCKED diagnostics above."
            or report.get("status") != "BLOCKED"
            or report.get("release_eligible") is not False
            or report.get("legal_clearance") is not False
            or set(report.get("blocker_codes", [])) != expected_codes
            or len(report.get("messages", [])) != len(expected_codes)
            or "PLM_" in result.stdout or "sensitive-path-marker" in result.stdout):
        raise ValueError("packaged startup launcher report or fixed refusal differs")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", free_loopback_port()))

    matrix_root = root / "startup-launcher-matrix"
    matrix_root.mkdir()
    try:
        for name in ("missing-diagnostic", "corrupt-manifest"):
            case_root = matrix_root / name
            case_payload = case_root / "payload"
            case_payload.mkdir(parents=True)
            shutil_module.copyfile(script, case_payload / "start-trial.ps1")
            shutil_module.copyfile(checksums_path, case_root / "payload-sha256sums.txt")
            shutil_module.copyfile(diagnostic_path, case_payload / "check-startup.ps1")
            (case_root / "manifest.json").write_bytes(before_manifest)
            if name == "missing-diagnostic":
                (case_payload / "check-startup.ps1").unlink()
            else:
                (case_root / "manifest.json").write_text("{", encoding="ascii")
            attempt = run_packaged_launcher(
                shell, case_payload / "start-trial.ps1", case_root, env)
            if (attempt.returncode != 1 or attempt.stdout.strip()
                    or attempt.stderr.strip() !=
                    "Packaged production startup blocked; trust prerequisites are not ready."):
                raise ValueError("startup launcher diagnostic fallback differs: " + name)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", free_loopback_port()))
        if (manifest_path.read_bytes() != before_manifest
                or checksums_path.read_bytes() != before_sums
                or sha_file(diagnostic_path) != before_diagnostic):
            raise ValueError("startup launcher changed parent candidate inputs")
        return {"status": "STARTUP_LAUNCHER_DIAGNOSTIC_PASS_LIMITED",
                "blocker_codes": len(expected_codes), "fallback_cases": 2,
                "listener_started": False, "source_manifest_unchanged": True}
    finally:
        if matrix_root.parent != root or matrix_root.is_symlink():
            raise RuntimeError("refusing to clean startup launcher matrix outside smoke root")
        shutil.rmtree(matrix_root)


def probe_packaged_startup_guard_tamper_matrix(root: Path) -> dict:
    import copy

    source_manifest_path = root / "manifest.json"
    source_bytes = source_manifest_path.read_bytes()
    source = json.loads(source_bytes.decode("utf-8-sig"))
    script_source = root / "payload" / "start-trial.ps1"
    if not script_source.is_file() or script_source.is_symlink():
        raise ValueError("packaged startup guard missing for tamper matrix")

    ready = copy.deepcopy(source)
    ready["release_eligible"] = True
    ready["legal_clearance"] = True
    ready["startup_preflight"].update({
        "formal_startup_ready": True,
        "packaged_product_public_key_resource_present": True,
        "formal_license_trust_verified": True,
        "database_credential_reference_verified": True,
        "service_identity_acl_verified": True,
        "tls_certificate_configured": True,
        "tls_private_key_configured": True,
        "blocker_codes": [],
    })
    wrong_target = copy.deepcopy(ready)
    wrong_target["startup_preflight"]["database_credential_target_reference"] = "../outside"
    string_booleans = copy.deepcopy(ready)
    for key in (
        "formal_startup_ready", "packaged_product_public_key_resource_present",
        "formal_license_trust_verified", "database_credential_reference_verified",
        "service_identity_acl_verified", "tls_certificate_configured",
        "tls_private_key_configured",
    ):
        string_booleans["startup_preflight"][key] = "true"
    blocker_as_string = copy.deepcopy(ready)
    blocker_as_string["startup_preflight"]["blocker_codes"] = "[]"
    missing_blockers = copy.deepcopy(ready)
    del missing_blockers["startup_preflight"]["blocker_codes"]
    invalid_startup = copy.deepcopy(ready)
    invalid_startup["startup_preflight"] = "ready"
    cases = {
        "all-ready-tamper": json.dumps(ready),
        "wrong-credential-target": json.dumps(wrong_target),
        "string-booleans": json.dumps(string_booleans),
        "blocker-codes-string": json.dumps(blocker_as_string),
        "missing-blocker-codes": json.dumps(missing_blockers),
        "startup-object-string": json.dumps(invalid_startup),
        "malformed-json": "{",
    }

    shell = shutil.which("pwsh")
    if not shell:
        raise ValueError("PowerShell 7 unavailable on hosted Windows runner")
    matrix_root = root / "startup-manifest-tamper-matrix"
    matrix_root.mkdir()
    try:
        for name, manifest_text in cases.items():
            case_root = matrix_root / name
            payload = case_root / "payload"
            payload.mkdir(parents=True)
            shutil.copyfile(script_source, payload / "start-trial.ps1")
            (case_root / "manifest.json").write_text(manifest_text, encoding="utf-8")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            result = subprocess.run(
                [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                 str(payload / "start-trial.ps1")],
                cwd=str(payload), capture_output=True, text=True, errors="replace",
                timeout=20, env={key: value for key, value in os.environ.items()
                                 if not key.upper().startswith("PLM_")})
            if (result.returncode != 1 or result.stdout.strip()
                    or result.stderr.strip() !=
                    "Packaged production startup blocked; trust prerequisites are not ready."):
                raise ValueError("tampered startup manifest was not fixed-fail-closed: " + name)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        if source_manifest_path.read_bytes() != source_bytes:
            raise ValueError("tamper matrix changed source candidate manifest")
        return {"status": "STARTUP_MANIFEST_TAMPER_FAIL_CLOSED_PASS",
                "cases": len(cases), "stdout_empty": True, "listener_started": False}
    finally:
        if matrix_root.parent != root or matrix_root.is_symlink():
            raise RuntimeError("refusing to clean startup tamper workspace outside smoke root")
        shutil.rmtree(matrix_root)


def probe_packaged_startup_diagnostic(root: Path) -> dict:
    import copy

    source_manifest_path = root / "manifest.json"
    source_bytes = source_manifest_path.read_bytes()
    source = json.loads(source_bytes.decode("utf-8-sig"))
    source_script = root / "payload" / "check-startup.ps1"
    if not source_script.is_file() or source_script.is_symlink():
        raise ValueError("packaged read-only startup diagnostic missing")
    shell = shutil.which("powershell")
    if not shell:
        raise ValueError("Windows PowerShell unavailable on hosted Windows runner")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        actual_port = probe.getsockname()[1]
    actual_result = subprocess.run(
        [shell, "-NoProfile", "-File", r".\payload\check-startup.ps1"],
        cwd=str(root), capture_output=True, text=True, errors="replace",
        timeout=20, env={key: value for key, value in os.environ.items()
                         if not key.upper().startswith("PLM_")})
    if actual_result.returncode != 2 or actual_result.stderr.strip():
        raise ValueError(
            "documented package-root diagnostic command contract mismatch: "
            f"exit={actual_result.returncode}; stdout_bytes="
            f"{len(actual_result.stdout.encode('utf-8'))}; "
            f"stderr_empty={not bool(actual_result.stderr.strip())}"
        )
    try:
        actual_report = json.loads(actual_result.stdout)
    except json.JSONDecodeError:
        raise ValueError(
            "documented package-root diagnostic output is not JSON: "
            f"exit={actual_result.returncode}; stdout_bytes="
            f"{len(actual_result.stdout.encode('utf-8'))}"
        ) from None
    if (actual_report.get("status") != "BLOCKED"
            or actual_report.get("release_eligible") is not False
            or actual_report.get("legal_clearance") is not False
            or actual_report.get("blocker_codes") != source["startup_preflight"]["blocker_codes"]
            and set(actual_report.get("blocker_codes", [])) !=
            set(source["startup_preflight"]["blocker_codes"]) | {"NON_RELEASE_CANDIDATE"}):
        raise ValueError("documented package-root diagnostic report differs from source manifest")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", actual_port))

    ready = copy.deepcopy(source)
    ready["release_eligible"] = True
    ready["legal_clearance"] = True
    ready["startup_preflight"].update({
        "formal_startup_ready": True,
        "packaged_product_public_key_resource_present": True,
        "formal_license_trust_verified": True,
        "database_credential_reference_verified": True,
        "service_identity_acl_verified": True,
        "tls_certificate_configured": True,
        "tls_private_key_configured": True,
        "blocker_codes": [],
    })
    extra_field = copy.deepcopy(source)
    extra_field["startup_preflight"]["unexpected"] = "sensitive-path-marker"
    wrong_type = copy.deepcopy(source)
    wrong_type["startup_preflight"]["tls_certificate_configured"] = "false"
    cases = {
        "ready-candidate": json.dumps(ready),
        "extra-field": json.dumps(extra_field),
        "wrong-type": json.dumps(wrong_type),
        "malformed-json": "{",
    }
    matrix_root = root / "startup-diagnostic-matrix"
    matrix_root.mkdir()
    try:
        if actual_result.returncode != 2 or actual_result.stderr.strip():
            try:
                diagnostic_stdout = json.loads(actual_result.stdout)
                stdout_shape = "json:" + str(diagnostic_stdout.get("status", "no-status"))
            except (json.JSONDecodeError, AttributeError):
                stdout_shape = "non-json"
            stderr_shape = ("empty" if not actual_result.stderr.strip()
                            else "fixed-rejection" if actual_result.stderr.strip() ==
                            "Startup preflight diagnostic rejected; manifest invalid."
                            else "unexpected-nonempty")
            raise ValueError(
                "actual startup diagnostic contract mismatch: "
                f"exit={actual_result.returncode}; stdout_bytes={len(actual_result.stdout.encode('utf-8'))}; "
                f"stdout_shape={stdout_shape}; stderr_shape={stderr_shape}"
            )
        try:
            report = json.loads(actual_result.stdout)
        except json.JSONDecodeError:
            raise ValueError(
                "actual startup diagnostic output is not JSON: "
                f"exit={actual_result.returncode}; stdout_bytes={len(actual_result.stdout.encode('utf-8'))}"
            ) from None
        expected_codes = {
            "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
            "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
            "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
            "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
            "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
            "NON_RELEASE_CANDIDATE",
        }
        if (report.get("status") != "BLOCKED" or report.get("release_eligible") is not False
                or report.get("legal_clearance") is not False
                or set(report.get("blocker_codes", [])) != expected_codes
                or len(report.get("messages", [])) != len(expected_codes)
                or any("sensitive-path-marker" in x or "PLM-" in x for x in actual_result.stdout)):
            raise ValueError("startup diagnostic report is incomplete or exposes forbidden details")

        for name, manifest_text in cases.items():
            case_root = matrix_root / name
            payload = case_root / "payload"
            payload.mkdir(parents=True)
            shutil.copyfile(source_script, payload / "check-startup.ps1")
            (case_root / "manifest.json").write_text(manifest_text, encoding="utf-8")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            result = subprocess.run(
                [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-File",
                 str(payload / "check-startup.ps1")],
                cwd=str(payload), capture_output=True, text=True, errors="replace",
                timeout=20, env={key: value for key, value in os.environ.items()
                                 if not key.upper().startswith("PLM_")})
            if result.returncode != 2 or result.stdout.strip():
                raise ValueError("invalid diagnostic input did not fail without output: " + name)
            if result.stderr.strip() != "Startup preflight diagnostic rejected; manifest invalid.":
                raise ValueError("invalid diagnostic input response was not fixed: " + name)
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        if source_manifest_path.read_bytes() != source_bytes:
            raise ValueError("startup diagnostic changed source candidate manifest")
        return {"status": "STARTUP_PREFLIGHT_DIAGNOSTIC_FAIL_CLOSED_PASS",
                "blocked": True, "tamper_cases": len(cases),
                "stdout_redacted": True, "listener_started": False}
    finally:
        if matrix_root.parent != root or matrix_root.is_symlink():
            raise RuntimeError("refusing to clean startup diagnostic workspace outside smoke root")
        shutil.rmtree(matrix_root)


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

    staging_target = runner_temp / ("plm-parent-stage-" + str(parent.get("workflow_run")))
    existing_target = runner_temp / ("plm-parent-stage-existing-" + str(parent.get("workflow_run")))
    outside_target = runner_temp.parent / ("plm-parent-stage-outside-" + str(parent.get("workflow_run")))
    try:
        stage_candidate(args.archive, args.verification_summary, outside_target)
    except ValueError:
        if outside_target.exists():
            raise ValueError("out-of-root staging rejection created a path")
    else:
        raise ValueError("out-of-root staging target unexpectedly accepted")
    existing_target.mkdir()
    sentinel = existing_target / "preserve.txt"
    sentinel.write_text("preserve", encoding="ascii")
    try:
        stage_candidate(args.archive, args.verification_summary, existing_target)
    except ValueError:
        if not sentinel.is_file() or sentinel.read_text(encoding="ascii") != "preserve":
            raise ValueError("existing staging target was changed")
    else:
        raise ValueError("existing staging target unexpectedly accepted")
    if existing_target.parent != runner_temp or existing_target.drive.casefold() == "c:":
        raise ValueError("refusing to clean staging test outside runner temp")
    shutil.rmtree(existing_target)

    staging_result = stage_candidate(args.archive, args.verification_summary, staging_target)
    if (staging_result.get("status") != "HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED"
            or staging_result.get("payload_file_count") != parent.get("payload_file_count")
            or staging_result.get("installation_performed") is not False
            or not (staging_target / "payload" / "runtime" / "python.exe").is_file()):
        raise ValueError("candidate staging receipt or extracted runtime mismatch")
    if staging_target.parent != runner_temp or staging_target.drive.casefold() == "c:":
        raise ValueError("refusing to clean staged candidate outside runner temp")
    shutil.rmtree(staging_target)

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
            "formal_license_trust_verified": False,
            "database_credential_target_reference": "PLMProjectTool/Database",
            "database_credential_reference_verified": False,
            "service_identity_acl_verified": False,
            "tls_certificate_configured": False,
            "tls_private_key_configured": False,
            "blocker_codes": [
                "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
                "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
                "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
                "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
                "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
            ],
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
        startup_manifest_tamper_matrix = probe_packaged_startup_guard_tamper_matrix(root)
        startup_preflight_diagnostic = probe_packaged_startup_diagnostic(root)
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
            "candidate_staging": staging_result,
            "startup_entrypoint_probe": startup_entrypoint_probe,
            "startup_guard_probe": startup_guard_probe,
            "startup_manifest_tamper_matrix": startup_manifest_tamper_matrix,
            "startup_preflight_diagnostic": startup_preflight_diagnostic,
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
