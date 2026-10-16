"""Typed Document-owned immutable parse metadata, never content/download authority."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .parse_job_source import CommittedParseDocumentSource
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobReadError


@dataclass(frozen=True, slots=True)
class ParseJobResultSource:
    parse_record_id: UUID
    job_id: UUID
    document_version_id: UUID
    scope: str
    project_id: UUID | None
    result_ref_id: UUID
    sha256: bytes
    created_at: datetime
    started_at: datetime
    completed_at: datetime
    result_created_at: datetime

    def __post_init__(self):
        if (any(type(x) is not UUID or not x.int for x in (self.parse_record_id, self.job_id, self.document_version_id, self.result_ref_id))
            or self.scope not in ('GLOBAL', 'PROJECT')
            or (self.scope == 'GLOBAL' and self.project_id is not None)
            or (self.scope == 'PROJECT' and (type(self.project_id) is not UUID or not self.project_id.int))
            or type(self.sha256) is not bytes or len(self.sha256) != 32
            or any(type(x) is not datetime or x.tzinfo is None or x.utcoffset() is None for x in (
                self.created_at, self.started_at, self.completed_at, self.result_created_at))
            or not self.created_at <= self.started_at <= self.result_created_at <= self.completed_at):
            raise JobReadError()


class DocumentParseJobResults:
    def __init__(self, *, repository):
        if repository is None: raise ValueError('Actual Document result repository required')
        self._repo = repository

    def read(self, tx, *, facts, source):
        try:
            if type(facts) is not JobReadFacts or type(source) is not CommittedParseDocumentSource:
                raise JobReadError()
            facts.__post_init__(); source.__post_init__()
            request = source.request
            if facts.state != 'SUCCEEDED' or (facts.owner_module, facts.job_type, facts.scope, facts.project_id, facts.actor_id) != (
                'document', 'DOCUMENT_PARSE', request.scope, request.project_id, request.actor_id):
                raise JobReadError()
            result = self._repo.get(tx, job_id=facts.job_id)
            if type(result) is not ParseJobResultSource: raise JobReadError()
            result.__post_init__()
            if (result.job_id, result.document_version_id, result.scope, result.project_id) != (
                facts.job_id, request.document_version_id, request.scope, request.project_id):
                raise JobReadError()
            if result.created_at < max(facts.created_at, source.version_created_at) or result.completed_at > facts.completed_at:
                raise JobReadError()
            return result
        except JobReadError: raise
        except Exception: raise JobReadError() from None
