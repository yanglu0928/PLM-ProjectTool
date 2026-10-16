"""Disposable PG18 Auth/CSRF confirmation and revocation integration.

Document/Evidence and License remain synthetic; this does not assert complete
Reference admission or actual human deidentification.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmError,
    ReferenceDeidentificationConfirmService,
)
from plm_assistant.modules.solution.application.prove_reference_deidentification import (
    ReferenceDeidentificationProofService,
)
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeError, ReferenceDeidentificationRevokeService,
    RevokeReferenceDeidentification,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_proof_repository import (
    SqlAlchemyReferenceDeidentificationProofRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_repository import (
    SqlAlchemyReferenceDeidentificationRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_deidentification_revocation_repository import (
    SqlAlchemyReferenceDeidentificationRevocationRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "prior_revoke_owner", ROOT / "validation/sol-01-a04-p02-p03-p03-p02-revoke-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
source = prior.source
TOKEN, CSRF = b"a" * 32, b"c" * 32


def rejects(code: str, action) -> None:
    try:
        action()
    except (ReferenceDeidentificationConfirmError, ReferenceDeidentificationRevokeError) as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError("expected " + code)


def verify(port: int) -> None:
    prior.verify(port)
    url = URL.create("postgresql+psycopg", username="poc_admin",
                     host="127.0.0.1", port=port, database="postgres")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        actor = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized='section version actor'"
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
            "password_hash,algorithm_id,parameter_set) VALUES "
            "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
            "RETURNING password_credential_id", (actor,),
        ).fetchone()[0]
        db.execute("UPDATE plm.auth_users SET credential_version=1,"
                   "active_password_credential_id=%s,state='ENABLED',"
                   "deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",
                   (credential, actor))
        session_id = db.execute(
            "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
            "credential_version,idle_expires_at,absolute_expires_at) "
            "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
            "statement_timestamp()+interval '2 hours') RETURNING session_id",
            (hashlib.sha256(TOKEN).digest(), hashlib.sha256(CSRF).digest(), actor),
        ).fetchone()[0]
    engine = create_engine(url)
    try:
        runtime = DatabaseRuntime(engine)
        sources = prior.prior._Sources(uuid.uuid4())
        audit = AuditService(SqlAlchemyAuditRepository())
        receipts = SqlAlchemyIdempotencyReceipts()
        access = SqlAlchemyLicenseImportAccess()
        read_access = SqlAlchemyDeploymentReadAccess()
        confirm = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=prior.prior._License(), sources=sources,
            repository=SqlAlchemyReferenceDeidentificationRepository(),
            receipts=receipts, audit=audit, clock=lambda: datetime.now(timezone.utc),
        )
        revoke = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=prior.prior._License(),
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=receipts, audit=audit, clock=lambda: datetime.now(timezone.utc),
        )
        read = ReferenceDeidentificationProofService(
            admins=read_access,
            confirmations=SqlAlchemyReferenceDeidentificationProofRepository(),
            clock=lambda: datetime.now(timezone.utc),
        )
        request = ReferenceSourceRequest(
            TOKEN, uuid.uuid4(), "GLOBAL", None, (sources.version,), (),
            "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
        )
        command = ConfirmReferenceDeidentification(
            request, CSRF, datetime.now(timezone.utc) + timedelta(days=1),
            "I_VERIFIED_DEIDENTIFICATION", "A" * 16,
        )
        rejects("AUTH_ACCESS_DENIED", lambda: confirm.confirm(
            ConfirmReferenceDeidentification(
                request, b"w" * 32, command.expires_at,
                command.attestation_statement, "B" * 16)))
        first = confirm.confirm(command)
        assert first.confirmed_by == actor
        args = dict(session_token=TOKEN, trace_id=request.trace_id,
                    source_fingerprint=first.source_fingerprint,
                    source_project_class="PLM", deidentification_class="DEIDENTIFIED",
                    applicability={"industry": "synthetic"})
        with runtime.unit_of_work() as tx:
            proof = read.prove(tx, **args)
            assert proof is not None and proof.confirmation_id == first.confirmation_id
        revoke_command = RevokeReferenceDeidentification(
            first.confirmation_id, TOKEN, CSRF, uuid.uuid4(), "ADMIN_REVIEW", "R" * 16)
        rejects("AUTH_ACCESS_DENIED", lambda: revoke.revoke(
            RevokeReferenceDeidentification(
                first.confirmation_id, TOKEN, b"w" * 32, uuid.uuid4(),
                "ADMIN_REVIEW", "W" * 16)))
        revoked = revoke.revoke(revoke_command)
        assert revoked.confirmation_id == first.confirmation_id
        with runtime.unit_of_work() as tx:
            assert read.prove(tx, **args) is None
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            db.execute("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(),"
                       "revoke_reason='ADMIN_REVOKED',lock_version=lock_version+1 "
                       "WHERE session_id=%s", (session_id,))
        rejects("AUTH_ACCESS_DENIED", lambda: confirm.confirm(
            ConfirmReferenceDeidentification(
                request, CSRF, datetime.now(timezone.utc) + timedelta(days=1),
                "I_VERIFIED_DEIDENTIFICATION", "N" * 16)))
        rejects("AUTH_ACCESS_DENIED", lambda: revoke.revoke(revoke_command))
        with runtime.unit_of_work() as tx:
            assert read.prove(tx, **args) is None
    finally:
        engine.dispose()
    print("SOL_01_A04_P02_P03_P03_P03_P01_AUTH_PG_PASS: real Session/CSRF/role "
          "confirm, proof and revoke; wrong CSRF and revoked Session denied")


def main() -> None:
    scratch = Path(tempfile.mkdtemp(prefix="plm-sol-auth-confirm-pg-"))
    if not str(scratch).isascii():
        raise RuntimeError("ASCII temporary PostgreSQL path required")
    install = scratch / "pgsql"
    for name in ("bin", "lib", "share"):
        shutil.copytree(source.PG_SOURCE / name, install / name)
    shutil.copy2(source.VECTOR_SOURCE / "vector.dll", install / "lib/vector.dll")
    shutil.copy2(source.VECTOR_SOURCE / "vector.control", install / "share/extension/vector.control")
    for path in (source.VECTOR_SOURCE / "sql").glob("vector--*.sql"):
        shutil.copy2(path, install / "share/extension" / path.name)
    binary, data = install / "bin", scratch / "data"
    port = source.free_port()
    started = False
    try:
        source.run(str(binary / "initdb.exe"), "-D", str(data), "-U", "poc_admin",
                   "-A", "trust", "--no-locale", "-E", "UTF8")
        source.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-l", str(scratch / "postgres.log"),
                   "-o", f"-h 127.0.0.1 -p {port}", "-w", "start", detached=True)
        started = True
        verify(port)
    finally:
        if started:
            source.run(str(binary / "pg_ctl.exe"), "-D", str(data), "-m", "fast", "-w", "stop")
        status = subprocess.run([str(binary / "pg_ctl.exe"), "-D", str(data), "status"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if status.returncode == 0:
            raise RuntimeError(f"isolated PostgreSQL remains running; data preserved at {scratch}")
        if (scratch.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
                and scratch.name.startswith("plm-sol-auth-confirm-pg-")):
            shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
