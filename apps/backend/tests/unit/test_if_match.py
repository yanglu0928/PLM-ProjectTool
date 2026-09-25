from __future__ import annotations

import unittest

from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


class IfMatchTests(unittest.TestCase):
    def test_canonical_strong_etag_maps_to_record_version(self) -> None:
        self.assertEqual(parse_if_match(((b"If-Match", b'"v1"'),)), 1)
        self.assertEqual(parse_if_match(((b"if-match", b'"v9223372036854775806"'),)),
                         9_223_372_036_854_775_806)

    def test_missing_is_required_precondition(self) -> None:
        with self.assertRaises(ApplicationError) as caught:
            parse_if_match(())
        self.assertEqual(caught.exception.spec.code, "CONFLICT_VERSION_REQUIRED")
        self.assertEqual(caught.exception.spec.status_code, 428)

    def test_noncanonical_weak_multiple_and_oversized_rejected(self) -> None:
        bad_values = (
            b'W/"v1"', b'*', b'"v0"', b'"v01"', b'"v1", "v2"', b'v1',
            b'"v-1"', b'"v1" ', b'"V1"', b'"v9223372036854775807"',
            b'"v9999999999999999999999999999"', b'"v1"\x00',
        )
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(ApplicationError) as caught:
                parse_if_match(((b"if-match", value),))
            self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")
        with self.assertRaises(ApplicationError) as caught:
            parse_if_match(((b"if-match", b'"v1"'), (b"If-Match", b'"v1"')))
        self.assertEqual(caught.exception.spec.code, "REQUEST_MALFORMED")


if __name__ == "__main__":
    unittest.main()
