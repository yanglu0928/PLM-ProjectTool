"""Actual PostgreSQL name/unique/version/history and atomic refusal verification."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from psycopg import sql
from sqlalchemy import text
from plm_assistant.modules.auth.application.user_name_patch import (
    PatchUserName, UserNamePatchService, UserNamePatchError)
from plm_assistant.modules.auth.application.managed_user_create import CreateManagedUser, ManagedUserCreateService
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.user_name_patch_repository import SqlAlchemyUserNamePatchRepository
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts

spec = spec_from_file_location('_user_name_publication', Path(__file__).resolve().parents[1]
    / 'aud-03-a06-a04-p03-a04-p03-publication' / 'verify.py')
fixture = module_from_spec(spec); spec.loader.exec_module(fixture)


def exercise(v):
    db = v['db']; hasher = ScryptPasswordHasher()
    results = SqlAlchemyUserCreateResultRepository(verifier=hasher)
    create = ManagedUserCreateService(unit_of_work=v['uow'], access=SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'], users=SqlAlchemyUserRepository(), results=results,
        replay_verifier=UserCreateReplayVerifier(source=results), hasher=hasher,
        audit=v['audit'], receipts=SqlAlchemyIdempotencyReceipts())
    deps = dict(unit_of_work=v['uow'], access=SqlAlchemyUserCreateAccess(),
        license_guard=v['guard'], repository=SqlAlchemyUserNamePatchRepository(), audit=v['audit'])
    service = UserNamePatchService(**deps)
    tables = ('auth_users','auth_password_credentials','auth_sessions','aud_events',
        'plt_idempotency_receipts','auth_user_create_results')
    def snap():
        return {t: tuple(db.execute(sql.SQL('SELECT * FROM plm.{} ORDER BY 1').format(sql.Identifier(t)))) for t in tables}
    key = str(uuid4())
    def original():
        return CreateManagedUser(v['tokens'][1], fixture.base.auth.CSRF, uuid4(),
            'Synthetic original rename user', bytearray(b'Synthetic name proof password'))
    first = create.create(original(), idempotency_key=key)
    def cmd(name, version=1):
        return PatchUserName(v['tokens'][1], fixture.base.auth.CSRF, uuid4(), first.user_id, version, name)
    def reject(command, code, owner=service):
        before = snap()
        try: owner.patch(command)
        except UserNamePatchError as exc: assert exc.code == code, (exc.code, code)
        else: raise AssertionError('Unsafe name mutation accepted')
        assert snap() == before
    before = snap()
    assert service.patch(cmd('  Synthetic original rename user  ')) == first
    assert snap() == before
    credential_before = before['auth_password_credentials']; sessions_before = before['auth_sessions']
    with ThreadPoolExecutor(max_workers=2) as pool:
        def competing(name):
            try: return service.patch(cmd(name))
            except UserNamePatchError as exc: return exc.code
        outcomes = list(pool.map(competing, ('Synthetic renamed A', 'Synthetic renamed B')))
    assert sum(type(x) is str and x == 'CONFLICT_VERSION' for x in outcomes) == 1
    changed = next(x for x in outcomes if type(x) is not str)
    assert changed.lock_version == 2 and changed.credential_version == first.credential_version
    assert changed.account_state == first.account_state and changed.deployment_role == first.deployment_role
    after = snap()
    assert after['auth_password_credentials'] == credential_before and after['auth_sessions'] == sessions_before
    assert after['auth_user_create_results'] == before['auth_user_create_results']
    assert after['plt_idempotency_receipts'] == before['plt_idempotency_receipts']
    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='USER_NAME_CHANGED' AND target_object_id=%s",
        (first.user_id,)).fetchone() == (1,)
    assert db.execute('SELECT username_normalized FROM plm.auth_users WHERE user_id=%s',
        (first.user_id,)).fetchone() == (changed.username_display.casefold(),)
    before = snap(); assert create.create(original(), idempotency_key=key) == first; assert snap() == before
    reject(cmd(changed.username_display, 1), 'CONFLICT_VERSION')
    before = snap(); assert service.patch(cmd(changed.username_display, 2)) == changed; assert snap() == before
    duplicate = fixture.base.auth.user(db, 'Synthetic reserved disabled', b'd'*32, 'NONE')
    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (duplicate,))
    reject(cmd(' SYNTHETIC RESERVED DISABLED ', 2), 'CONFLICT_DUPLICATE')
    renamed = service.patch(cmd('  新名称-e\u0301  ', 2))
    assert renamed.username_display == '新名称-é' and renamed.lock_version == 3
    assert db.execute("SELECT user_id FROM plm.auth_users WHERE username_normalized='synthetic original rename user'").fetchone() is None
    assert db.execute("SELECT user_id FROM plm.auth_users WHERE username_normalized='新名称-é'").fetchone()==(first.user_id,)
    v['guard'].enabled=False
    try: reject(cmd('License denied',3),'LICENSE_OPERATION_DENIED')
    finally: v['guard'].enabled=True
    for command in (replace(cmd('Forbidden', 3), session_token=v['tokens'][0]),
                    replace(cmd('Forbidden', 3), csrf_token=b'?'*32)):
        reject(command, 'AUTH_ACCESS_DENIED')
    reject(replace(cmd('Missing',3),user_id=uuid4()), 'RESOURCE_NOT_FOUND')
    reached=[]
    class FaultAudit:
        def append(self,tx,draft):
            result=v['audit'].append(tx,draft); reached.append(result)
            raise RuntimeError('Synthetic fault after actual audit insert')
    reject(cmd('Rollback name',3), 'AUTH_PATCH_UNAVAILABLE',
        UserNamePatchService(**(deps | {'audit':FaultAudit()})))
    assert len(reached)==1
    class FinalLicenseLoss:
        def append(self,tx,draft):
            result=v['audit'].append(tx,draft)
            v['guard'].enabled=False
            return result
    try:
        reject(cmd('Final License rollback',3),'LICENSE_OPERATION_DENIED',
            UserNamePatchService(**(deps | {'audit':FinalLicenseLoss()})))
    finally: v['guard'].enabled=True
    class FinalRevocation:
        calls=0
        def authorized_admin(self,tx,**kwargs):
            self.calls+=1
            if self.calls==2:
                tx.session.execute(text("UPDATE plm.auth_sessions SET revoked_at=statement_timestamp(), "
                    "revoke_reason='ADMIN_REVOKED', lock_version=lock_version+1 "
                    "WHERE user_id=:actor"),dict(actor=v['users'][1]))
            return deps['access'].authorized_admin(tx,**kwargs)
    revoke=FinalRevocation()
    reject(cmd('Revocation rollback',3),'AUTH_ACCESS_DENIED',
        UserNamePatchService(**(deps | {'access':revoke})))
    assert revoke.calls==2
    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s", (first.user_id,))
    disabled=service.patch(cmd('Synthetic disabled renamed',3))
    assert disabled.account_state=='DISABLED' and disabled.lock_version==4
    before=snap(); assert create.create(original(),idempotency_key=key)==first; assert snap()==before
    # Owned corruption fixture: source mismatch must not be silently repaired.
    db.execute("UPDATE plm.auth_users SET username_display='Synthetic inconsistent source' WHERE user_id=%s",(first.user_id,))
    reject(cmd('No silent repair',4),'AUTH_PATCH_UNAVAILABLE')
    print('PASS: actual PG rename/canonical, disabled unique, same-version concurrency, no-op/stale, '
        'credentials/sessions/first history retained, original create replay, current Admin-CSRF, '
        'post-Audit and final actual Session revoke rollback. No HTTP/production/performance/package claim.')


if __name__ == '__main__': fixture.main(exercise=exercise)
