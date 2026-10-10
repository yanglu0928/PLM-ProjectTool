"""Disposable Win11 Edge/PG18 document-only GLOBAL Reference proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_attestation_fixture",
    ROOT / "validation/sol-01-a04-p08-p04-p03-global-attestation-browser/serve.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def main() -> None:
    clear = bytearray(base.PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)

    def on_preview(**kwargs) -> None:
        base.on_preview(
            **kwargs,
            browser_script=Path(__file__).with_name("run-edge-browser.mjs"),
            include_reference_create=True, include_reference_read=True,
            include_reference_revise=True, include_document_read=True,
        )
        with psycopg.connect(host="127.0.0.1", port=kwargs["port"], user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            root = db.execute(
                "SELECT reference_solution_id,lock_version FROM plm.sol_reference_solutions "
                "WHERE name='Synthetic Document only reference'"
            ).fetchone()
            assert root is not None and root[1] == 1, root
            rows = db.execute(
                "SELECT version_no,declared_document_count,declared_evidence_count,"
                "deidentification_confirmation_id FROM plm.sol_reference_versions "
                "WHERE reference_solution_id=%s ORDER BY version_no", (root[0],)
            ).fetchall()
            assert len(rows) == 2 and [(r[0], r[1], r[2]) for r in rows] == [
                (1, 1, 0), (2, 1, 0)], rows
            assert rows[0][3] is not None and rows[1][3] is not None
            assert rows[0][3] != rows[1][3]
            for action in ("SOL_REFERENCE_CREATED", "SOL_REFERENCE_REVISED"):
                assert db.execute(
                    "SELECT count(*) FROM plm.aud_events WHERE action=%s "
                    "AND target_object_id=%s", (action, root[0]),
                ).fetchone()[0] == 1
        print("SOL_01_A15_P02_GLOBAL_DOCUMENT_ONLY_EDGE_PG_PASS")

    base.fixture.main(on_preview=on_preview, login_credential=credential)


if __name__ == "__main__":
    main()
