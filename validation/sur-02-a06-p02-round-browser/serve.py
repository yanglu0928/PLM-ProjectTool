"""Approved-Survey wrapper around the owned Windows browser fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "validation/sur-01-a06-a05-p02-windows-browser/serve.py"
spec = importlib.util.spec_from_file_location("sur_round_browser_base", PATH)
assert spec is not None and spec.loader is not None
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original = base.schema.insert_valid


def insert_approved(db, ids, *, name="Round browser approved survey"):
    survey, version = original(db, ids, name=name)
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute("UPDATE plm.srv_survey_versions SET version_state='APPROVED' "
                   "WHERE survey_version_id=%s", (version,))
        db.execute("UPDATE plm.srv_surveys SET current_approved_version_ref=%s "
                   "WHERE survey_id=%s", (version, survey))
    return survey, version


base.schema.insert_valid = insert_approved

if __name__ == "__main__":
    base.main()
