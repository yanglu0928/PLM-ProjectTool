"""Owned Windows 11 Edge/Vue/FastAPI/PostgreSQL proof for Stage Transition."""

from __future__ import annotations

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
from sqlalchemy.engine import URL

from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.windows_ai_read_cursor import WindowsAIReadCursorCodecs
from plm_assistant.entrypoints.windows_workflow_checklist import _create_handover_qualification
from plm_assistant.modules.ai.api.invocation_list_cursor import AIInvocationListCursorCodec
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.model_list_cursor import ModelListCursorCodec
from plm_assistant.modules.ai.application.prompt_list_cursor import PromptListCursorCodec
from plm_assistant.modules.ai.application.provider_list_cursor import ProviderListCursorCodec
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.application.read_parse_result import DocumentParseResultReadService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer
from plm_assistant.modules.handover.application.workflow_qualification_owner import HandoverWorkflowCurrentQualificationQuery
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.workflow.application.record_checklist import RecordWorkflowChecklist, WorkflowChecklistRecordService
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import SqlAlchemyChecklistRecordAppendRepository
from plm_assistant.modules.workflow.infrastructure.checklist_record_replay_repository import SqlAlchemyChecklistRecordReplayRepository


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handover = load(ROOT / "validation/hnd-03-a04-workflow-qualification-pg/verify.py", "wfl_a07_handover")
workflow = load(ROOT / "validation/wfl-02-a01-p03-history-schema/verify.py", "wfl_a07_workflow")
browser = load(ROOT / "validation/hnd-02-a05-a06-windows-browser/serve.py", "wfl_a07_browser")


class Keys:
    def resolve_key(self, key_ref: str) -> bytes:
        assert type(key_ref) is str and key_ref
        return (key_ref.encode() + b"-" + b"k" * 64)[:32]


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def prepare_checklists(context: dict[str, object], workflow_id: uuid.UUID) -> None:
    runtime = context["runtime"]
    project_id = context["project_id"]
    token = context["manager_token"]
    assert isinstance(project_id, uuid.UUID) and isinstance(token, bytes)
    parse_results = DocumentParseResultReadService(
        documents=context["downloads"], metadata=SqlAlchemyParseResultReadRepository(),
        storage=LocalParseResultStorage(context["data_root"]), unit_of_work=runtime.unit_of_work,
    )
    qualification = _create_handover_qualification(
        documents=context["documents"], downloads=context["downloads"], parse_results=parse_results,
    )
    repository = SqlAlchemyProjectAuthorizationRepository()
    records = WorkflowChecklistRecordService(
        unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectWriteAccess(),
        projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work, repository=repository),
        license_guard=context["license_guard"], qualification=qualification,
        appender=SqlAlchemyChecklistRecordAppendRepository(),
        replay=SqlAlchemyChecklistRecordReplayRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=context["audit"],
    )
    for expected, item_key in enumerate(("HANDOVER_BASELINE", "HANDOVER_ISSUES"), start=1):
        trace_id = uuid.uuid4()
        with runtime.unit_of_work() as tx:
            proof = qualification.qualify_only_current_in_transaction(
                tx, HandoverWorkflowCurrentQualificationQuery(token, trace_id, project_id, item_key),
            )
        result = records.record(RecordWorkflowChecklist(
            token, handover.CSRF, trace_id, project_id, item_key, ChecklistState.PASS,
            tuple(value.evidence_id for value in proof.evidence), (), expected,
        ), idempotency_key=str(uuid.uuid4()))
        assert result.record.workflow_id == workflow_id


def verify_browser(context: dict[str, object]) -> None:
    database, project_id, manager_id = context["database"], context["project_id"], context["manager_id"]
    data_root = context["data_root"]
    assert isinstance(database, str) and isinstance(project_id, uuid.UUID)
    assert isinstance(manager_id, uuid.UUID) and isinstance(data_root, Path)
    with handover.connect(database) as db, db.transaction():
        workflow_id = workflow.initialize(db, project_id, manager_id)
        db.execute("UPDATE plm.wfl_project_workflows SET workflow_state='ACTIVE',current_stage_key='HANDOVER',lock_version=1,updated_at=statement_timestamp() WHERE workflow_id=%s", (workflow_id,))
        db.execute("UPDATE plm.wfl_stages SET stage_state='ACTIVE' WHERE workflow_id=%s AND stage_key='HANDOVER'", (workflow_id,))
    prepare_checklists(context, workflow_id)
    browser.install_credential(database, manager_id)
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    backend = proxy = thread = listener = None
    temp_name = ""
    try:
        public_port = reserve_port()
        origin = f"http://127.0.0.1:{public_port}"
        database_url = URL.create("postgresql+psycopg", username="poc_admin",
            password=uuid.uuid4().hex + uuid.uuid4().hex, host="127.0.0.1", port=55434, database=database)
        browser.browser.auth_fixture.write_database_url(
            database_url.render_as_string(hide_password=False), target=credential_target)
        with tempfile.TemporaryDirectory(prefix="plm-wfl-a07-browser-") as directory, ExitStack() as stack:
            temp_name = directory
            config = BootstrapSettings(data_root=data_root, trusted_origins=(origin,))
            stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=SimpleNamespace(guard=context["license_guard"])))
            keys = Keys()
            for module in ("windows_capability", "windows_handover", "windows_handover_action_read"):
                stack.enter_context(patch(f"plm_assistant.entrypoints.{module}.WindowsSecretKeyProvider", return_value=keys))
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
            stack.enter_context(patch("plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service", return_value=object()))
            stack.enter_context(patch(prefix + "create_windows_document_upload_token_issuer",
                return_value=HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref: b"u" * 32),
                    key_ref="synthetic-transition-browser-upload-token")))
            logs = StringIO()
            with redirect_stdout(logs):
                app = production.create_production_platform_write_app(config, credential_target=credential_target)
            listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(128)
            backend = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
            thread = Thread(target=lambda: backend.run(sockets=[listener]), daemon=False); thread.start()
            deadline = monotonic() + 20
            while not backend.started:
                if not thread.is_alive() or monotonic() > deadline:
                    raise RuntimeError("owned backend startup failed: " + logs.getvalue()[-1000:])
                sleep(.05)
            proxy = subprocess.Popen(["node", str(ROOT / "validation/rag-04-a06-p08-windows-browser/start-preview-proxy.mjs"),
                str(public_port), str(listener.getsockname()[1])], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            ready: queue.Queue[str] = queue.Queue()
            Thread(target=lambda: ready.put(proxy.stdout.readline().strip()), daemon=True).start()
            if ready.get(timeout=20) != "OWNED_RAG_PREVIEW_READY":
                raise RuntimeError("owned frontend startup failed: " + proxy.stderr.read())
            print(f"WFL_TRANSITION_BROWSER_READY {origin}/login PROJECT={project_id} WORKFLOW={workflow_id} "
                f"USERNAME='{browser.USERNAME}' PASSWORD='{browser.PASSWORD}'", flush=True)
            if sys.stdin.readline().strip() != "VERIFY":
                raise RuntimeError("browser validation stopped before VERIFY")
            with handover.connect(database) as db:
                assert db.execute("SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows WHERE project_id=%s", (project_id,)).fetchone() == ("SURVEY", 4)
                assert db.execute("SELECT stage_key,stage_state FROM plm.wfl_stages WHERE project_id=%s AND stage_key IN ('HANDOVER','SURVEY') ORDER BY stage_order", (project_id,)).fetchall() == [("HANDOVER", "COMPLETED"), ("SURVEY", "ACTIVE")]
                assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions WHERE project_id=%s", (project_id,)).fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.wfl_transition_gate_items WHERE project_id=%s", (project_id,)).fetchone()[0] == 2
                assert db.execute("SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s AND action='WORKFLOW_STAGE_TRANSITIONED'", (project_id,)).fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s AND operation='V1_WORKFLOW_TRANSITION' AND state='COMPLETED'", (project_id,)).fetchone()[0] == 1
            print("WFL_02_A02_A07_WINDOWS_BROWSER_PASS: real Edge -> built Vue -> production FastAPI -> PostgreSQL 18 transition/refresh and exact Gate/Audit/idempotency facts verified", flush=True)
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
    assert not temp_name or not Path(temp_name).exists()
    print("WFL_02_A02_A07_WINDOWS_BROWSER_CLEANUP_PASS", flush=True)


def main() -> None:
    handover.main(verify_browser)
    print("WFL_02_A02_A07_OWNED_FIXTURE_CLEANUP_PASS")


if __name__ == "__main__":
    main()
