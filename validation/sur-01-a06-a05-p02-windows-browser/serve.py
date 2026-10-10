"""Owned Windows 11 browser/HTTP/PostgreSQL proof for Survey source location."""

from __future__ import annotations

import hashlib
import importlib.util
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import patch

import uvicorn
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.windows_ai_read_cursor import WindowsAIReadCursorCodecs
from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = load(ROOT / "validation/sur-01-a02-definition-schema/verify.py",
              "sur_a05_browser_schema")
browser = load(ROOT / "validation/hnd-02-a05-a06-windows-browser/serve.py",
               "sur_a05_browser_fixture")


class Keys:
    def resolve_key(self, key_ref: str) -> bytes:
        assert type(key_ref) is str and key_ref
        return (key_ref.encode() + b"-" + b"k" * 64)[:32]


class Guard:
    @staticmethod
    def require_valid(*, trace_id: uuid.UUID) -> None:
        assert type(trace_id) is uuid.UUID and trace_id.int != 0


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def main() -> None:
    name = "sur01a06a05p02_" + uuid.uuid4().hex[:8]
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    backend = proxy = thread = listener = None
    temp_name = ""
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            database_url = URL.create(
                "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
                port=55434, database=name,
            )
            cfg = create_migration_config(database_url)
            command.upgrade(cfg, "head"); command.check(cfg)
            with tempfile.TemporaryDirectory(prefix="plm-sur-a05-browser-") as directory, ExitStack() as stack:
                temp_name = directory
                data_root = Path(directory)
                template_bytes = b"Synthetic project template for Survey source location."
                record_bytes = b"Synthetic customer-approved handover evidence."
                with schema.connect(name) as db:
                    ids = schema.seed_dependencies(db)
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("UPDATE plm.doc_file_objects SET scope='PROJECT',project_id=%s "
                                   "WHERE file_object_id=%s", (ids["project"], ids["template_file"]))
                        db.execute("UPDATE plm.doc_documents SET scope='PROJECT',project_id=%s "
                                   "WHERE document_id=%s", (ids["project"], ids["template_document"]))
                        db.execute("UPDATE plm.doc_document_versions SET scope='PROJECT',project_id=%s "
                                   "WHERE document_version_id=%s", (ids["project"], ids["template_version"]))
                        for prefix, content in (("template", template_bytes), ("record", record_bytes)):
                            digest = hashlib.sha256(content).digest()
                            _, locator = LocalFileStorage.locators(
                                scope="PROJECT", project_id=ids["project"],
                                file_object_id=ids[prefix + "_file"])
                            target = data_root / locator
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(content)
                            db.execute("UPDATE plm.doc_file_objects SET storage_locator=%s,sha256=%s,size_bytes=%s "
                                       "WHERE file_object_id=%s",
                                       (locator, digest, len(content), ids[prefix + "_file"]))
                            db.execute("UPDATE plm.doc_document_versions SET content_sha256=%s,size_bytes=%s "
                                       "WHERE document_version_id=%s", (digest, len(content), ids[prefix + "_version"]))
                        evidence = uuid.uuid4()
                        db.execute("""
                            INSERT INTO plm.evd_evidence_records(
                              evidence_id,scope,project_id,document_id,document_version_id,
                              locator_type,locator_schema_version,locator_payload,
                              content_fingerprint,display_label,display_excerpt,
                              eligibility_state,eligibility_reason,created_by)
                            VALUES (%s,'PROJECT',%s,%s,%s,'DOCUMENT',1,
                              '{"locator_type":"DOCUMENT"}'::jsonb,%s,
                              '第 1 页 · 客户确认的交接范围','合成验收短提示，不是权威正文',
                              'ELIGIBLE','browser fixture',%s)
                        """, (evidence, ids["project"], ids["record_document"],
                                ids["record_version"], hashlib.sha256(record_bytes).digest(), ids["actor"]))
                        db.execute("""
                            INSERT INTO plm.hnd_item_evidence_refs(
                              analysis_item_row_id,handover_analysis_version_id,
                              handover_analysis_id,project_id,evidence_id,ordinal)
                            VALUES (%s,%s,%s,%s,%s,0)
                        """, (ids["handover_item_row"], ids["analysis_version"],
                                ids["analysis"], ids["project"], evidence))
                        db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
                                   "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
                                   (ids["project"], ids["actor"], ids["department"]))
                    survey, version = schema.insert_valid(db, ids, name="浏览器来源定位调研")
                    questions = tuple(row[0] for row in db.execute(
                        "SELECT question_id FROM plm.srv_questions WHERE survey_version_id=%s ORDER BY sequence_no",
                        (version,)).fetchall())
                    before = db.execute("SELECT (SELECT count(*) FROM plm.srv_surveys),"
                        "(SELECT count(*) FROM plm.srv_survey_versions)").fetchone()
                browser.install_credential(name, ids["actor"])
                public_port = reserve_port(); origin = f"http://127.0.0.1:{public_port}"
                secret_url = URL.create(
                    "postgresql+psycopg", username="poc_admin",
                    password=uuid.uuid4().hex + uuid.uuid4().hex,
                    host="127.0.0.1", port=55434, database=name,
                )
                browser.browser.auth_fixture.write_database_url(
                    secret_url.render_as_string(hide_password=False), target=credential_target)
                config = BootstrapSettings(data_root=data_root, trusted_origins=(origin,))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                    return_value=SimpleNamespace(guard=Guard()),
                ))
                keys = Keys()
                for module in ("windows_capability", "windows_handover",
                               "windows_handover_action_read", "windows_survey"):
                    stack.enter_context(patch(
                        f"plm_assistant.entrypoints.{module}.WindowsSecretKeyProvider",
                        return_value=keys,
                    ))
                prefix = "plm_assistant.entrypoints.production_login."
                codecs = (
                    ("create_windows_secret_list_cursor_codec", SecretListCursorCodec(b"s" * 32)),
                    ("create_windows_project_member_cursor_codec", MemberListCursorCodec(b"m" * 32)),
                    ("create_windows_project_department_cursor_codec", DepartmentListCursorCodec(b"d" * 32)),
                    ("create_windows_document_list_cursor_codec", DocumentListCursorCodec(b"l" * 32)),
                    ("create_windows_document_version_cursor_codec", VersionListCursorCodec(b"v" * 32)),
                    ("create_windows_document_parse_cursor_codec", ParseListCursorCodec(b"p" * 32)),
                    ("create_windows_user_list_cursor_codec", UserListCursorCodec(b"u" * 32)),
                    ("create_windows_job_list_cursor_codec", JobListCursorCodec(b"j" * 32)),
                    ("create_windows_audit_cursor_codec", AuditListCursorCodec(b"a" * 32)),
                    ("create_windows_ai_provider_list_cursor_codec", ProviderListCursorCodec(b"r" * 32)),
                    ("create_windows_ai_model_list_cursor_codec", ModelListCursorCodec(b"o" * 32)),
                    ("create_windows_ai_prompt_list_cursor_codec", PromptListCursorCodec(b"q" * 32)),
                    ("create_windows_ai_read_cursor_codecs", WindowsAIReadCursorCodecs(
                        AITaskListCursorCodec(b"t" * 32), AIInvocationListCursorCodec(b"i" * 32))),
                )
                for function, codec in codecs:
                    stack.enter_context(patch(prefix + function, return_value=codec))
                stack.enter_context(patch(
                    "plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",
                    return_value=object(),
                ))
                stack.enter_context(patch(
                    prefix + "create_windows_document_upload_token_issuer",
                    return_value=HmacUploadTokenIssuer(
                        provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                        key_ref="synthetic-survey-location-browser-upload-token",
                    ),
                ))
                logs = StringIO()
                with redirect_stdout(logs):
                    app = production.create_production_platform_write_app(
                        config, credential_target=credential_target)
                listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(128)
                backend = uvicorn.Server(uvicorn.Config(
                    app, log_level="critical", access_log=False, proxy_headers=False,
                    lifespan="on", timeout_graceful_shutdown=5,
                ))
                thread = Thread(target=lambda: backend.run(sockets=[listener]), daemon=False)
                thread.start(); deadline = monotonic() + 20
                while not backend.started:
                    if not thread.is_alive() or monotonic() > deadline:
                        raise RuntimeError("owned backend startup failed: " + logs.getvalue()[-1000:])
                    sleep(.05)
                proxy = subprocess.Popen(
                    ["node", str(ROOT / "validation/rag-04-a06-p08-windows-browser/start-preview-proxy.mjs"),
                     str(public_port), str(listener.getsockname()[1])],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                ready: queue.Queue[str] = queue.Queue()
                Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
                if ready.get(timeout=20) != "OWNED_RAG_PREVIEW_READY":
                    raise RuntimeError("owned frontend startup failed: " + proxy.stderr.read())
                print(f"SUR_SOURCE_BROWSER_READY {origin}/login PROJECT={ids['project']} SURVEY={survey} "
                      f"VERSION={version} QUESTIONS={','.join(map(str, questions))} EVIDENCE={evidence} "
                      f"USERNAME='{browser.USERNAME}' PASSWORD='{browser.PASSWORD}'", flush=True)
                if sys.stdin.readline().strip() != "VERIFY":
                    raise RuntimeError("browser validation stopped before VERIFY")
                with schema.connect(name) as db:
                    after = db.execute("SELECT (SELECT count(*) FROM plm.srv_surveys),"
                        "(SELECT count(*) FROM plm.srv_survey_versions)").fetchone()
                    assert after == before, (before, after)
                print("SUR_01_A06_A05_P02_WINDOWS_BROWSER_PASS: real Edge -> built Vue -> "
                      "production FastAPI -> PostgreSQL 18 manual, project Document, Handover, "
                      "Evidence Viewer and zero-write source location passed", flush=True)
        finally:
            if proxy is not None:
                if proxy.poll() is None:
                    try:
                        proxy.stdin.write("STOP\n"); proxy.stdin.flush(); proxy.wait(timeout=10)
                    except (BrokenPipeError, subprocess.TimeoutExpired):
                        proxy.kill(); proxy.wait(timeout=10)
                for stream in (proxy.stdin, proxy.stdout, proxy.stderr):
                    if stream is not None: stream.close()
            if backend is not None: backend.should_exit = True
            if thread is not None:
                thread.join(timeout=10); assert not thread.is_alive()
            if listener is not None: listener.close()
            browser.browser.auth_fixture.delete_test_credential(credential_target)
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
    assert not temp_name or not Path(temp_name).exists()
    print("SUR_01_A06_A05_P02_WINDOWS_BROWSER_CLEANUP_PASS", flush=True)


if __name__ == "__main__":
    main()
