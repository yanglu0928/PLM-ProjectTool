from __future__ import annotations
import unittest,uuid
from contextlib import AbstractContextManager
from datetime import datetime,timezone
from plm_assistant.modules.output.application.cancel_request import (
    CancelOutputRequest,OutputRequestCancelFacts,OutputRequestCancelError,
    OutputRequestCancelService,
)
from plm_assistant.modules.jobs.application.output_cancel import OutputJobCancelResult
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
class Tx(AbstractContextManager):
    def __init__(self,u):self.u=u;self.committed=False
    def __enter__(self):return self
    def __exit__(self,*_):
        if not self.committed:self.u.rollbacks+=1
    def commit(self):self.committed=True;self.u.commits+=1
class Uow:
    def __init__(self):self.commits=0;self.rollbacks=0
    def __call__(self):return Tx(self)
class Access:
    def __init__(self,actor):self.actor=actor;self.allowed=True
    def authenticated_user(self,*_,**__):return self.actor
    def require_canceller(self,*_,**__):return self.allowed
class License:
    def require_valid(self,**_):return True
class Repo:
    def __init__(self,facts):self.facts=facts;self.updates=[]
    def get_for_update(self,*_,**__):return self.facts
    def set_state(self,tx,*,facts,state,completed_at):
        self.facts=OutputRequestCancelFacts(facts.output_request_id,facts.project_id,
          facts.requested_by,facts.job_id,facts.context_snapshot_id,state,facts.lock_version+1)
        self.updates.append((state,completed_at));return facts.lock_version+1
class Jobs:
    def __init__(self,state,changed=True):self.state=state;self.changed=changed;self.calls=[]
    def cancel_output(self,tx,**kw):
        self.calls.append(kw);return OutputJobCancelResult(kw["job_id"],self.state,self.changed)
class Receipts:
    def __init__(self,replay=None):self.replay=replay;self.completed=[]
    def reserve(self,*_,**__):return self.replay
    def complete(self,*_,**kw):self.completed.append(kw["result"])
class Audit:
    def __init__(self):self.events=[]
    def append(self,tx,event):self.events.append(event)
class OutputRequestCancelTests(unittest.TestCase):
    def setUp(self):
        self.actor,self.project,self.request,self.job,self.snapshot,self.trace=[uuid.uuid4() for _ in range(6)]
        self.facts=OutputRequestCancelFacts(self.request,self.project,self.actor,self.job,self.snapshot,"QUEUED",4)
        self.uow=Uow();self.access=Access(self.actor);self.repo=Repo(self.facts)
        self.jobs=Jobs("CANCELLED");self.receipts=Receipts();self.audit=Audit()
        self.command=CancelOutputRequest(bytes.fromhex("11"*32),bytes.fromhex("22"*32),
            self.trace,self.project,self.request,"requested by project owner",4)
        self.service=OutputRequestCancelService(unit_of_work=self.uow,access=self.access,
            license_guard=License(),repository=self.repo,jobs=self.jobs,receipts=self.receipts,
            audit=self.audit,clock=lambda:datetime(2026,11,4,tzinfo=timezone.utc))
    def test_pending_cancel_updates_output_and_job_in_one_uow(self):
        result=self.service.cancel(self.command,idempotency_key="0123456789abcdef")
        self.assertEqual((result.state,result.changed,result.lock_version),("CANCELLED",True,5))
        self.assertEqual((self.uow.commits,self.uow.rollbacks),(1,0))
        self.assertEqual((len(self.jobs.calls),len(self.repo.updates),len(self.audit.events),
                          len(self.receipts.completed)),(1,1,1,1))
    def test_stale_output_version_does_not_cancel_job(self):
        stale=CancelOutputRequest(self.command.session_token,self.command.csrf_token,self.trace,
            self.project,self.request,self.command.reason,3)
        with self.assertRaisesRegex(OutputRequestCancelError,"CONFLICT_VERSION"):
            self.service.cancel(stale,idempotency_key="0123456789abcdef")
        self.assertEqual(self.jobs.calls,[])
        self.assertEqual((self.uow.commits,self.uow.rollbacks),(0,1))
    def test_creator_or_manager_authorization_fails_closed(self):
        self.access.allowed=False
        with self.assertRaisesRegex(OutputRequestCancelError,"RESOURCE_NOT_FOUND"):
            self.service.cancel(self.command,idempotency_key="0123456789abcdef")
        self.assertEqual(self.jobs.calls,[])
    def test_exact_replay_checks_access_and_returns_current_state_without_write(self):
        self.repo.facts=OutputRequestCancelFacts(self.request,self.project,self.actor,self.job,
          self.snapshot,"CANCELLED",5)
        self.receipts.replay=IdempotencyResult("V1_OUTPUT_REQUEST",self.request,200)
        result=self.service.cancel(self.command,idempotency_key="0123456789abcdef")
        self.assertEqual((result.state,result.lock_version,result.changed),("CANCELLED",5,False))
        self.assertEqual((self.jobs.calls,self.audit.events,self.receipts.completed),([],[],[]))
    def test_job_binding_failure_rolls_back_entire_owner(self):
        self.jobs.cancel_output=lambda *_,**__: (_ for _ in ()).throw(RuntimeError("binding mismatch"))
        with self.assertRaisesRegex(OutputRequestCancelError,"SYSTEM_UNAVAILABLE"):
            self.service.cancel(self.command,idempotency_key="0123456789abcdef")
        self.assertEqual((self.uow.commits,self.uow.rollbacks),(0,1))
if __name__=="__main__":unittest.main()
