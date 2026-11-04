"""Hosted P25 real HTTP + Edge fail-closed integration; all owned data stays in RUNNER_TEMP."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

import psycopg
import uvicorn
from sqlalchemy import URL
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_output_create import create_windows_output_request_create_router
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.user_orm import UserRow
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import upgrade_database
from plm_assistant.modules.project.infrastructure.orm import DepartmentRow, ProjectMemberRow, ProjectRow

TOKEN = b"t" * 32
CSRF = b"c" * 32
PROJECT = uuid.UUID("01234567-89ab-4cde-8123-456789abcdef")
ACTOR = uuid.UUID("31234567-89ab-4cde-8123-456789abcdef")
DEPARTMENT = uuid.UUID("61234567-89ab-4cde-8123-456789abcdef")
ACTOR_BY_TOKEN: dict[bytes, uuid.UUID] = {}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or name.startswith("/")
            or any(part in ("", ".", "..") for part in path.parts)
            or not name.isascii()):
        raise ValueError("PG sidecar archive member rejected")
    return path


def verify_and_extract_sidecar(archive: Path, digest_file: Path, root: Path) -> Path:
    expected = json.loads(digest_file.read_text(encoding="utf-8-sig"))
    expected_sha = expected.get("Hash") or expected.get("hash")
    if type(expected_sha) is not str or sha256_file(archive) != expected_sha.lower():
        raise ValueError("same-run PostgreSQL sidecar archive digest mismatch")
    root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)) or len(names) > 10000:
            raise ValueError("PG sidecar archive has duplicate or excessive entries")
        if any(info.is_dir() for info in bundle.infolist()):
            raise ValueError("PG sidecar archive must contain only files")
        for name in names:
            safe_member(name)
        required_metadata = {"manifest.json", "payload-sha256sums.txt", "third-party-inventory.json"}
        if not required_metadata.issubset(names):
            raise ValueError("PG sidecar metadata missing")
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        if (manifest.get("kind") != "WINDOWS_PG18_PGVECTOR_RUNTIME_NON_RELEASE_REBUILT"
                or manifest.get("release_eligible") is not False
                or manifest.get("database_started") is not False):
            raise ValueError("PG sidecar manifest is not the expected non-release candidate")
        expected_files: dict[str, str] = {}
        for line in bundle.read("payload-sha256sums.txt").decode("ascii").splitlines():
            digest, sep, name = line.partition("  ")
            safe_member(name)
            if sep != "  " or len(digest) != 64 or name in expected_files:
                raise ValueError("PG sidecar hash inventory malformed")
            expected_files[name] = digest
        if manifest.get("payload_file_count") != sum(n.startswith("payload/") for n in expected_files):
            raise ValueError("PG sidecar payload count mismatch")
        if set(names) != set(expected_files) | required_metadata:
            raise ValueError("PG sidecar files differ from its inventory")
        for name, expected_hash in expected_files.items():
            h = hashlib.sha256()
            with bundle.open(name) as src:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    h.update(block)
            if h.hexdigest() != expected_hash:
                raise ValueError("PG sidecar payload digest mismatch")
            if name.startswith("payload/pgsql/"):
                target = root.joinpath(*safe_member(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(name) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
    binary = root / "payload" / "pgsql" / "bin"
    for executable in ("initdb.exe", "pg_ctl.exe", "postgres.exe"):
        if not (binary / executable).is_file():
            raise ValueError("verified PG sidecar is missing a required executable")
    return root / "payload" / "pgsql"


def run_checked(args: list[str], *, timeout: int = 180) -> str:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    if p.returncode:
        def safe_tail(value: str) -> str:
            runner_temp = os.environ.get("RUNNER_TEMP", "")
            if runner_temp:
                value = value.replace(runner_temp, "<runner-temp>")
            value = re.sub(r"[\x00-\x1f]+", " ", value)
            return value[-1200:]
        raise RuntimeError("hosted P25 command failed: " + Path(args[0]).name
                           + " exit_code=" + str(p.returncode)
                           + " stdout=" + safe_tail(p.stdout)
                           + " stderr=" + safe_tail(p.stderr))
    return p.stdout.strip()


def start_pg(binary: Path, data: Path, log: Path, port: int) -> None:
    for name in ("pg_config.exe", "postgres.exe", "initdb.exe"):
        run_checked([str(binary / name), "--version"], timeout=30)
    run_checked([str(binary / "initdb.exe"), "-D", str(data), "-U", "postgres",
                 "--auth-local=trust", "--auth-host=trust", "--no-locale",
                 "-E", "UTF8", "--debug", "--no-clean"], timeout=180)
    result = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(log),
                             "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=90, check=False)
    if result.returncode:
        raise RuntimeError("isolated PG18 failed to start; runner temp data retained for diagnosis")


def pg_sql(binary: Path, port: int, db: str, statement: str) -> str:
    return run_checked([str(binary / "psql.exe"), "-X", "-v", "ON_ERROR_STOP=1",
                        "-h", "127.0.0.1", "-p", str(port), "-U", "postgres",
                        "-d", db, "-Atc", statement], timeout=60)


def db_url(name: str, port: int) -> URL:
    return URL.create("postgresql+psycopg", username="postgres", host="127.0.0.1",
                      port=port, database=name)


def db_dsn(name: str, port: int) -> str:
    return f"postgresql://postgres@127.0.0.1:{port}/{name}"


def create_database(name: str, port: int) -> None:
    with psycopg.connect(db_dsn("postgres", port), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')


def drop_database(name: str, port: int) -> None:
    with psycopg.connect(db_dsn("postgres", port), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


def snapshot(name: str, port: int) -> dict[str, int]:
    with psycopg.connect(db_dsn(name, port)) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='plm' AND (table_name LIKE 'out%' OR table_name LIKE 'job%' "
            "OR table_name LIKE 'aud%' OR table_name LIKE 'plt_idempotency%') ORDER BY table_name"
        ).fetchall()
        return {table: conn.execute(f'SELECT count(*) FROM plm."{table}"').fetchone()[0]
                for (table,) in rows}


class SyntheticSessions:
    def validate(self, token: bytes, *, csrf_token=None, require_csrf=False):
        if token != TOKEN or csrf_token != CSRF or require_csrf is not True:
            raise RuntimeError("synthetic session rejected")
        return SimpleNamespace(user_id=ACTOR)


class SyntheticSessionAccess:
    def authenticated_user(self, transaction, *, session_token, csrf_token, now):
        if session_token == TOKEN and csrf_token == CSRF:
            return ACTOR_BY_TOKEN.get(session_token)
        return None


class SyntheticOrigins:
    def __init__(self, expected_origin: str) -> None:
        self.expected = expected_origin.encode("ascii")

    def require_trusted(self, headers):
        if not any(k.lower() == b"origin" and v == self.expected for k, v in headers):
            raise RuntimeError("synthetic same-origin check rejected")


class SyntheticLicense:
    def require_valid(self, **_):
        return True


def seed_synthetic_project(runtime) -> None:
    creator = uuid.UUID("71234567-89ab-4cde-8123-456789abcdef")
    implementer = uuid.UUID("81234567-89ab-4cde-8123-456789abcdef")
    customer_manager = uuid.UUID("91234567-89ab-4cde-8123-456789abcdef")
    with runtime.unit_of_work() as tx:
        tx.session.add_all([
            UserRow(user_id=user, username_display=name, username_normalized=name,
                    state="DISABLED", deployment_role="NONE")
            for user, name in ((creator, "p25-synthetic-creator"),
                               (ACTOR, "p25-synthetic-manager"),
                               (implementer, "p25-synthetic-implementer"),
                               (customer_manager, "p25-synthetic-customer-manager"))
        ])
        tx.session.flush()
        tx.session.add(ProjectRow(project_id=PROJECT, project_code="P25-A",
                                  project_code_normalized="P25-A",
                                  name="Synthetic P25 output project", created_by=creator))
        tx.session.flush()
        tx.session.add(DepartmentRow(department_id=DEPARTMENT, project_id=PROJECT,
                                     department_code="P25", department_code_normalized="P25",
                                     name="Synthetic P25 Department", state="ACTIVE"))
        tx.session.add_all([
            ProjectMemberRow(project_member_id=uuid.uuid4(), project_id=PROJECT,
                             user_id=user, department_id=DEPARTMENT,
                             project_role=role, state="ACTIVE")
            for user, role in ((ACTOR, "PROJECT_MANAGER"),
                               (implementer, "IMPLEMENTATION_MEMBER"),
                               (customer_manager, "CUSTOMER_MANAGER"))
        ])
        tx.commit()



def windows_loader_diagnostics(pg_root: Path) -> dict[str, object]:
    result: dict[str, object] = {"platform": sys.platform, "pe_tool_available": False}
    if os.name != "nt":
        result["status"] = "NOT_WINDOWS"
        return result

    def category(name: str) -> str:
        binary = pg_root / "bin" / name
        library = pg_root / "lib" / name
        if binary.is_file():
            return "sidecar_bin"
        if library.is_file():
            return "sidecar_lib"
        system_root = Path(os.environ.get("SystemRoot", ""))
        if system_root and (system_root / "System32" / name).is_file():
            return "system32"
        if system_root and (system_root / name).is_file():
            return "windows_root"
        for raw in os.environ.get("PATH", "").split(os.pathsep):
            entry = raw.strip().strip('"')
            if entry and (Path(entry) / name).is_file():
                return "path"
        if name.lower().startswith(("api-ms-win-", "ext-ms-win-")):
            return "api_set"
        return "missing"

    result["runtime_presence"] = {
        name: category(name) for name in (
            "VCRUNTIME140.dll", "VCRUNTIME140_1.dll", "MSVCP140.dll",
            "MSVCP140_1.dll", "ucrtbase.dll", "libwinpthread-1.dll",
            "libintl-9.dll", "icuuc77.dll", "icudt77.dll")
    }
    try:
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        vswhere = program_files_x86 / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        dumpbin = None
        if vswhere.is_file():
            located = subprocess.run(
                [str(vswhere), "-latest", "-products", "*", "-property", "installationPath"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", timeout=15, check=False)
            if located.returncode == 0 and located.stdout.strip():
                tool_root = Path(located.stdout.strip().splitlines()[0])
                tools_root = tool_root / "VC" / "Tools" / "MSVC"
                candidates = sorted(tools_root.glob("*/bin/Hostx64/x64/dumpbin.exe"))
                if candidates:
                    dumpbin = candidates[-1]
        result["pe_tool_available"] = dumpbin is not None
        dependency_rows: list[dict[str, str]] = []
        missing: set[str] = set()
        queue = [pg_root / "bin" / "initdb.exe"]
        visited: set[Path] = set()
        while dumpbin is not None and queue and len(visited) < 48:
            image = queue.pop(0)
            resolved_image = image.resolve()
            if resolved_image in visited:
                continue
            visited.add(resolved_image)
            probe = subprocess.run(
                [str(dumpbin), "/nologo", "/dependents", str(image)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", timeout=20, check=False)
            if probe.returncode != 0:
                dependency_rows.append({"image": image.name, "probe": "FAILED"})
                continue
            names = []
            for line in probe.stdout.splitlines():
                match = re.fullmatch(r"\s*([A-Za-z0-9_.+-]+\.dll)\s*", line, flags=re.IGNORECASE)
                if match:
                    names.append(match.group(1))
            for name in sorted(set(names), key=str.lower):
                where = category(name)
                dependency_rows.append({"image": image.name[:120], "name": name[:160], "resolved": where})
                if where == "missing":
                    missing.add(name.lower())
                elif where == "sidecar_bin":
                    queue.append(pg_root / "bin" / name)
                elif where == "sidecar_lib":
                    queue.append(pg_root / "lib" / name)
        result["dependency_probe_count"] = len(visited)
        result["dependencies"] = dependency_rows[:120]
        result["missing_dependencies"] = sorted(missing)[:80]
        result["dependency_probe_truncated"] = bool(queue) or len(dependency_rows) > 120
    except Exception as probe_failure:
        result["pe_probe_error_type"] = type(probe_failure).__name__[:120]

    try:
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
        if not powershell:
            result["application_error_events"] = {"status": "POWERSHELL_UNAVAILABLE"}
        else:
            command = (
                "$e=Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=(Get-Date).AddMinutes(-30)} "
                "-ErrorAction SilentlyContinue | Where-Object { "
                "$_.ProviderName -in @('Application Error','Windows Error Reporting') -and $_.Message -match '(?i)initdb\\.exe' } "
                "| Select-Object -First 3; if(-not $e){ '[]' } else { "
                "$e | ForEach-Object { [ordered]@{ id=$_.Id; provider=$_.ProviderName; "
                "message=$_.Message.Substring(0,[Math]::Min(1200,$_.Message.Length)) } } | ConvertTo-Json -Compress }"
            )
            events = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", timeout=25, check=False)
            raw = events.stdout.strip()
            if events.returncode == 0:
                raw = raw.replace(str(Path(os.environ.get("RUNNER_TEMP", "")).resolve()), "<runner-temp>")
                raw = re.sub(r'[A-Za-z]:[^ \r\n,;]+', '<absolute-path>', raw)
                raw = re.sub(r"[\x00-\x1f]+", " ", raw)
                result["application_error_events"] = {
                    "status": "CAPTURED", "data": raw[:3000] if raw else "[]"}
            else:
                result["application_error_events"] = {"status": "QUERY_FAILED"}
    except Exception as event_failure:
        result["application_error_events"] = {
            "status": "QUERY_FAILED", "error_type": type(event_failure).__name__[:120]}
    return result


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--sidecar-sha", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if runner_temp.drive.upper() != "D:" or not str(runner_temp).isascii():
        raise ValueError("P25 requires an ASCII D-drive GitHub runner temp")
    for path in (args.dist, args.sidecar, args.sidecar_sha):
        if not path.resolve(strict=True).is_relative_to(runner_temp):
            raise ValueError("P25 input escaped RUNNER_TEMP")
    if not (args.dist / "index.html").is_file():
        raise ValueError("same-run frontend production build missing")
    work = Path(tempfile.mkdtemp(prefix="plm-out-p25-", dir=runner_temp))
    if not work.resolve(strict=True).is_relative_to(runner_temp) or not str(work).isascii():
        raise ValueError("P25 work root is not an ASCII RUNNER_TEMP child")
    pg_data = None
    pg_run = None
    pg_log = None
    pg_root = None
    pg_started = False
    database = "plm_out25_" + args.run_id[-10:]
    runtime = None
    server = None
    server_task = None
    ACTOR_BY_TOKEN[TOKEN] = ACTOR
    try:
        pg_root = verify_and_extract_sidecar(args.sidecar, args.sidecar_sha, work / "pg-runtime")
        binary = pg_root / "bin"
        pg_port = free_port()
        pg_run = Path(tempfile.mkdtemp(prefix="plm-out-p25-pg-", dir=runner_temp))
        if not pg_run.resolve(strict=True).is_relative_to(runner_temp) or not str(pg_run).isascii():
            raise ValueError("P25 PostgreSQL data directory escaped the D-drive runner temp")
        pg_data = pg_run / "data"
        pg_log = pg_run / "postgresql.log"
        start_pg(binary, pg_data, pg_log, pg_port)
        pg_started = True
        create_database(database, pg_port)
        version = pg_sql(binary, pg_port, database, "SHOW server_version;")
        pg_sql(binary, pg_port, database, "CREATE EXTENSION vector;")
        vector = pg_sql(binary, pg_port, database,
                        "SELECT extversion FROM pg_extension WHERE extname='vector';")
        if version != "18.6" or vector != "0.8.6":
            raise ValueError("P25 isolated PostgreSQL runtime version mismatch")
        upgrade_database(db_url(database, pg_port), "head")
        runtime = create_database_runtime(db_url(database, pg_port))
        seed_synthetic_project(runtime)
        fixed_app = create_app()
        if "/api/v1/projects/{project_id}/output-requests" in fixed_app.openapi().get("paths", {}):
            raise AssertionError("default application mounted the Output Create route")
        ui_port = free_port()
        ui_origin = f"http://localhost:{ui_port}"
        router = create_windows_output_request_create_router(
            runtime=runtime, sessions=SyntheticSessions(), origins=SyntheticOrigins(ui_origin),
            license_guard=SyntheticLicense(), audit=AuditService(SqlAlchemyAuditRepository()),
            session_access=SyntheticSessionAccess())
        app = create_app(output_request_create_router=router)
        api_port = free_port()
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=api_port,
                                               log_level="error", access_log=False))
        server_task = asyncio.create_task(server.serve())
        for _ in range(300):
            if server.started:
                break
            if server_task.done():
                await server_task
                raise RuntimeError("P25 real Output HTTP server stopped during startup")
            await asyncio.sleep(0.1)
        if not server.started:
            raise TimeoutError("P25 real Output HTTP server did not start")
        before = snapshot(database, pg_port)
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        node_summary = work / "edge-summary.json"
        command = ["node", str(ROOT / "validation/out-01-a01-p25-real-http-edge/run.mjs"),
                   "--dist", str(args.dist), "--summary-out", str(node_summary),
                   "--backend-origin", f"http://127.0.0.1:{api_port}", "--port", str(ui_port)]
        node_env = os.environ.copy()
        node_env["TEMP"] = str(runner_temp)
        node_env["TMP"] = str(runner_temp)
        node = await asyncio.create_subprocess_exec(*command, cwd=str(ROOT),
                                                    env=node_env,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.STDOUT)
        output, _ = await asyncio.wait_for(node.communicate(), timeout=240)
        if node.returncode:
            raise RuntimeError("P25 Edge harness failed: " + output.decode("utf-8", "replace")[-6000:])
        edge_summary = json.loads(node_summary.read_text(encoding="utf-8"))
        after = snapshot(database, pg_port)
        if edge_summary.get("real_backend_posts") != 1 or edge_summary.get("real_backend_status") != 422:
            raise AssertionError("P25 real HTTP rejection contract did not pass")
        if before != after:
            raise AssertionError("P25 real HTTP rejection changed Output/Job/Audit/Idempotency rows")
        result = {
            "wbs": "OUT-01-A01-P25", "status": "PASS_SCOPE_LIMITED",
            "runner_os": "GitHub hosted Windows Server 2025", "runner_drive": "D:",
            "browser": "Microsoft Edge headless", "postgresql_version": version,
            "pgvector_version": vector, "real_http_status": 422,
            "real_http_posts": 1, "database_snapshot_unchanged": True,
            "default_create_route_absent": True, "empty_publisher_manifest": True,
            "customer_data": False, "external_api_calls": 0, "plugin_executed": False,
            "docx_generated": False, "release_eligible": False,
            "edge_checks": edge_summary.get("checks", []),
            "synthetic_post_count": edge_summary.get("request_posts"),
        }
        args.summary_out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                                    encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except Exception as failure:
        def safe_diagnostic_text(value: str, limit: int = 1600) -> str:
            value = value.replace(str(runner_temp), "<runner-temp>")
            value = re.sub(r"[\x00-\x1f]+", " ", value)
            value = re.sub(r"(?i)(password|token|secret|api[_-]?key)=([^\s&]+)", r"\1=<redacted>", value)
            return value[-limit:]

        diagnostic: dict[str, object] = {
            "wbs": "OUT-01-A01-P25",
            "status": "FAILED_DIAGNOSTIC",
            "failure_type": type(failure).__name__[:120],
            "failure": safe_diagnostic_text(str(failure)),
            "customer_data": False,
            "external_api_calls": 0,
            "plugin_executed": False,
            "database_files_included": False,
        }
        if pg_root is not None:
            try:
                diagnostic["windows_loader"] = windows_loader_diagnostics(pg_root)
            except Exception as loader_failure:
                diagnostic["windows_loader"] = {"status": "PROBE_FAILED",
                                                "error_type": type(loader_failure).__name__[:120]}
        if pg_root is not None and pg_data is not None:
            try:
                status_probe = subprocess.run(
                    [str(pg_root / "bin" / "pg_ctl.exe"), "-D", str(pg_data), "status"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace", timeout=20, check=False)
                diagnostic["pg_ctl_status"] = {
                    "exit_code": status_probe.returncode,
                    "stdout": safe_diagnostic_text(status_probe.stdout, 600),
                    "stderr": safe_diagnostic_text(status_probe.stderr, 600),
                }
            except Exception as probe_failure:
                diagnostic["pg_ctl_status_probe_error"] = safe_diagnostic_text(str(probe_failure), 600)
        if pg_run is not None and pg_run.exists():
            inventory = []
            try:
                for candidate in sorted(pg_run.rglob("*"))[:80]:
                    if candidate.is_file():
                        inventory.append({
                            "path": candidate.relative_to(pg_run).as_posix()[:240],
                            "size_bytes": candidate.stat().st_size,
                        })
                diagnostic["pg_temp_files"] = inventory
                diagnostic["pg_temp_file_count_capped"] = len(inventory) == 80
            except Exception as inventory_failure:
                diagnostic["pg_temp_inventory_error"] = safe_diagnostic_text(str(inventory_failure), 600)
        if pg_log is not None and pg_log.is_file():
            try:
                log_tail = pg_log.read_text(encoding="utf-8", errors="replace")[-3000:]
                diagnostic["postgres_log_tail"] = safe_diagnostic_text(log_tail, 2400)
            except Exception as log_failure:
                diagnostic["postgres_log_read_error"] = safe_diagnostic_text(str(log_failure), 600)
        try:
            args.summary_out.parent.mkdir(parents=True, exist_ok=True)
            args.summary_out.write_text(
                json.dumps(diagnostic, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8")
            print(json.dumps(diagnostic, ensure_ascii=False, sort_keys=True), flush=True)
        except Exception as evidence_failure:
            print("P25 bounded diagnostic could not be written: "
                  + safe_diagnostic_text(str(evidence_failure), 400), flush=True)
        raise
    finally:
        if server is not None:
            server.should_exit = True
        if server_task is not None:
            await asyncio.wait_for(server_task, timeout=30)
        if runtime is not None:
            runtime.dispose()
        if pg_started:
            drop_database(database, pg_port)
        ACTOR_BY_TOKEN.clear()
        if pg_run is not None and pg_run.exists() and pg_root is not None:
            pgctl = str(pg_root / "bin" / "pg_ctl.exe")
            state = subprocess.run([pgctl, "-D", str(pg_data), "status"], capture_output=True,
                                   timeout=20, check=False)
            if state.returncode == 0:
                run_checked([pgctl, "-D", str(pg_data), "-m", "fast", "-w", "stop"], timeout=90)
                state = subprocess.run([pgctl, "-D", str(pg_data), "status"], capture_output=True,
                                       timeout=20, check=False)
            if state.returncode == 0:
                raise RuntimeError("P25 PostgreSQL remains running; its D-drive data is preserved")
            if state.returncode != 3:
                raise RuntimeError("P25 could not confirm PostgreSQL stopped; its D-drive data is preserved")
            if pg_run.resolve(strict=True).parent != runner_temp or not pg_run.name.startswith("plm-out-p25-pg-"):
                raise RuntimeError("P25 cleanup refused an unowned PostgreSQL path")
            shutil.rmtree(pg_run)
        if work.exists():
            if not work.resolve(strict=True).is_relative_to(runner_temp) or not work.name.startswith("plm-out-p25-"):
                raise RuntimeError("P25 cleanup refused an unowned path")
            shutil.rmtree(work)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
