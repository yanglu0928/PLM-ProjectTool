import unittest
from datetime import datetime,timezone
from uuid import uuid4
from plm_assistant.modules.auth.infrastructure.password_reset_access import SqlAlchemyPasswordResetAccess,PasswordResetAccessError


class PasswordResetAccessTests(unittest.TestCase):
    def test_required_verifier(self):
        with self.assertRaises(ValueError):SqlAlchemyPasswordResetAccess(verifier=None)

    def test_invalid_inputs_no_auth_or_final(self):
        access=SqlAlchemyPasswordResetAccess(verifier=object());now=datetime.now(timezone.utc)
        self.assertIsNone(access.prove(None,session_token=b'bad',csrf_token=b'c'*32,now=now))
        for expected in (True,-1,9223372036854775807):
            self.assertFalse(access.require_self_reset(None,proof=None,result=None,session_token=b't'*32,
                csrf_token=b'c'*32,trace_id=uuid4(),expected_version=expected,now=now))
        self.assertFalse(access.require_self_reset(None,proof=None,result=None,session_token=b't'*32,
            csrf_token=b'c'*32,trace_id=uuid4(),expected_version=0,now=now))

    def test_missing_source_fixed_failure_no_private_exception(self):
        with self.assertRaises(PasswordResetAccessError) as caught:
            SqlAlchemyPasswordResetAccess(verifier=object()).prove(None,session_token=b't'*32,csrf_token=b'c'*32,
                now=datetime.now(timezone.utc))
        self.assertEqual(str(caught.exception),'AUTH_PASSWORD_RESET_ACCESS_UNAVAILABLE')
