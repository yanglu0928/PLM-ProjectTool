"""Explicit Windows platform: real Session/Project/Audit, synthetic trust sources."""
from contextlib import ExitStack
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.production_login import create_production_login_app,create_production_platform_app,create_production_platform_write_app,ProductionLoginStartupError
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.audit.api.list_cursor import AuditListCursorCodec
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.department_list_cursor import DepartmentListCursorCodec
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.infrastructure.upload_token import HmacUploadTokenIssuer

spec=spec_from_file_location("_audit_platform_fixture",Path(__file__).resolve().parents[1]/"aud-02-a02-list-cursor"/"verify.py")
fixture=module_from_spec(spec)
spec.loader.exec_module(fixture)


def verify_platform(*,url,session,admin_session,project,local,deployed,guard):
    prefix="plm_assistant.entrypoints.production_login."
    with TemporaryDirectory(prefix="plm-audit-platform-") as directory,ExitStack() as stack:
        settings=BootstrapSettings(data_root=Path(directory),trusted_origins=("http://localhost",))
        stack.enter_context(patch(prefix+"read_database_url",return_value=url))
        stack.enter_context(patch("plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services",return_value=SimpleNamespace(guard=guard)))
        for name,codec in (
            ("create_windows_secret_list_cursor_codec",SecretListCursorCodec(b"q"*32)),
            ("create_windows_project_member_cursor_codec",MemberListCursorCodec(b"m"*32)),
            ("create_windows_project_department_cursor_codec",DepartmentListCursorCodec(b"d"*32)),
            ("create_windows_document_list_cursor_codec",DocumentListCursorCodec(b"l"*32)),
            ("create_windows_document_version_cursor_codec",VersionListCursorCodec(b"v"*32)),
            ("create_windows_document_parse_cursor_codec",ParseListCursorCodec(b"p"*32)),
            ("create_windows_audit_cursor_codec",AuditListCursorCodec(b"a"*32)),
        ):stack.enter_context(patch(prefix+name,return_value=codec))
        stack.enter_context(patch("plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service",return_value=object()))
        stack.enter_context(patch(prefix+"create_windows_document_upload_token_issuer",return_value=HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref:b"u"*32),key_ref="document-upload-token-v1")))
        path=f"/api/v1/projects/{project}/audit-events"
        headers={"Cookie":"plm_session="+session.hex()}
        ah={"Cookie":"plm_session="+admin_session.hex()}
        for closed in (create_app(),create_production_login_app(settings)):
            with TestClient(closed,base_url="http://localhost") as client:
                assert client.get(path,headers=headers).status_code==404
                assert client.get("/api/v1/admin/audit-events",headers=ah).status_code==404
        for factory in (create_production_platform_app,create_production_platform_write_app):
            with TestClient(factory(settings),base_url="http://localhost") as client:
                first=client.get(path,headers=headers,params={"page_size":2})
                assert first.status_code==200,first.text
                second=client.get(path,headers=headers,params={"page_size":2,"cursor":first.json()["data"]["next_cursor"]})
                assert second.status_code==200,second.text
                records=first.json()["data"]["items"]+second.json()["data"]["items"]
                assert len(records)==len(local)==4 and {v["audit_event_id"] for v in records}=={str(v) for v in local}
                assert client.get(path+"/"+str(local[0]),headers=headers).status_code==200
                assert client.get(path,headers=ah).status_code==404
                assert client.get("/api/v1/admin/audit-events",headers=ah).status_code==200
                assert client.get("/api/v1/admin/audit-events/"+str(deployed[0]),headers=ah).status_code==200
                assert client.get("/api/v1/admin/audit-events/"+str(local[0]),headers=ah).status_code==404
                guard.enabled=False
                assert client.get(path,headers=headers).status_code==403
                guard.enabled=True
                assert client.get("/health/ready").status_code==200
            with patch(prefix+"create_windows_audit_cursor_codec",side_effect=RuntimeError("synthetic missing audit trust")):
                try:factory(settings)
                except ProductionLoginStartupError as exc:assert "synthetic missing" not in str(exc)
                else:raise AssertionError("platform opened without Audit key")
    print("AUD-02-A05 PASS: both explicit platform modes real Session/PM/Admin/scope/keyset, default/login closed, missing Audit key fails closed; synthetic License/keys, no production ceremony")


if __name__=="__main__":fixture.main(resolved=True,http=True,platform_check=verify_platform)
