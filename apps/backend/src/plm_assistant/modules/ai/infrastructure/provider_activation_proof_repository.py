"""Latest final probe proof, rechecked against the original Job/Outbox pair."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.ai.application.provider_activation_proof import (
    LatestProviderProbe, ProviderActivationProofError,
)
from plm_assistant.modules.ai.infrastructure.provider_orm import AIProviderProbeResultRow
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.ai.infrastructure.provider_test_job_read import SqlAlchemyProviderTestJobReadRepository
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts


class SqlAlchemyProviderActivationProofRepository:
    def __init__(self) -> None:
        self._jobs = SqlAlchemyJobReadRepository()
        self._proofs = SqlAlchemyProviderTestJobReadRepository()

    def latest_success(self, transaction: object, *, provider_id: uuid.UUID) -> LatestProviderProbe | None:
        if type(provider_id) is not uuid.UUID or not provider_id.int:
            raise ProviderActivationProofError("VALIDATION_FAILED")
        session = self._proofs._snapshots._leases._session(transaction)
        connection = session.connection()
        if connection.dialect.name != "postgresql" or connection.get_isolation_level() != "READ COMMITTED":
            raise ProviderActivationProofError()
        row = session.scalar(select(AIProviderProbeResultRow).where(
            AIProviderProbeResultRow.ai_provider_id == provider_id,
        ).order_by(AIProviderProbeResultRow.observed_at.desc(),
                   AIProviderProbeResultRow.probe_result_id.desc()).limit(1))
        if row is None or row.outcome != "SUCCEEDED":
            return None
        facts = self._jobs.get(transaction, job_id=row.job_id)
        if (type(facts) is not JobReadFacts or facts.state != "SUCCEEDED"
                or (facts.owner_module, facts.job_type, facts.scope, facts.project_id) != (
                    "ai", "AI_PROVIDER_TEST", "DEPLOYMENT", None)
                or self._proofs.result_id(transaction, facts=facts) != row.probe_result_id):
            raise ProviderActivationProofError()
        return LatestProviderProbe(row.ai_provider_id, row.provider_config_version_id,
                                   row.secret_version_id, row.job_id,
                                   row.probe_result_id, bytes(row.policy_sha256))
