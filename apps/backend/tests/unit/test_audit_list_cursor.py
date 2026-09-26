import base64
from dataclasses import replace
from datetime import datetime,timezone,timedelta
import hashlib
import hmac
import json
import unittest
from uuid import uuid4
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec,_DOMAIN
from plm_assistant.modules.audit.application.queries.audit_query import AuditSearch,AuditPosition
from plm_assistant.modules.platform.application.errors import ApplicationError


class AuditCursorTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)
        self.key=b"k"*32;self.codec=AuditListCursorCodec(self.key)
        self.search=AuditSearch(self.now-timedelta(days=1),self.now,page_size=2)
        self.position=AuditPosition(self.now-timedelta(seconds=1),uuid4())
        self.args=dict(session_token=b"s"*32,actor_id=uuid4(),project_id=uuid4(),search=self.search)
        self.token=self.codec.encode(**self.args,position=self.position)

    def decode(self,**changes):return self.codec.decode(self.token,**(self.args|changes))
    def reject(self,**changes):
        with self.assertRaises(ApplicationError) as exc:self.decode(**changes)
        self.assertEqual(exc.exception.spec.code,"REQUEST_MALFORMED")

    def forge(self,change,*,domain=_DOMAIN):
        encoded,_=self.token.split(".")
        payload=json.loads(base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4)))
        change(payload)
        raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
        b64=lambda b:base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")
        return b64(raw)+"."+b64(hmac.digest(self.key,domain+raw,"sha256"))

    def test_roundtrip_full_search_and_utc_equivalent(self):
        self.assertEqual(self.decode(),replace(self.search,after=self.position))
        offset=timezone(timedelta(hours=8))
        same=replace(self.search,start_at=self.search.start_at.astimezone(offset),end_at=self.search.end_at.astimezone(offset))
        self.assertEqual(self.decode(search=same).after,self.position)
        self.assertEqual(self.codec.encode(**(self.args|dict(search=same)),position=self.position),self.token)

    def test_actor_session_project_deployment_binding_and_wrong_key(self):
        for changes in (dict(actor_id=uuid4()),dict(session_token=b"x"*32),dict(project_id=uuid4()),dict(project_id=None)):
            self.reject(**changes)
        with self.assertRaises(ApplicationError):AuditListCursorCodec(b"x"*32).decode(self.token,**self.args)
        token=self.codec.encode(**(self.args|dict(project_id=None)),position=self.position)
        self.assertEqual(self.codec.decode(token,**(self.args|dict(project_id=None))).after,self.position)

    def test_every_filter_page_size_and_explicit_window_bound(self):
        for changes in (dict(page_size=3),dict(action="OTHER"),dict(outcome="FAILED"),dict(actor_id=uuid4()),
                        dict(target_object_type="PRJ-01"),dict(target_object_id=uuid4()),dict(trace_id=uuid4()),
                        dict(start_at=self.search.start_at+timedelta(seconds=1)),dict(end_at=self.now+timedelta(seconds=1))):
            self.reject(search=replace(self.search,**changes))

    def test_saved_window_retains_first_range_but_filters_still_match(self):
        moved=replace(self.search,start_at=self.search.start_at+timedelta(days=7),end_at=self.search.end_at+timedelta(days=7))
        self.reject(search=moved)
        result=self.codec.decode_saved_window(self.token,**(self.args|dict(search=moved)))
        self.assertEqual(result,replace(self.search,after=self.position))
        with self.assertRaises(ApplicationError):
            self.codec.decode_saved_window(self.token,**(self.args|dict(search=replace(moved,page_size=3))))

    def test_malformed_tampered_oversized_and_noncanonical_tokens(self):
        for token in ("",self.token+"=",self.token+"\n","a"*2100+"."+"b"*43,self.token[:-1]+("A" if self.token[-1]!="A" else "B")):
            with self.assertRaises(ApplicationError):self.codec.decode(token,**self.args)
        for change in (lambda p:p.update(v=True),lambda p:p.update(family="document-list"),
                       lambda p:p.update(extra="field"),lambda p:p.update(event=123),lambda p:p.update(event=p["event"].upper()),
                       lambda p:p.update(time=p["end"]),lambda p:p.update(start="2026-09-01T00:00:00+00:00")):
            with self.assertRaises(ApplicationError):self.codec.decode(self.forge(change),**self.args)
        with self.assertRaises(ApplicationError):self.codec.decode(self.forge(lambda p:None,domain=b""),**self.args)

    def test_dedicated_key_input_shape_and_unsigned_after_rejected(self):
        for key in (None,b"short",bytearray(self.key)):
            with self.assertRaises(ValueError):AuditListCursorCodec(key)
        for changes in (dict(actor_id=True),dict(project_id=False),dict(session_token=b"short"),
                        dict(search=replace(self.search,after=self.position))):
            with self.assertRaises(ValueError):self.codec.encode(**(self.args|changes),position=self.position)
        for pos in (AuditPosition(self.search.end_at,uuid4()),AuditPosition(self.search.start_at-timedelta(seconds=1),uuid4()),None):
            with self.assertRaises(ValueError):self.codec.encode(**self.args,position=pos)

    def test_payload_contains_digest_not_session_or_key_and_is_not_encryption(self):
        encoded,_=self.token.split(".")
        raw=base64.urlsafe_b64decode(encoded+"="*(-len(encoded)%4))
        payload=json.loads(raw)
        self.assertEqual(payload["session"],hashlib.sha256(self.args["session_token"]).hexdigest())
        self.assertNotIn(self.args["session_token"],raw)
        self.assertNotIn(self.key,raw)
        self.assertEqual(payload["actor"],str(self.args["actor_id"]))
