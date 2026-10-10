"""Disposable Win11 Edge/PG18 GLOBAL Reference eligibility UI proof."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_browser_base",
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

    def on_preview(**facts) -> None:
        base.on_preview(
            **facts,
            browser_script=ROOT / "validation/sol-01-a15-p02-global-document-only-browser/run-edge-browser.mjs",
            browser_extra=("eligibility",),
            include_reference_create=True, include_reference_read=True,
            include_reference_revise=True, include_reference_eligibility=True,
            include_document_read=True,
        )
        with psycopg.connect(host="127.0.0.1", port=facts["port"], user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            root = db.execute(
                "SELECT reference_solution_id,eligibility_state,lock_version "
                "FROM plm.sol_reference_solutions "
                "WHERE name='Synthetic Document only reference'"
            ).fetchone()
            assert root is not None and root[1:] == ("RESTRICTED", 3), root
            assert db.execute(
                "SELECT count(*) FROM plm.sol_reference_eligibility_events "
                "WHERE reference_solution_id=%s", (root[0],)).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events "
                "WHERE action='SOL_REFERENCE_ELIGIBILITY_SET' AND target_object_id=%s",
                (root[0],)).fetchone()[0] == 2
        print("SOL_01_A16_P06_P03_GLOBAL_ELIGIBILITY_EDGE_PG_PASS")

    base.fixture.main(on_preview=on_preview, login_credential=credential)


if __name__ == "__main__":
    main()
