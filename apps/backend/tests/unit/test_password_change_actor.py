import unittest
from dataclasses import replace
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from plm_assistant.modules.auth.application.password_change_actor import PasswordChangeActorProof
from plm_assistant.modules.auth.application.user_read import UserReadView
from plm_assistant.modules.auth.infrastructure.password_change_access import SqlAlchemyPasswordChangeAccess


class PasswordChangeActorTests(unittest.TestCase):
    def test_normal_and_restricted_any_enabled_role(self):
        now=datetime.now(timezone.utc)
        for role in ('NONE','DEPLOYMENT_ADMIN'):
            for required in (False,True):
                proof=PasswordChangeActorProof(UserReadView(uuid4(),'Synthetic','ENABLED',role,1,now,now,1),
                    uuid4(),required,uuid4(),0,now,now+timedelta(minutes=30),now+timedelta(hours=8))
                self.assertEqual(proof.password_change_required,required)

    def test_bad_proof_and_boundary_inputs(self):
        now=datetime.now(timezone.utc)
        proof=PasswordChangeActorProof(UserReadView(uuid4(),'Synthetic','ENABLED','NONE',1,now,now,1),
            uuid4(),True,uuid4(),0,now,now+timedelta(minutes=30),now+timedelta(hours=8))
        for field,value in (('password_change_required',1),('session_version',True),('session_version',-1),
            ('credential_id','client'),('session_idle_expires_at',now),('session_created_at',datetime.now())):
            with self.assertRaises(ValueError):replace(proof,**{field:value})
        with self.assertRaises(ValueError):replace(proof,user_view=replace(proof.user_view,account_state='DISABLED'))
        access=SqlAlchemyPasswordChangeAccess(verifier=object())
        self.assertIsNone(access.prove(None,session_token=b'x',csrf_token=b'c'*32,now=now))
        self.assertFalse(access.require_changed(None,proof=proof,result=None,session_token=b'x',
            csrf_token=b'c'*32,trace_id=uuid4(),now=now))
