from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.parser.application.authorized_source import (
    AuthorizedParserInputSource,
)
from plm_assistant.modules.parser.application.current_authority import ParserAuthorityError


class AuthorizedParserInputSourceTests(unittest.TestCase):
    def test_denial_never_reads_file_source(self):
        source, authority = Mock(), SimpleNamespace(assert_current=Mock())
        authority.assert_current.side_effect = ParserAuthorityError("RESOURCE_NOT_FOUND")
        wrapped = AuthorizedParserInputSource(source=source, authority=authority)
        tx, request = object(), object()
        with self.assertRaises(ParserAuthorityError):
            wrapped.read_input(tx, request=request)
        authority.assert_current.assert_called_once_with(tx, request=request)
        source.read_input.assert_not_called()


if __name__ == "__main__":
    unittest.main()
