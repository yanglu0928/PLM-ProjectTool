"""Parser-owned input Port that rechecks current authority in the caller's UOW."""

from __future__ import annotations

from plm_assistant.modules.document.application.parse_job_source import DocumentParseInputSource

from .current_authority import ParserAuthorityError


class AuthorizedParserInputSource:
    def __init__(self, *, source, authority):
        if source is None or authority is None:
            raise ValueError("Parser source and current authority required")
        self._source, self._authority = source, authority

    def read_input(self, tx, *, request) -> DocumentParseInputSource:
        self._authority.assert_current(tx, request=request)
        result = self._source.read_input(tx, request=request)
        if type(result) is not DocumentParseInputSource or result.committed.request != request:
            raise ParserAuthorityError("PARSER_INPUT_UNAVAILABLE")
        result.__post_init__()
        return result
