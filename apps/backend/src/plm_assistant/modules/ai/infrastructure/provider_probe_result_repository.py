"""Append-only safe Provider probe result in caller's PostgreSQL transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from plm_assistant.modules.ai.application.provider_test_preflight import ProviderTestPreflightSnapshot
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderProbeResultRow
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class SqlAlchemyProviderProbeResultRepository:
    def append_success(self, transaction: object, *,
                       snapshot: ProviderTestPreflightSnapshot) -> uuid.UUID:
        if type(snapshot) is not ProviderTestPreflightSnapshot:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        session = SqlAlchemyJobLeaseRepository._session(transaction)
        connection = session.connection()
        if (connection.dialect.name != "postgresql"
                or connection.get_isolation_level() != "READ COMMITTED"):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        claim, plan = snapshot.claim, snapshot.plan
        if (claim.provider_id != plan.provider_id
                or claim.config_version != plan.config_version
                or claim.probe_id != plan.probe_id):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        observed = session.execute(select(func.clock_timestamp())).scalar_one()
        result_id = uuid.UUID(new_uuid7())
        session.add(AIProviderProbeResultRow(
            probe_result_id=result_id, ai_provider_id=claim.provider_id,
            provider_config_version_id=claim.config_id,
            secret_record_id=plan.secret_ref,
            secret_version_id=claim.secret_version_id,
            job_id=claim.job_id, probe_id=claim.probe_id,
            policy_sha256=claim.policy_sha256,
            outcome="SUCCEEDED", failure_code=None,
            attempt_no=claim.attempt_no, fencing_token=claim.fencing_token,
            observed_at=observed,
        ))
        session.flush()
        return result_id
