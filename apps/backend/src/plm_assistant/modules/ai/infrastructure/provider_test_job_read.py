"""Same-transaction historical Provider Test Job/result proof, never activation authority."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.infrastructure.provider_orm import (
    AIProviderConfigVersionRow, AIProviderProbeResultRow,
)
from plm_assistant.modules.jobs.application.authorized_read import JobReadError, JobReadFacts
from plm_assistant.modules.jobs.infrastructure.ai_provider_test_claim_repository import (
    SqlAlchemyAIProviderTestClaimRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow


class SqlAlchemyProviderTestJobReadRepository:
    def __init__(self) -> None:
        self._snapshots = SqlAlchemyAIProviderTestClaimRepository()

    def result_id(self, transaction: object, *, facts: JobReadFacts) -> uuid.UUID | None:
        if type(facts) is not JobReadFacts:
            raise JobReadError()
        facts.__post_init__()
        session = self._snapshots._leases._session(transaction)
        connection = session.connection()
        if connection.dialect.name != "postgresql" or connection.get_isolation_level() != "READ COMMITTED":
            raise JobReadError()
        job = session.get(JobRow, facts.job_id)
        if job is None:
            raise JobReadError("RESOURCE_NOT_FOUND")
        if (job.owner_module, job.job_type, job.scope, job.project_id, job.actor_ref,
                job.state, job.attempt_count, job.lock_version) != (
                facts.owner_module, facts.job_type, facts.scope, facts.project_id,
                facts.actor_id, facts.state, facts.attempt_count, facts.lock_version):
            raise JobReadError()
        provider_id, config_id, config_version, secret_version_id, policy_sha256 = self._snapshots._snapshot(session, job)
        result = session.scalar(select(AIProviderProbeResultRow).where(
            AIProviderProbeResultRow.job_id == facts.job_id,
        ))
        if result is None:
            if facts.state == "SUCCEEDED":
                raise JobReadError()
            return None
        config = session.get(AIProviderConfigVersionRow, config_id)
        if (config is None or (config.ai_provider_id, config.config_version_no,
                               config.secret_ref) != (
                               provider_id, config_version, result.secret_record_id)):
            raise JobReadError()
        if ((result.job_id, result.ai_provider_id, result.provider_config_version_id,
             result.secret_version_id, result.policy_sha256, result.probe_id,
             result.attempt_no, result.fencing_token) != (
             facts.job_id, provider_id, config_id, secret_version_id, policy_sha256,
             "CHAT_CONNECTIVITY_V1", facts.attempt_count, job.fencing_token)
                or facts.state not in ("SUCCEEDED", "FAILED")
                or (facts.state == "SUCCEEDED") != (result.outcome == "SUCCEEDED")
                or (facts.state == "FAILED") != (result.outcome == "FAILED")):
            raise JobReadError()
        return result.probe_result_id if facts.state == "SUCCEEDED" else None
