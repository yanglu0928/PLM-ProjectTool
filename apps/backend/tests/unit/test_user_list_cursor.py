import unittest,base64
from dataclasses import replace
from datetime import datetime,timezone
from uuid import uuid4
from plm_assistant.modules.auth.api.user_list_cursor import UserListCursorCodec
from plm_assistant.modules.auth.application.user_list import UserListQuery
from plm_assistant.modules.platform.application.errors import ApplicationError


class UserListCursorTests(unittest.TestCase):
    def setUp(self):
        self.codec=UserListCursorCodec(b'u'*32)
        self.q=UserListQuery(b's'*32,uuid4(),2)
        self.position=(datetime.now(timezone.utc),uuid4())
    def test_opaque_randomized_roundtrip_and_original_key_restore(self):
        token=self.codec.encode(query=self.q,before=self.position)
        self.assertEqual(self.codec.decode(token,query=self.q),self.position)
        self.assertNotEqual(token,self.codec.encode(query=self.q,before=self.position))
        packed=base64.urlsafe_b64decode(token[3:]+'='*(-len(token[3:])%4))
        self.assertNotIn(str(self.position[1]).encode(),packed)
        self.assertEqual(UserListCursorCodec(b'u'*32).decode(token,query=replace(self.q,trace_id=uuid4())),self.position)
    def test_tampering_binding_family_and_key_refuse(self):
        token=self.codec.encode(query=self.q,before=self.position)
        for bad in ('',None,token+'=',token.replace('u1.','j1.'),token[:9]+('A' if token[9]!='A' else 'B')+token[10:]):
            with self.assertRaises(ApplicationError):self.codec.decode(bad,query=self.q)
        for q in (replace(self.q,page_size=3),replace(self.q,session_token=b't'*32)):
            with self.assertRaises(ApplicationError):self.codec.decode(token,query=q)
        with self.assertRaises(ApplicationError):UserListCursorCodec(b'v'*32).decode(token,query=self.q)
    def test_no_bad_key_or_position(self):
        for key in (None,b'u'*31,bytearray(b'u'*32)):
            with self.assertRaises(ValueError):UserListCursorCodec(key)
        with self.assertRaises(ValueError):self.codec.encode(query=self.q,before=(datetime.now(),uuid4()))
