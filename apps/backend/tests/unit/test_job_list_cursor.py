import base64
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from plm_assistant.modules.jobs.application.authorized_list import JobListQuery
from plm_assistant.modules.jobs.api.list_cursor import JobListCursorCodec
from plm_assistant.modules.platform.application.errors import ApplicationError


class JobCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec = JobListCursorCodec(b'k' * 32)
        self.query = JobListQuery(b's' * 32, uuid4(), uuid4(), 1)
        self.position = (datetime.now(timezone.utc), uuid4())
        self.token = self.codec.encode(query=self.query, before=self.position)

    def test_roundtrip_randomized_ciphertext_hides_coordinates(self):
        self.assertEqual(self.codec.decode(self.token, query=self.query), self.position)
        self.assertNotEqual(self.codec.encode(query=self.query, before=self.position), self.token)
        packed = base64.urlsafe_b64decode(self.token[3:] + '=' * (-len(self.token[3:]) % 4))
        for secret in (str(self.position[1]).encode(), self.position[0].isoformat().encode(), b'job_id', b'created_at'):
            self.assertNotIn(secret, packed)

    def test_current_query_binding_trace_not_permission_snapshot(self):
        self.assertEqual(self.codec.decode(self.token, query=replace(self.query, trace_id=uuid4())), self.position)
        for changes in ({'session_token': b't' * 32}, {'project_id': uuid4()}, {'page_size': 2}, {'scope': 'PROJECT'}, {'project_id': None}):
            with self.assertRaises(ApplicationError): self.codec.decode(self.token, query=replace(self.query, **changes))

    def test_tamper_family_truncation_size_and_wrong_key_refuse(self):
        altered = self.token[:5] + ('A' if self.token[5] != 'A' else 'B') + self.token[6:]
        for token in (altered, self.token + '=', self.token[1:], 'j1.A', '', 'j2.' + self.token[3:], 'j1.' + 'A' * 1537, None):
            with self.assertRaises(ApplicationError): self.codec.decode(token, query=self.query)
        with self.assertRaises(ApplicationError): JobListCursorCodec(b'x' * 32).decode(self.token, query=self.query)

    def test_same_dedicated_key_restore_keeps_existing_cursor(self):
        restored = JobListCursorCodec(b'k' * 32)
        self.assertEqual(restored.decode(self.token, query=self.query), self.position)

    def test_strict_key_and_position(self):
        for key in (None, b'k', bytearray(b'k' * 32), 'k' * 32):
            with self.assertRaises(ValueError): JobListCursorCodec(key)
        for before in ((datetime.now(), uuid4()), (self.position[0], str(uuid4())), (), [*self.position]):
            with self.assertRaises(ValueError): self.codec.encode(query=self.query, before=before)
