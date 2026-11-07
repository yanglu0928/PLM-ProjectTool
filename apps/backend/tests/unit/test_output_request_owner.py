from __future__ import annotations
import hashlib,unittest,uuid
from contextlib import AbstractContextManager
from datetime import datetime,timezone
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest,CreatedOutputRequest,OutputRequestError,OutputRequestService,ResolvedOutputContext)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,canonical_payload_fingerprint)
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
    def __init__(self,a):self.actor=a;self.calls=0
    def authorized_creator(self,*_,**__):self.calls+=1;return self.actor
class License:
    def require_valid(self,*,trace_id):return True
class Resolver:
    def __init__(self,refs,payload):self.refs=refs;self.payload=payload
    def resolve(self,*_,**__):return ResolvedOutputContext(self.refs,self.payload,canonical_payload_fingerprint(self.payload))
class Repository:
    def __init__(self):self.existing=None;self.created=[];self.jobs={};self.idempotency_digests=[]
    def lock_generation(self,*_,**__):pass
    def find_generation(self,*_,**__):return self.existing
    def create(self,*_,**kw):
        request=uuid.uuid4();self.created.append(request);self.jobs[request]=uuid.uuid4()
        self.idempotency_digests.append(kw["idempotency_digest"]);return request
    def snapshot_id(self,*_,**__):return uuid.uuid4()
    def attach_job(self,*_,**__):pass
    def get(self,tx,*,project_id,output_request_id):
        if self.existing and self.existing.output_request_id==output_request_id:return self.existing
        return CreatedOutputRequest(output_request_id,project_id,self.jobs[output_request_id],"QUEUED")
class Jobs:
    def __init__(self):self.jobs=[]
    def enqueue_output(self,*_,**__):j=uuid.uuid4();self.jobs.append(j);return j
class Receipts:
    def __init__(self):self.replay=None;self.completed=[]
    def reserve(self,*_,**__):return self.replay
    def complete(self,*_,**kw):self.completed.append(kw["result"])
class Audit:
    def __init__(self):self.events=[]
    def append(self,tx,event):self.events.append(event);return uuid.uuid4()
class OutputRequestOwnerTests(unittest.TestCase):
    def setUp(self):
        self.actor,self.project,self.trace,self.source,self.template=[uuid.uuid4() for _ in range(5)]
        self.uow=Uow();self.access=Access(self.actor);self.repo=Repository();self.jobs=Jobs()
        self.receipts=Receipts();self.audit=Audit()
        self.command=CreateOutputRequest(b"session",b"csrf",self.trace,self.project,"DOCX",
            self.template,(self.source,),"standard-output.v1","word.generate")
        self.service=OutputRequestService(unit_of_work=self.uow,access=self.access,
            license_guard=License(),resolver=Resolver((self.source,),{"source_order":[str(self.source)]}),
            repository=self.repo,jobs=self.jobs,receipts=self.receipts,audit=self.audit,
            clock=lambda:datetime(2026,11,2,tzinfo=timezone.utc))
    def test_create_is_one_transaction_with_job_audit_and_receipt(self):
        result=self.service.create(self.command,idempotency_key="out-create-key-0001")
        self.assertEqual((result.status_code,result.request_state),(202,"QUEUED"))
        self.assertEqual((self.uow.commits,self.uow.rollbacks),(1,0))
        self.assertEqual((len(self.repo.created),len(self.jobs.jobs),len(self.audit.events),len(self.receipts.completed)),(1,1,1,1))
        self.assertEqual(self.repo.idempotency_digests,[hashlib.sha256(b"out-create-key-0001").hexdigest()])
        self.assertNotIn("out-create-key-0001",self.repo.idempotency_digests)
    def test_same_generation_on_a_new_key_reuses_request_without_audit(self):
        self.repo.existing=CreatedOutputRequest(uuid.uuid4(),self.project,uuid.uuid4(),"QUEUED")
        result=self.service.create(self.command,idempotency_key="out-create-key-0002")
        self.assertEqual(result,self.repo.existing)
        self.assertEqual((len(self.repo.created),len(self.jobs.jobs),len(self.audit.events)),(0,0,0))
        self.assertEqual(len(self.receipts.completed),1)
    def test_resolver_cannot_change_fixed_sources(self):
        self.service._resolver=Resolver((uuid.uuid4(),),{})
        with self.assertRaisesRegex(OutputRequestError,"VALIDATION_FAILED"):
            self.service.create(self.command,idempotency_key="out-create-key-0003")
        self.assertEqual((self.uow.commits,self.uow.rollbacks),(0,1))
        self.assertEqual(len(self.jobs.jobs),0)
    def test_missing_project_authority_fails_closed(self):
        self.access.actor=None
        with self.assertRaisesRegex(OutputRequestError,"FORBIDDEN"):
            self.service.create(self.command,idempotency_key="out-create-key-0004")
        self.assertEqual(len(self.repo.created),0)
    def test_receipt_replay_requires_authorization_and_returns_same_refs(self):
        request,job=uuid.uuid4(),uuid.uuid4()
        self.repo.existing=CreatedOutputRequest(request,self.project,job,"QUEUED")
        self.receipts.replay=IdempotencyResult("V1_OUTPUT_REQUEST",request,202)
        result=self.service.create(self.command,idempotency_key="out-create-key-0005")
        self.assertEqual(result,self.repo.existing)
        self.assertEqual(self.access.calls,1)
        self.assertEqual((len(self.repo.created),len(self.jobs.jobs),len(self.audit.events)),(0,0,0))
if __name__=="__main__":unittest.main()
