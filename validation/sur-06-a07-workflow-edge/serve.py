"""Owned Windows 11 Edge proof for the first two Workflow stages."""

from __future__ import annotations

import importlib.util
import queue
import socket
import subprocess
import sys
import tempfile
import uuid
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
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
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationEvidence,
    ChecklistQualificationRegistration,
    ChecklistQualificationRegistry,
    ChecklistQualificationReview,
    CurrentChecklistQualification,
)


ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load(ROOT / "validation/wfl-02-a02-a07-windows-browser/serve.py",
            "sur06a07_browser_base")
survey = load(ROOT / "validation/sur-06-a05-workflow-pg/verify.py",
              "sur06a07_survey_fixture")
review_fixture = survey.review_fixture
workflow_fixture = survey.workflow_fixture


class SyntheticHandoverOwner:
    """Composition-only proxy; real Handover Owner is proven by earlier gates."""

    def __init__(self, context, subject_id, subject_version_id) -> None:
        self.context = context
        self.subject_id = subject_id
        self.subject_version_id = subject_version_id

    def qualify_only_current_in_transaction(self, transaction, query):
        assert transaction is not None and query.project_id == self.context["project_id"]
        assert query.item_key in {"HANDOVER_BASELINE", "HANDOVER_ISSUES"}
        now = datetime.now(timezone.utc)
        fingerprint = b"h" * 32
        evidence = ChecklistQualificationEvidence(
            self.context["evidence_id"], query.project_id, 0,
            self.context["evidence_fingerprint"], now,
        )
        review = ChecklistQualificationReview(
            self.context["review_id"], self.context["review_round_id"],
            query.project_id, self.subject_id, self.subject_version_id, 0,
            fingerprint, now, "HND-02", "HANDOVER_ALL_V1",
        )
        return CurrentChecklistQualification(
            query.project_id, "HANDOVER", query.item_key, "HND-02",
            self.subject_id, self.subject_version_id, fingerprint,
            (evidence,), review,
        )


class SurveyRegistryOwner:
    def __init__(self, registry) -> None:
        self.registry = registry

    def qualify_only_current_in_transaction(self, transaction, query):
        return self.registry.qualify_only_current_in_transaction(transaction, query)


def build_registry(context):
    real = base._create_handover_qualification  # prove module loaded as expected
    assert callable(real)
    survey_registry = __import__(
        "plm_assistant.entrypoints.windows_workflow_checklist",
        fromlist=["_create_qualification_registry"],
    )._create_qualification_registry(
        documents=survey.Documents(context["document_facts"]),
        downloads=survey.Downloads(context["document_facts"]),
        parse_results=survey.NoParse(),
    )
    with review_fixture.schema.connect(context["database"]) as db:
        subject = db.execute(
            "SELECT handover_analysis_id,current_approved_version_ref "
            "FROM plm.hnd_analyses WHERE project_id=%s AND analysis_state='ACTIVE'",
            (context["project_id"],),
        ).fetchone()
    assert subject is not None and subject[1] is not None
    return ChecklistQualificationRegistry((
        ChecklistQualificationRegistration(
            ("HANDOVER_BASELINE", "HANDOVER_ISSUES"),
            SyntheticHandoverOwner(context, subject[0], subject[1]),
        ),
        ChecklistQualificationRegistration(
            ("SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"),
            SurveyRegistryOwner(survey_registry),
        ),
    ))


def reserve_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


def verify_browser(context: dict[str, object]) -> None:
    database = context["database"]
    project = context["project_id"]
    manager = context["manager_id"]
    assert isinstance(database, str) and isinstance(project, uuid.UUID)
    assert isinstance(manager, uuid.UUID)
    with review_fixture.schema.connect(database) as db, db.transaction():
        workflow_id = workflow_fixture.initialize(db, project, manager)

    registry = build_registry(context)
    base.browser.install_credential(database, manager)
    credential_target = "PLMProjectTool/Test-" + str(uuid.uuid4())
    backend = proxy = thread = listener = None
    temp_name = ""
    try:
        public_port = reserve_port()
        origin = f"http://127.0.0.1:{public_port}"
        database_url = URL.create(
            "postgresql+psycopg", username="poc_admin",
            password=uuid.uuid4().hex + uuid.uuid4().hex,
            host="127.0.0.1", port=55434, database=database,
        )
        base.browser.browser.auth_fixture.write_database_url(
            database_url.render_as_string(hide_password=False),
            target=credential_target,
        )
        with tempfile.TemporaryDirectory(prefix="plm-sur06-a07-") as directory, ExitStack() as stack:
            temp_name = directory
            config = BootstrapSettings(data_root=Path(directory), trusted_origins=(origin,))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",
                return_value=SimpleNamespace(guard=context["guard"]),
            ))
            keys = base.Keys()
            for module in ("windows_capability", "windows_handover",
                           "windows_handover_action_read", "windows_survey"):
                stack.enter_context(patch(
                    f"plm_assistant.entrypoints.{module}.WindowsSecretKeyProvider",
                    return_value=keys,
                ))
            stack.enter_context(patch(
                "plm_assistant.entrypoints.windows_workflow_checklist._create_qualification_registry",
                return_value=registry,
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
                ("create_windows_evidence_list_cursor_codec", EvidenceListCursorCodec(b"e" * 32)),
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
                    key_ref="synthetic-sur06-a07-upload-token",
                ),
            ))
            logs = StringIO()
            with redirect_stdout(logs):
                app = production.create_production_platform_write_app(
                    config, credential_target=credential_target,
                )
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0)); listener.listen(128)
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
            print(f"SUR06_A07_BROWSER_READY {origin} PROJECT={project} WORKFLOW={workflow_id} "
                  f"USERNAME='{base.browser.USERNAME}' PASSWORD='{base.browser.PASSWORD}'", flush=True)
            if sys.stdin.readline().strip() != "VERIFY":
                raise RuntimeError("browser validation stopped before VERIFY")
            with review_fixture.schema.connect(database) as db:
                assert db.execute(
                    "SELECT current_stage_key,lock_version FROM plm.wfl_project_workflows "
                    "WHERE workflow_id=%s", (workflow_id,),
                ).fetchone() == ("REQUIREMENT", 7)
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_checklist_records WHERE project_id=%s "
                    "AND result='PASS'", (project,),
                ).fetchone()[0] == 4
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_stage_transitions WHERE project_id=%s",
                    (project,),
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.wfl_transition_gate_items WHERE project_id=%s",
                    (project,),
                ).fetchone()[0] == 4
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
                    "AND action='WORKFLOW_CHECKLIST_RECORDED'", (project,),
                ).fetchone()[0] == 4
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
                    "AND action='WORKFLOW_STAGE_TRANSITIONED'", (project,),
                ).fetchone()[0] == 2
                assert db.execute(
                    "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s "
                    "AND state='COMPLETED' AND operation IN "
                    "('V1_WORKFLOW_START','V1_WORKFLOW_CHECKLIST_RECORD','V1_WORKFLOW_TRANSITION')",
                    (project,),
                ).fetchone()[0] == 7
            print("SUR_06_A07_WORKFLOW_EDGE_PASS: Edge -> built Vue -> production FastAPI -> "
                  "PostgreSQL 18.6 reached REQUIREMENT/v7 with 4 PASS, 2 transitions, "
                  "4 gates, exact Audit and idempotency history", flush=True)
    finally:
        if proxy is not None:
            if proxy.poll() is None:
                try:
                    proxy.stdin.write("STOP\n"); proxy.stdin.flush(); proxy.wait(timeout=10)
                except (BrokenPipeError, subprocess.TimeoutExpired):
                    proxy.kill(); proxy.wait(timeout=10)
            for stream in (proxy.stdin, proxy.stdout, proxy.stderr):
                if stream is not None:
                    stream.close()
        if backend is not None:
            backend.should_exit = True
        if thread is not None:
            thread.join(timeout=10); assert not thread.is_alive()
        if listener is not None:
            listener.close()
        base.browser.browser.auth_fixture.delete_test_credential(credential_target)
    assert not temp_name or not Path(temp_name).exists()
    print("SUR_06_A07_WORKFLOW_EDGE_CLEANUP_PASS", flush=True)


def main() -> None:
    review_fixture.main(verify_browser)
    print("SUR_06_A07_OWNED_FIXTURE_CLEANUP_PASS")


if __name__ == "__main__":
    main()
