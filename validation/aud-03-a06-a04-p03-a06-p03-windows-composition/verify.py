"""Real production composition with synthetic trust, actual published DB/file sources."""
from contextlib import ExitStack
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
from fastapi.testclient import TestClient
from plm_assistant.entrypoints import production_login as production
from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


def load(name, folder):
    spec=spec_from_file_location(name,Path(__file__).resolve().parents[1]/folder/'verify.py')
    module=module_from_spec(spec);spec.loader.exec_module(module);return module

fixture=load('_composition_publication','aud-03-a06-a04-p03-a04-p03-publication')
trust=load('_composition_trust','aud-02-a05-windows-platform')


def exercise(v):
    exported=[]
    for scope in ('PROJECT','DEPLOYMENT'):
        _,command,staged=v['prepare'](scope,260);result=v['worker'].publish(command,staged)
        path=(f'/api/v1/projects/{v["project"]}/audit-exports/{command.export_id}' if scope=='PROJECT'
              else f'/api/v1/admin/audit-exports/{command.export_id}')
        exported.append((path,scope,result,staged,{'cookie':'plm_session='+v['tokens'][0 if scope=='PROJECT' else 1].hex()}))
    settings=BootstrapSettings(data_root=v['file_root'],trusted_origins=('http://localhost',))
    prefix='plm_assistant.entrypoints.production_login.'
    with ExitStack() as stack:
        stack.enter_context(patch(prefix+'read_database_url',return_value=v['url']))
        stack.enter_context(patch('plm_assistant.entrypoints.windows_license_runtime.create_windows_license_services',return_value=SimpleNamespace(guard=v['guard'])))
        for name,codec in (
            ('create_windows_secret_list_cursor_codec',trust.SecretListCursorCodec(b'q'*32)),
            ('create_windows_project_member_cursor_codec',trust.MemberListCursorCodec(b'm'*32)),
            ('create_windows_project_department_cursor_codec',trust.DepartmentListCursorCodec(b'd'*32)),
            ('create_windows_document_list_cursor_codec',trust.DocumentListCursorCodec(b'l'*32)),
            ('create_windows_document_version_cursor_codec',trust.VersionListCursorCodec(b'v'*32)),
            ('create_windows_document_parse_cursor_codec',trust.ParseListCursorCodec(b'p'*32)),
            ('create_windows_audit_cursor_codec',trust.AuditListCursorCodec(b'a'*32)),
        ):stack.enter_context(patch(prefix+name,return_value=codec))
        stack.enter_context(patch('plm_assistant.entrypoints.windows_secret_write.create_windows_secret_write_service',return_value=object()))
        stack.enter_context(patch(prefix+'create_windows_document_upload_token_issuer',return_value=trust.HmacUploadTokenIssuer(provider=SimpleNamespace(resolve_key=lambda ref:b'u'*32),key_ref='document-upload-token-v1')))
        for closed in (create_app(),production.create_production_login_app(settings)):
            with TestClient(closed,base_url='http://localhost') as client:
                for path,*rest in exported:
                    assert client.get(path).status_code==404 and client.get(path+'/content').status_code==404
        for factory in (production.create_production_platform_app,production.create_production_platform_write_app):
            with TestClient(factory(settings),base_url='http://localhost') as client:
                for path,scope,result,staged,cookie in exported:
                    response=client.get(path,headers=cookie);assert response.status_code==200,response.text
                    assert response.json()['data']['scope']==scope and response.json()['data']['file_sha256']==result.file_sha256.hex()
                    response=client.get(path+'/content',headers=cookie);assert response.status_code==200,response.text
                    assert len(response.content.splitlines())==260 and hashlib.sha256(response.content).digest()==result.file_sha256
                    assert int(response.headers['content-length'])==result.byte_count
                    assert client.post(path.rsplit('/',1)[0],headers=cookie,json={}).status_code==404
                    assert client.get(path,headers={'cookie':'plm_session='+(b'X'*32).hex()}).status_code==401
                    v['guard'].enabled=False
                    for suffix in ('','/content'):assert client.get(path+suffix,headers=cookie).status_code==403
                    v['guard'].enabled=True
                path,_,result,staged,cookie=exported[0]
                for suffix in ('','/content'):
                    assert client.get(path+suffix,headers=exported[1][-1]).status_code==404
                    assert client.get(f'/api/v1/admin/audit-exports/{result.export_id}'+suffix,headers=exported[1][-1]).status_code==404
                file=v['file_root']/fixture.f._locators(staged.content.coordinate)[1]
                original=file.read_bytes();file.write_bytes(original+b'bad')
                try:
                    response=client.get(path+'/content',headers=cookie)
                    assert response.status_code==503 and response.json()['error']['code']=='FILE_CONTENT_UNAVAILABLE'
                finally:file.write_bytes(original)
                assert client.get('/health/ready').status_code==200
            for name in ('AuditExportContentReader','create_audit_export_result_router','create_audit_export_download_router'):
                with patch(prefix+name,side_effect=RuntimeError('private constructor error')):
                    try:factory(settings)
                    except production.ProductionLoginStartupError as exc:assert 'private' not in str(exc)
                    else:raise AssertionError('partially wired app published')
    print('P03-A06-P03 PASS: both explicit Windows platform factories actual PG/schema/current Session/PM or Admin/published metadata/private file HTTP full hash/headers, unknown Session/Scope/Admin bypass/License/corruption safe; default/login-only404 and export POST closed, three constructor failures do not publish app. Credential/License/cursor/write trust injected synthetic; runtime dispose additionally unit tested; formal account/Server2025/Debian/quality/performance/installer remain pending.')


if __name__=='__main__':fixture.main(exercise=exercise)
