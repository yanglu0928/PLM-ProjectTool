"""AI Task Job projection exposes retry eligibility without task content."""

from __future__ import annotations

from plm_assistant.modules.jobs.application.authorized_read import (
    JobOwnerProjection,
    JobReadError,
    JobReadFacts,
)


class AITaskJobReadProjection:
    def __init__(self, *, repository: object) -> None:
        if repository is None or not callable(getattr(repository, "retryable", None)):
            raise ValueError("AI Task Job read proof repository required")
        self._repository = repository

    def project(self, tx: object, *, facts: JobReadFacts, actor_id: object,
                project_role: str | None) -> JobOwnerProjection:
        if type(facts) is not JobReadFacts:
            raise JobReadError()
        facts.__post_init__()
        if ((facts.owner_module, facts.job_type) != ("ai", "AI_TASK_EXECUTE")
                or facts.scope != "PROJECT" or facts.project_id is None
                or project_role is None):
            raise JobReadError("RESOURCE_NOT_FOUND")
        return JobOwnerProjection(
            facts.job_id, self._repository.retryable(tx, facts=facts),
        )
