"""Disposable Win11 Edge/PG18 proof for GLOBAL Reference revision."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_multisource_fixture",
    ROOT / "validation/sol-01-a04-p08-p05-p03-global-multisource-browser/serve.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def main() -> None:
    clear = bytearray(base.base.PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)

    def on_preview(**kwargs) -> None:
        document, version, evidence = base.second_source(
            port=kwargs["port"], scratch=kwargs["scratch"], actor=kwargs["actor"])
        with psycopg.connect(host="127.0.0.1", port=kwargs["port"], user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            outsider = db.execute(
                "INSERT INTO plm.auth_users(username_display,username_normalized) "
                "VALUES ('Reference Reader','reference reader') RETURNING user_id"
            ).fetchone()[0]
            password = db.execute(
                "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
                "password_hash,algorithm_id,parameter_set) VALUES "
                "(%s,1,%s,%s,%s) RETURNING password_credential_id",
                (outsider, credential.password_hash, credential.algorithm_id,
                 Jsonb(credential.parameter_set)),
            ).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET credential_version=1,"
                       "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                       (password, outsider))
        base.base.on_preview(
            **kwargs,
            browser_script=Path(__file__).with_name("run-edge-browser.mjs"),
            browser_extra=(document, version, evidence),
            include_reference_create=True, include_reference_read=True,
            include_reference_revise=True,
        )
        with psycopg.connect(host="127.0.0.1", port=kwargs["port"], user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            row = db.execute(
                "SELECT r.reference_solution_id,r.lock_version,v.version_no,"
                "v.declared_document_count,v.declared_evidence_count "
                "FROM plm.sol_reference_solutions r JOIN plm.sol_reference_versions v "
                "ON v.reference_version_id=r.current_version_ref "
                "WHERE r.name='Synthetic GLOBAL revise root'"
            ).fetchone()
            assert row is not None and row[1:] == (1, 2, 2, 2), row
            assert db.execute(
                "SELECT count(*) FROM plm.sol_reference_versions "
                "WHERE reference_solution_id=%s", (row[0],)
            ).fetchone()[0] == 2
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_REVISED' "
                "AND target_object_id=%s", (row[0],)
            ).fetchone()[0] == 1
        print("SOL_01_A13_P03_GLOBAL_REVISE_EDGE_PG_PASS")

    base.base.fixture.main(on_preview=on_preview, login_credential=credential)


if __name__ == "__main__":
    main()
