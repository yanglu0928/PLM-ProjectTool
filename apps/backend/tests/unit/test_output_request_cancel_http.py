from __future__ import annotations
import unittest,uuid
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.output.api.cancel_request import create_output_request_cancel_router
from plm_assistant.modules.output.application.cancel_request import OutputRequestCancelError,OutputRequestCancelResult
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
class Sessions:
    def validate(self,token,*,csrf_token=None,require_csrf=False):
        if require_csrf is not True:raise AssertionError()
        if token!=bytes.fromhex("11"*32):raise SessionError("AUTH_SESSION_EXPIRED")
        return SimpleNamespace(user_id=uuid.uuid4())
class Origins:
    def require_trusted(self,headers):pass
class Service:
    def __init__(self):self.result=None;self.received=None
    def cancel(self,command,*,idempotency_key):
        self.received=(command,idempotency_key)
        if isinstance(self.result,Exception):raise self.result
        return self.result
class OutputRequestCancelHttpTests(unittest.TestCase):
    def setUp(self):
        self.project,self.request,self.trace=[uuid.uuid4() for _ in range(3)]
        self.service=Service();self.app=FastAPI()
        @self.app.middleware("http")
        async def trace(request,call_next):
            request.state.trace_id=str(self.trace);return await call_next(request)
        self.app.include_router(create_output_request_cancel_router(
            sessions=Sessions(),origins=Origins(),service=self.service))
        install_error_handlers(self.app);self.client=TestClient(self.app)
        self.headers={"origin":"https://plm.example.test",
          "cookie":"plm_session="+"11"*32,"x-csrf-token":"22"*32,
          "idempotency-key":"0123456789abcdef","if-match":'"v4"'}
        self.path=f"/api/v1/projects/{self.project}/output-requests/{self.request}:cancel"
    def test_cancel_response_is_minimal_and_returns_new_etag(self):
        self.service.result=OutputRequestCancelResult(self.request,self.project,"CANCELLED",True,5)
        response=self.client.post(self.path,headers=self.headers,json={"reason":"cancel requested"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["etag"],'"v5"')
        self.assertEqual(response.json()["data"],{"output_request_id":str(self.request),
            "state":"CANCELLED","changed":True,"etag":'"v5"'})
        self.assertEqual(self.service.received[0].expected_version,4)
    def test_extra_fields_and_query_are_rejected(self):
        response=self.client.post(self.path,headers=self.headers,
            json={"reason":"x","job_id":str(uuid.uuid4())})
        self.assertEqual(response.status_code,400)
        response=self.client.post(self.path+"?state=FAILED",headers=self.headers,json={"reason":"x"})
        self.assertEqual(response.status_code,400)
    def test_stale_version_uses_safe_conflict(self):
        self.service.result=OutputRequestCancelError("CONFLICT_VERSION")
        response=self.client.post(self.path,headers=self.headers,json={"reason":"cancel requested"})
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()["error"]["code"],"CONFLICT_VERSION")
if __name__=="__main__":unittest.main()
