"""Document Owner provenance projection; current authority belongs to caller UOW."""
from plm_assistant.modules.jobs.application.authorized_read import JobReadFacts, JobOwnerProjection, JobReadError
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding, ParseJobRef
from .parse_job_source import CommittedParseDocumentSource, DocumentParseSourceError


class DocumentParseJobReadProjection:
    def __init__(self, *, queue, sources, results=None):
        if queue is None or sources is None:
            raise ValueError('Actual Jobs and Document source Ports required')
        self._queue, self._sources = queue, sources
        self._results = results

    def project(self, tx, *, facts, actor_id, project_role):
        try:
            if type(facts) is not JobReadFacts:
                raise JobReadError()
            facts.__post_init__()
            if (facts.owner_module, facts.job_type) != ('document', 'DOCUMENT_PARSE'):
                raise JobReadError('RESOURCE_NOT_FOUND')
            binding = self._queue.peek_parse_for_job(tx, job_id=facts.job_id)
            if binding is None:
                raise JobReadError('RESOURCE_NOT_FOUND')
            if type(binding) is not ParseJobBinding:
                raise JobReadError()
            binding.__post_init__()
            request = binding.request
            if (binding.refs.job_id, request.scope, request.project_id, request.actor_id) != (
                facts.job_id, facts.scope, facts.project_id, facts.actor_id
            ):
                raise JobReadError()
            source = self._sources.read(tx, request=request)
            if type(source) is not CommittedParseDocumentSource or source.request != request:
                raise JobReadError()
            source.__post_init__()
            # Lock original Document sources before the complete Jobs/Outbox pair.
            refs = self._queue.find_parse(tx, request=request)
            if type(refs) is not ParseJobRef or refs != binding.refs:
                raise JobReadError()
            if facts.state == 'SUCCEEDED':
                if self._results is None: raise JobReadError()
                from .parse_job_result import ParseJobResultSource
                result = self._results.read(tx, facts=facts, source=source)
                if type(result) is not ParseJobResultSource: raise JobReadError()
                result.__post_init__()
                if (result.job_id, result.document_version_id, result.scope, result.project_id) != (
                    facts.job_id, request.document_version_id, facts.scope, facts.project_id): raise JobReadError()
                return JobOwnerProjection(facts.job_id, False, 'DOCUMENT_PARSE', result.parse_record_id)
            return JobOwnerProjection(facts.job_id, False)
        except JobReadError:
            raise
        except DocumentParseSourceError as exc:
            raise JobReadError('RESOURCE_NOT_FOUND' if exc.code == 'RESOURCE_NOT_FOUND' else 'JOB_UNAVAILABLE') from None
        except Exception:
            raise JobReadError() from None
