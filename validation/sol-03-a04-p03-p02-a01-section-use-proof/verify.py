"""Disposable PG proof for stable Section identity in OutlineVersion input."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.application.create_outline import CreateOutline, OutlineCreateService
from plm_assistant.modules.solution.application.create_section import CreateSection, SectionCreateService
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseError, OutlineSectionUseProofService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_use_project_fixture",
    ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def denied(action):
    try:
        action()
    except OutlineSectionUseError:
        return
    raise AssertionError("invalid Section identity accepted")


def on_created(*, runtime, audit, license_guard, project, other_project,
               token, csrf, port, **_unused):
    common = dict(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectWriteAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    outline = OutlineCreateService(
        **common, repository=SqlAlchemyOutlineCreateRepository()).create(
            CreateOutline(token, csrf, uuid.uuid4(), project,
                          "Section proof parent", "section-use-outline-0001"))
    section = SectionCreateService(
        **common, repository=SqlAlchemySectionCreateRepository()).create(
            CreateSection(token, csrf, uuid.uuid4(), project,
                          outline.solution_outline_id, "Overview",
                          "section-use-section-0001"))
    proof = OutlineSectionUseProofService(sections=SqlAlchemySectionReadRepository())
    with runtime.unit_of_work() as tx:
        result = proof.prove(
            tx, project_id=project,
            outline_id=outline.solution_outline_id,
            section_id=section.solution_section_id)
        assert result.solution_section_id == section.solution_section_id
        denied(lambda: proof.prove(
            tx, project_id=other_project,
            outline_id=outline.solution_outline_id,
            section_id=section.solution_section_id))
        denied(lambda: proof.prove(
            tx, project_id=project, outline_id=uuid.uuid4(),
            section_id=section.solution_section_id))
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            try:
                db.execute(
                    "SELECT solution_section_id FROM plm.sol_sections "
                    "WHERE solution_section_id=%s FOR UPDATE NOWAIT",
                    (section.solution_section_id,))
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise AssertionError("Section proof did not retain root lock")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        db.execute("ALTER TABLE plm.sol_sections DISABLE TRIGGER trg_sol_sections__owner")
        try:
            db.execute(
                "UPDATE plm.sol_sections SET section_state='ARCHIVED', "
                "lock_version=lock_version+1 WHERE solution_section_id=%s",
                (section.solution_section_id,))
        finally:
            db.execute("ALTER TABLE plm.sol_sections ENABLE TRIGGER trg_sol_sections__owner")
    with runtime.unit_of_work() as tx:
        denied(lambda: proof.prove(
            tx, project_id=project,
            outline_id=outline.solution_outline_id,
            section_id=section.solution_section_id))
    return 0


if __name__ == "__main__":
    fixture.main(on_created=on_created)
    print("SOL_03_A04_P03_P02_A01_SECTION_USE_PROOF_PASS: real Section identity, "
          "parent/scope, archived denial and retained root lock")
