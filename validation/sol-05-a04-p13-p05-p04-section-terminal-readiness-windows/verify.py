"""Disposable Win11/PG18 terminal Section current-proof regression."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

import psycopg

from plm_assistant.entrypoints.windows_solution_outline import (
    _windows_section_current_validator,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.solution.application.section_review_readiness import (
    SectionReviewReadinessError, SectionReviewReadinessService,
)
from plm_assistant.modules.solution.application.section_version_validation_contract import (
    SectionCurrentFactQuery,
)
from plm_assistant.modules.solution.infrastructure.section_review_readiness_repository import (
    SqlAlchemySectionReviewReadinessRepository,
)
from plm_assistant.modules.trace.application.revoke_link import RevokeTraceLink


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_submit_windows",
    ROOT / "validation/sol-05-a04-p13-p05-p03-section-review-submit-windows/verify.py")
assert SPEC and SPEC.loader
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)


def _after_submit(**context):
    previous._after_submit(**context)
    project = context["project"]
    runtime = context["runtime"]
    connection = dict(host="127.0.0.1", port=context["port"],
                      user="poc_admin", dbname="postgres")
    with psycopg.connect(**connection) as db:
        section, version = db.execute(
            "SELECT solution_section_id,solution_section_version_id "
            "FROM plm.sol_section_versions WHERE project_id=%s "
            "AND version_state='IN_REVIEW' ORDER BY version_no DESC LIMIT 1",
            (project,)).fetchone()
        edge = db.execute(
            "SELECT trace_link_id FROM plm.trc_links WHERE project_id=%s "
            "AND target_object_id=%s AND target_version_id=%s "
            "AND link_state='ACTIVE' AND relation_type='IMPLEMENTS'",
            (project, section, version)).fetchone()[0]
    authorization = ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())
    readiness = SectionReviewReadinessService(
        repository=SqlAlchemySectionReviewReadinessRepository(),
        current=_windows_section_current_validator(
            runtime=runtime, license_guard=context["license_guard"],
            authorization=authorization, documents=context["documents"],
            downloads=context["downloads"],
            parse_results=context["parse_results"]))
    query = SectionCurrentFactQuery(
        context["token"], uuid.uuid4(), project, section, version)
    with runtime.unit_of_work() as tx:
        proof = readiness.prove(tx, query=query, required_state="IN_REVIEW")
        assert proof.version.version_state == "IN_REVIEW"
        assert proof.required_state == "IN_REVIEW"
        assert all(getattr(proof.facts, name) == "PASS" for name in (
            "integrity", "content", "requirements", "evidence", "trace", "spec"))
        try:
            readiness.prove(tx, query=query)
        except SectionReviewReadinessError:
            pass
        else:
            raise AssertionError("DRAFT submit proof accepted IN_REVIEW")
    _, revoker = previous._trace_services(
        runtime=runtime, license_guard=context["license_guard"],
        audit=context["audit"])
    revoker.revoke(RevokeTraceLink(
        context["token"], context["csrf"], uuid.uuid4(), project,
        edge, 0), idempotency_key="terminal-readiness-revoke-0001")
    with runtime.unit_of_work() as tx:
        try:
            readiness.prove(tx, query=query, required_state="IN_REVIEW")
        except SectionReviewReadinessError:
            pass
        else:
            raise AssertionError("revoked Trace accepted at terminal")
    print("SOL_05_A04_P13_P05_P04_SECTION_TERMINAL_READINESS_WINDOWS_PASS")


if __name__ == "__main__":
    fixture = previous.prior.fixture
    fixture._after_submit = _after_submit
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
