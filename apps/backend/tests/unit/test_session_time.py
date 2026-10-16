import unittest
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.auth.api.session_time import utc_session_instant


class SessionTimeTests(unittest.TestCase):
    def test_session_expiry_wire_format_preserves_instant(self):
        instant = datetime(2030, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
        for offset in (timezone.utc, timezone(timedelta(hours=8)), timezone(-timedelta(hours=4))):
            with self.subTest(offset=offset):
                self.assertEqual(utc_session_instant(instant.astimezone(offset)),
                                 "2030-01-02T03:04:05.123456Z")

    def test_session_expiry_wire_format_rejects_naive_or_wrong_type(self):
        for value in (datetime(2030, 1, 2), "2030-01-02T03:04:05Z", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "aware session instant required"):
                    utc_session_instant(value)


if __name__ == "__main__":
    unittest.main()
