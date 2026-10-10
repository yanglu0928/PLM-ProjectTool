import unittest
from dataclasses import replace
from uuid import uuid4
from plm_assistant.modules.auth.application.session_credential import SessionCredentialFact


class SessionCredentialTests(unittest.TestCase):
    def test_restricted_and_normal_capabilities(self):
        fact=SessionCredentialFact(uuid4(),uuid4(),uuid4(),1,True)
        for cap in ('PASSWORD_STATE','PASSWORD_CHANGE','LOGOUT','SESSION_RENEW'):self.assertTrue(fact.permits(cap))
        self.assertFalse(fact.permits('BUSINESS'))
        self.assertTrue(replace(fact,password_change_required=False).permits('BUSINESS'))
        for cap in ('ADMIN','business','',None,True):self.assertFalse(fact.permits(cap))

    def test_strict_fact(self):
        good=SessionCredentialFact(uuid4(),uuid4(),uuid4(),1,True)
        for field,value in (('credential_version',True),('credential_version',0),('password_change_required',1),
            ('password_change_required',None),('credential_id','client'),('session_id',None)):
            with self.assertRaises(ValueError):replace(good,**{field:value})
