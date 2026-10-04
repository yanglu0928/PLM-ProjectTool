"""Windows 11/PG18.6/Vault/HTTP proof for the frozen AI read surfaces."""

from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from ctypes import wintypes

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_ai_read import create_windows_ai_read_routers
from plm_assistant.entrypoints.windows_ai_read_cursor import (
    AI_READ_CURSOR_KEY_REF,
    ProductionAIReadCursorStartupError,
    create_windows_ai_read_cursor_codecs,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.ai.infrastructure.suggestion_read_repository import (
    SqlAlchemyAISuggestionReadRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
    SqlAlchemyDeploymentReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.document.application.prepare_download import PrepareDownloadService
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.document.application.read_parse_result import (
    DocumentParseResultReadService,
)
from plm_assistant.modules.document.application.resolve_parse_nodes import (
    DocumentNodeLocationService,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
    _TARGET_PREFIX,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


ORIGIN = "https://plm.example.test"


def load_helper(directory: str, name: str):
    path = Path(__file__).resolve().parents[1] / directory / "verify.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def connect(name: str):
    return psycopg.connect(
        host="127.0.0.1", port=55434, user="poc_admin", dbname=name,
        autocommit=True, connect_timeout=5,
    )


class MissingKey:
    def resolve_key(self, _key_ref: str): return None


def seed_member(db, *, project, department, role: str, label: str,
                token: bytes, csrf: bytes):
    normalized = label.lower() + "-" + uuid.uuid4().hex[:8]
    actor = db.execute(
        "INSERT INTO plm.auth_users(username_display,username_normalized) "
        "VALUES (%s,%s) RETURNING user_id", (label, normalized),
    ).fetchone()[0]
    credential = db.execute(
        "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
        "password_hash,algorithm_id,parameter_set) VALUES "
        "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
        "RETURNING password_credential_id", (actor,),
    ).fetchone()[0]
    db.execute(
        "UPDATE plm.auth_users SET state='ENABLED',credential_version=1,"
        "active_password_credential_id=%s WHERE user_id=%s", (credential, actor),
    )
    db.execute(
        "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
        "credential_version,idle_expires_at,absolute_expires_at) VALUES "
        "(%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
        "statement_timestamp()+interval '2 hours')",
        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), actor),
    )
    db.execute(
        "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
        "project_role) VALUES (%s,%s,%s,%s)",
        (project, actor, department, role),
    )
    return actor


def seed_results(context: dict[str, object]) -> dict[str, object]:
    payload = {
        "schema_ref": "gap-output.v2", "schema_version": 2,
        "items": [{
            "category": "PENDING_CONFIRMATION", "title": "确认合成范围",
            "summary": "需要确认合成验证范围", "rationale": "固定节点提供依据",
            "recommendation": "请维护实际范围", "source_citations": [{
                "source_ordinal": 1, "node_ids": ["synthetic-1"],
            }],
            "confirmation": {
                "required": True, "question": "实际范围是什么？",
                "required_fields": [{
                    "key": "SCOPE", "label": "实际范围",
                    "prompt": "请填写实际范围", "reason": "用于确定实施边界",
                    "required": True,
                }],
            },
        }],
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    pm_token = context["session_token"]
    csrf = context["csrf_token"]
    cm_token, im_token, customer_token = b"g" * 32, b"i" * 32, b"u" * 32
    with connect(context["database"]) as db:
        project, task_id = context["project_id"], context["ai_task_id"]
        actor = db.execute(
            "SELECT requested_by FROM plm.ai_tasks WHERE ai_task_id=%s", (task_id,),
        ).fetchone()[0]
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments WHERE project_id=%s "
            "ORDER BY created_at LIMIT 1", (project,),
        ).fetchone()[0]
        seed_member(db, project=project, department=department,
                    role="CUSTOMER_MANAGER", label="AI Read Customer Manager",
                    token=cm_token, csrf=csrf)
        seed_member(db, project=project, department=department,
                    role="IMPLEMENTATION_MEMBER", label="AI Read Other Implementer",
                    token=im_token, csrf=csrf)
        seed_member(db, project=project, department=department,
                    role="CUSTOMER_MEMBER", label="AI Read Customer Member",
                    token=customer_token, csrf=csrf)
        facts = db.execute(
            "SELECT t.content_plan_ref,t.input_fingerprint,t.prompt_template_ref,"
            "t.prompt_version_no,s.egress_authorization_snapshot_id,p.ai_provider_id,"
            "p.provider_config_version_id,p.ai_model_id,p.model_revision,"
            "p.payload_fingerprint,"
            "c.content_revision_id,c.content_object_id,c.object_id,c.version_id,"
            "c.source_fingerprint,c.content_fingerprint "
            "FROM plm.ai_tasks t JOIN plm.ai_egress_authorization_snapshots s "
            "ON s.ai_task_id=t.ai_task_id JOIN plm.ai_execution_content_plans p "
            "ON p.content_plan_id=t.content_plan_ref JOIN plm.ai_execution_content_sources c "
            "ON c.content_plan_id=p.content_plan_id AND c.source_ordinal=1 "
            "WHERE t.ai_task_id=%s", (task_id,),
        ).fetchone()
        (plan, input_hash, prompt, prompt_version, snapshot, provider, config,
         model, revision, plan_payload_hash, parse_record, result_ref, document, version,
         source_hash, result_hash) = facts
        invocations = (uuid.uuid4(), uuid.uuid4())
        with db.transaction():
            for attempt, invocation in enumerate(invocations, 1):
                db.execute(
                    "INSERT INTO plm.ai_invocations(ai_invocation_id,ai_task_id,attempt_no,"
                    "scope,project_id,ai_provider_id,provider_config_version_id,ai_model_id,"
                    "model_revision_observed,prompt_template_id,prompt_version_no,"
                    "output_schema_ref,schema_version,input_fingerprint,"
                    "egress_authorization_mode,egress_authorization_snapshot_id,"
                    "request_payload_fingerprint,content_plan_ref,invocation_state,"
                    "schema_validation_required,schema_validation_state) VALUES "
                    "(%s,%s,%s,'PROJECT',%s,%s,%s,%s,%s,%s,%s,'gap-output.v2',2,%s,"
                    "'AUTHORIZED',%s,%s,%s,'PENDING',true,'PENDING')",
                    (invocation, task_id, attempt, project, provider, config, model,
                     revision, prompt, prompt_version, input_hash, snapshot,
                     plan_payload_hash, plan),
                )
                if attempt == 1:
                    db.execute(
                        "UPDATE plm.ai_invocations SET invocation_state='FAILED',"
                        "schema_validation_state='INVALID',error_code='PROVIDER_TIMEOUT',"
                        "retryable=true,started_at=statement_timestamp(),"
                        "completed_at=statement_timestamp(),lock_version=1 "
                        "WHERE ai_invocation_id=%s", (invocation,),
                    )
                else:
                    db.execute(
                        "UPDATE plm.ai_invocations SET invocation_state='RUNNING',"
                        "started_at=statement_timestamp(),lock_version=1 "
                        "WHERE ai_invocation_id=%s", (invocation,),
                    )
            suggestion = uuid.uuid4()
            db.execute(
                "INSERT INTO plm.ai_suggestion_payloads(suggestion_payload_id,"
                "ai_invocation_id,ai_task_id,scope,project_id,output_schema_ref,"
                "schema_version,canonical_payload,payload_fingerprint,fact_status,"
                "quality_flags) VALUES (%s,%s,%s,'PROJECT',%s,'gap-output.v2',2,%s,%s,"
                "'NOT_FORMAL_FACT',%s)",
                (suggestion, invocations[1], task_id, project, Jsonb(payload),
                 hashlib.sha256(canonical).digest(), Jsonb(["REVIEW_REQUIRED"])),
            )
            db.execute(
                "INSERT INTO plm.ai_suggestion_evidence_refs(suggestion_payload_id,"
                "ref_ordinal,scope,project_id,owner_module,object_type,object_id,"
                "version_id,content_fingerprint) VALUES "
                "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s,%s)",
                (suggestion, project, document, version, result_hash),
            )
            db.execute(
                "UPDATE plm.ai_invocations SET suggestion_payload_ref=%s,"
                "response_fingerprint=%s,invocation_state='SUCCEEDED',"
                "schema_validation_state='VALID',completed_at=statement_timestamp(),"
                "lock_version=2 WHERE ai_invocation_id=%s",
                (suggestion, hashlib.sha256(b"synthetic-response").digest(),
                 invocations[1]),
            )
            db.execute(
                "UPDATE plm.ai_tasks SET task_state='SUCCEEDED',suggestion_state='AVAILABLE',"
                "current_invocation_ref=%s,started_at=statement_timestamp(),"
                "completed_at=statement_timestamp(),lock_version=1 WHERE ai_task_id=%s",
                (invocations[1], task_id),
            )
            other_task, other_trace = uuid.uuid4(), uuid.uuid4()
            other_job = db.execute(
                "INSERT INTO plm.job_jobs(owner_module,job_type,scope,project_id,actor_ref,"
                "trace_id,payload_refs,idempotency_key,max_attempts) VALUES "
                "('ai','AI_TASK_EXECUTE','PROJECT',%s,%s,%s,%s,%s,3) RETURNING job_id",
                (project, actor, str(other_trace),
                 Jsonb({"ai_task_id": str(other_task)}),
                 "ai-read-page-" + uuid.uuid4().hex),
            ).fetchone()[0]
            db.execute(
                "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,requested_by,"
                "input_fingerprint,prompt_policy_ref,output_schema_ref,context_policy_ref,"
                "prompt_template_ref,prompt_version_no,prompt_policy_version,task_parameters,"
                "task_parameters_fingerprint,content_plan_ref,job_ref,trace_id) "
                "SELECT %s,'PROJECT',project_id,task_type,requested_by,input_fingerprint,"
                "prompt_policy_ref,output_schema_ref,context_policy_ref,prompt_template_ref,"
                "prompt_version_no,prompt_policy_version,task_parameters,"
                "task_parameters_fingerprint,content_plan_ref,%s,%s FROM plm.ai_tasks "
                "WHERE ai_task_id=%s",
                (other_task, other_job, other_trace, task_id),
            )
            db.execute(
                "INSERT INTO plm.ai_task_input_refs(ai_task_id,ref_ordinal,scope,project_id,"
                "owner_module,object_type,object_id,version_id) VALUES "
                "(%s,1,'PROJECT',%s,'document','DOCUMENT_VERSION',%s,%s)",
                (other_task, project, document, version),
            )
        file_row = db.execute(
            "SELECT f.storage_locator,f.sha256,f.size_bytes FROM plm.doc_file_objects f "
            "JOIN plm.doc_document_versions v ON v.file_object_id=f.file_object_id "
            "WHERE v.document_version_id=%s", (version,),
        ).fetchone()
        parse_locator = db.execute(
            "SELECT storage_locator FROM plm.doc_parse_result_refs "
            "WHERE parse_result_ref_id=%s", (result_ref,),
        ).fetchone()[0]
    original = "合成项目需求原文".encode("utf-8")
    assert hashlib.sha256(original).digest() == file_row[1] and len(original) == file_row[2]
    source_path = context["result_root"] / file_row[0]
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(original)
    return {
        "pm_token": pm_token, "cm_token": cm_token, "im_token": im_token,
        "customer_token": customer_token, "project": project, "task": task_id,
        "document": document, "version": version,
        "parse_record": parse_record,
        "parse_path": context["result_root"] / parse_locator,
    }


def validate(context: dict[str, object]) -> None:
    facts = seed_results(context)
    try:
        create_windows_ai_read_cursor_codecs(resolver=MissingKey())
    except ProductionAIReadCursorStartupError:
        pass
    else:
        raise AssertionError("missing AI read cursor key was accepted")
    vault = WindowsSecretKeyProvider()
    installed = vault.resolve_key(AI_READ_CURSOR_KEY_REF) is None
    if installed:
        vault.install_new(AI_READ_CURSOR_KEY_REF, b"r" * 32)
    try:
        codecs = create_windows_ai_read_cursor_codecs()
        runtime, guard = context["runtime"], context["guard"]
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=guard, repository=SqlAlchemyDocumentReadRepository(),
        )
        downloads = PrepareDownloadService(
            reader=documents, storage=LocalFileStorage(context["result_root"]),
            unit_of_work=runtime.unit_of_work, audit=context["audit"],
        )
        parse_results = DocumentParseResultReadService(
            documents=downloads, metadata=SqlAlchemyParseResultReadRepository(),
            storage=LocalParseResultStorage(context["result_root"]),
            unit_of_work=runtime.unit_of_work,
        )
        routers = create_windows_ai_read_routers(
            runtime=runtime, origins=LoginOriginPolicy([ORIGIN]),
            license_guard=guard, task_cursors=codecs.task,
            invocation_cursors=codecs.invocation, documents=documents,
            parse_results=parse_results,
        )
        with runtime.unit_of_work() as transaction:
            projection = SqlAlchemyAISuggestionReadRepository().get(
                transaction, project_id=facts["project"], ai_task_id=facts["task"],
            )
        assert projection is not None and projection.schema_version == 2
        DocumentNodeLocationService(results=parse_results).resolve(
            DocumentReadQuery(
                session_token=facts["pm_token"], trace_id=uuid.uuid4(),
                scope="PROJECT", project_id=facts["project"],
            ),
            document_id=facts["document"],
            document_version_id=facts["version"],
            parse_record_id=facts["parse_record"],
            node_ids=("synthetic-1",),
        )
        app = create_app(
            ai_task_list_router=routers.tasks,
            ai_task_invocation_list_router=routers.invocations,
            ai_suggestion_read_router=routers.suggestion,
        )
        base = f"/api/v1/projects/{facts['project']}/ai-tasks"
        task_path = base + f"/{facts['task']}"
        headers = lambda token: {"cookie": "plm_session=" + token.hex(),
                                 "host": "plm.example.test"}
        with TestClient(app, base_url=ORIGIN) as client:
            page = client.get(base + "?page_size=1", headers=headers(facts["pm_token"]))
            assert page.status_code == 200, page.text
            cursor = page.json()["data"]["next_cursor"]
            assert cursor.startswith("ait1.") and str(facts["task"]) not in cursor
            assert client.get(
                base + "?page_size=1&cursor=" + cursor,
                headers=headers(facts["pm_token"]),
            ).status_code == 200
            attempts = client.get(
                task_path + "/invocations?page_size=1",
                headers=headers(facts["pm_token"]),
            )
            assert attempts.status_code == 200, attempts.text
            invocation_cursor = attempts.json()["data"]["next_cursor"]
            assert invocation_cursor.startswith("aii1.")
            assert client.get(
                task_path + "/invocations?page_size=1&cursor=" + invocation_cursor,
                headers=headers(facts["pm_token"]),
            ).status_code == 200
            suggestion = client.get(
                task_path + "/suggestion", headers=headers(facts["pm_token"]),
            )
            assert suggestion.status_code == 200, suggestion.text
            data = suggestion.json()["data"]
            assert data["fact_status"] == "NOT_FORMAL_FACT"
            assert data["source_locations"][0]["precision"] == "PARSED_NODE"
            assert data["source_locations"][0]["locations"][0]["node_id"] == "synthetic-1"
            assert data["payload"]["items"][0]["confirmation"]["required"] is True
            assert client.get(
                task_path + "/suggestion", headers=headers(facts["cm_token"]),
            ).status_code == 200
            for token in (facts["im_token"], facts["customer_token"]):
                assert client.get(
                    task_path + "/suggestion", headers=headers(token),
                ).status_code == 404
            assert client.get(
                base, headers=headers(facts["im_token"]),
            ).json()["data"]["items"] == []
            original_result = facts["parse_path"].read_bytes()
            facts["parse_path"].write_bytes(b"x" * len(original_result))
            try:
                assert client.get(
                    task_path + "/suggestion", headers=headers(facts["pm_token"]),
                ).status_code == 404
            finally:
                facts["parse_path"].write_bytes(original_result)
            guard.enabled = False
            assert client.get(
                task_path + "/suggestion", headers=headers(facts["pm_token"]),
            ).status_code == 403
            guard.enabled = True
            with connect(context["database"]) as db:
                with db.transaction():
                    db.execute(
                        "UPDATE plm.doc_documents SET effective_version_ref=NULL "
                        "WHERE document_id=%s", (facts["document"],),
                    )
                    db.execute(
                        "UPDATE plm.doc_document_versions SET availability_state='REVOKED' "
                        "WHERE document_version_id=%s", (facts["version"],),
                    )
            assert client.get(
                task_path + "/suggestion", headers=headers(facts["pm_token"]),
            ).status_code == 404
            assert client.get(
                base, headers=headers(facts["pm_token"]),
            ).status_code == 200
            for forbidden in ("secret", "storage_locator", "response_fingerprint",
                              "provider_request_ref", "source_fingerprint"):
                assert forbidden not in suggestion.text.lower()
    finally:
        if installed:
            library = ctypes.WinDLL("Advapi32", use_last_error=True)
            library.CredDeleteW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            ]
            library.CredDeleteW.restype = wintypes.BOOL
            assert library.CredDeleteW(_TARGET_PREFIX + AI_READ_CURSOR_KEY_REF, 1, 0)
    print(
        "AI_04_A07_P07_WINDOWS_READ_COMPOSITION_PASS: Windows11/PostgreSQL18.6 "
        "real current-account Vault key, Task/Invocation encrypted pagination, V2 canonical "
        "Suggestion HTTP, PM/CM authorization, IM/CustomerMember isolation, exact fixed Parser "
        "node locator, License/document revoke and result-hash drift fail closed; no Provider I/O"
    )


def main() -> None:
    helper = load_helper(
        "ai-04-a06-p04-p04-a06-windows-composition", "p07_composition_helper",
    )
    helper.main(
        after_validation=validate,
        output_schema_ref="gap-output.v2", schema_version=2,
    )


if __name__ == "__main__":
    main()
