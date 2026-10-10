"""Disposable Edge/PG GLOBAL Reference Create→read→source-location proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_multisource_browser",
    ROOT / "validation/sol-01-a04-p08-p05-p03-global-multisource-browser/serve.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def on_preview(**kwargs) -> None:
    document, version, evidence = base.second_source(
        port=kwargs["port"], scratch=kwargs["scratch"], actor=kwargs["actor"])
    base.base.on_preview(
        **kwargs,
        browser_script=ROOT / "validation/sol-01-a04-p08-p05-p03-global-multisource-browser/run-edge-browser.mjs",
        browser_extra=(document, version, evidence, "create-read"),
        include_reference_create=True, include_reference_read=True)
    with psycopg.connect(host="127.0.0.1", port=kwargs["port"], user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        row = db.execute(
            "SELECT r.reference_solution_id,r.scope,r.project_id,r.eligibility_state,"
            "v.version_state,v.deidentification_confirmation_id,"
            "v.declared_document_count,v.declared_evidence_count "
            "FROM plm.sol_reference_solutions r JOIN plm.sol_reference_versions v "
            "USING (reference_solution_id) "
            "WHERE r.name='Synthetic multi-source reference'").fetchone()
        assert row is not None and row[1:5] == (
            "GLOBAL", None, "REFERENCE_ONLY", "DRAFT")
        assert row[5] is not None and row[6:] == (2, 2)
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_REFERENCE_CREATED'").fetchone()[0] == 1


def main() -> None:
    clear = bytearray(base.base.PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    base.base.fixture.main(on_preview=on_preview, login_credential=credential)
    print("SOL_01_A04_P09_P05_P04_GLOBAL_REFERENCE_EDGE_PG_PASS")


if __name__ == "__main__":
    main()
