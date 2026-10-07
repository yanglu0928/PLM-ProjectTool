"""Approved-Survey browser fixture with an eligible Conclusion reviewer."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from unittest.mock import patch

from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "validation/sur-03-a09-assignment-browser/serve.py"
spec = importlib.util.spec_from_file_location("sur_conclusion_browser_base", PATH)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

schema = base.base.base.schema
original_seed = schema.seed_dependencies


def seed_with_reviewer(db):
    ids = original_seed(db)
    reviewer = uuid.uuid4()
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("""
            INSERT INTO plm.auth_users(
              user_id,username_display,username_normalized,deployment_role)
            VALUES (%s,'Conclusion customer reviewer',
              'conclusion-customer-reviewer','NONE')
        """, (reviewer,))
        credential = db.execute("""
            INSERT INTO plm.auth_password_credentials(
              user_id,credential_version,password_hash,algorithm_id,parameter_set)
            VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb)
            RETURNING password_credential_id
        """, (reviewer,)).fetchone()[0]
        db.execute("""
            UPDATE plm.auth_users SET credential_version=1,
              active_password_credential_id=%s,state='ENABLED'
            WHERE user_id=%s
        """, (credential, reviewer))
        db.execute("""
            INSERT INTO plm.prj_project_members(
              project_id,user_id,department_id,project_role)
            VALUES (%s,%s,%s,'CUSTOMER_MANAGER')
        """, (ids["project"], reviewer, ids["department"]))
    ids["reviewer"] = reviewer
    return ids


schema.seed_dependencies = seed_with_reviewer

if __name__ == "__main__":
    with patch(
        "plm_assistant.entrypoints.production_login.create_windows_evidence_list_cursor_codec",
        return_value=EvidenceListCursorCodec(b"e" * 32),
    ):
        base.base.base.main()
