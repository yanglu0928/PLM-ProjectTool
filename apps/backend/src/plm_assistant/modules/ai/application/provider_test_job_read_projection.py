"""Provider Test Job Owner projection: safe historical reference only."""

from __future__ import annotations

from plm_assistant.modules.jobs.application.authorized_read import (
    JobOwnerProjection, JobReadError, JobReadFacts,
)


class ProviderTestJobReadProjection:
    def __init__(self, *, repository: object) -> None:
        if repository is None or not callable(getattr(repository, "result_id", None)):
            raise ValueError("Provider Test result proof repository required")
        self._repository = repository

    def project(self, tx: object, *, facts: JobReadFacts, actor_id: object,
                project_role: str | None) -> JobOwnerProjection:
        if type(facts) is not JobReadFacts:
            raise JobReadError()
        facts.__post_init__()
        if (facts.owner_module, facts.job_type) != ("ai", "AI_PROVIDER_TEST"):
            raise JobReadError("RESOURCE_NOT_FOUND")
        if (facts.scope != "DEPLOYMENT" or facts.project_id is not None
                or facts.actor_id is None or project_role is not None):
            raise JobReadError()
        result_id = self._repository.result_id(tx, facts=facts)
        if result_id is None:
            return JobOwnerProjection(facts.job_id, False)
        if facts.state != "SUCCEEDED":
            raise JobReadError()
        return JobOwnerProjection(facts.job_id, False, "AI_PROVIDER_TEST", result_id)
