"""Prototype browser fixture on isolated PostgreSQL 18 and production Windows composition."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "validation/req-01-a11-a05-windows-browser/serve.py"
spec = importlib.util.spec_from_file_location("prt_browser_base", PATH)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

schema = base.schema
original_seed = schema.seed_dependencies


def seed_with_prototype_inputs(db):
    """Add only the fixed approved Requirement needed by the Prototype UI."""
    ids = original_seed(db)
    requirement_version = uuid.uuid4()
    criteria = (uuid.uuid4(), uuid.uuid4())
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            """INSERT INTO plm.req_requirement_versions(
              requirement_version_id,requirement_id,project_id,version_no,
              version_state,statement,rationale,domain_name,priority,risk,
              requirement_classification,content_fingerprint,
              declared_source_count,declared_acceptance_count,
              declared_capability_count,declared_assumption_count,
              declared_exclusion_count,declared_dependency_count,
              declared_ai_task_count,review_ref,review_round_ref,created_by)
              VALUES (%s,%s,%s,1,'APPROVED',
              '项目应形成可追溯的受控原型评审记录',
              '隔离浏览器验收需要一个真实的当前批准需求','PLM','HIGH','LOW',
              'STANDARD_FUNCTION',%s,1,2,0,0,0,0,0,%s,%s,%s)""",
            (
                requirement_version,
                ids["requirement"],
                ids["project"],
                b"p" * 32,
                uuid.uuid4(),
                uuid.uuid4(),
                ids["actor"],
            ),
        )
        db.execute(
            """INSERT INTO plm.req_sources(
              requirement_version_id,requirement_id,project_id,ordinal,
              source_type,source_object_id)
              VALUES (%s,%s,%s,0,'HUMAN_DECISION',%s)""",
            (
                requirement_version,
                ids["requirement"],
                ids["project"],
                uuid.uuid4(),
            ),
        )
        for ordinal, criterion in enumerate(criteria):
            db.execute(
                """INSERT INTO plm.req_acceptance_criteria(
                  acceptance_criterion_id,requirement_version_id,requirement_id,
                  project_id,ordinal,observable_result,verification_method,
                  required_data,required_environment,evidence_requirement)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    criterion,
                    requirement_version,
                    ids["requirement"],
                    ids["project"],
                    ordinal,
                    "原型版本可固定输入并进入正式评审" if ordinal == 0
                    else "需求覆盖页不得把送审回执显示为批准",
                    "真实 Edge 与生产 HTTP 验证",
                    "隔离合成项目数据",
                    "Windows 11 + PostgreSQL 18",
                    "HTTP 状态、固定版本与审计记录",
                ),
            )
        db.execute(
            """UPDATE plm.req_requirements
               SET current_approved_version_ref=%s
               WHERE requirement_id=%s""",
            (requirement_version, ids["requirement"]),
        )
        db.execute(
            """UPDATE plm.doc_documents
               SET latest_version_ref=%s,effective_version_ref=%s
               WHERE document_id=%s""",
            (
                ids["record_version"],
                ids["record_version"],
                ids["record_document"],
            ),
        )
    ids["requirement_version"] = requirement_version
    ids["acceptance_criteria"] = criteria
    return ids


schema.seed_dependencies = seed_with_prototype_inputs


if __name__ == "__main__":
    keys = base.base.base.base.base.Keys()
    with (
        patch(
            "plm_assistant.entrypoints.production_login.create_windows_evidence_list_cursor_codec",
            return_value=EvidenceListCursorCodec(b"e" * 32),
        ),
        patch(
            "plm_assistant.entrypoints.windows_requirement.WindowsSecretKeyProvider",
            return_value=keys,
        ),
        patch(
            "plm_assistant.entrypoints.windows_prototype_cursor.WindowsSecretKeyProvider",
            return_value=keys,
        ),
    ):
        base.base.base.base.base.main()
