"""Caller-UOW immutable password-change first and real historical KDF source."""
from sqlalchemy import select,insert
from .user_repository import _session
from .user_orm import PasswordChangeResultRow as Row, PasswordCredentialRow as Credential
from .user_create_result_repository import SqlAlchemyUserCreateResultRepository
from ..application.user_read import _id,_time
from ..application.password_change_result import PasswordChangeResult
from ..application.password_change_replay import PasswordChangeReplayError
from ..application.ports.password_hash import PasswordHashResult

FIELDS=('result_id','user_id','before_credential_id','credential_id','before_credential_version',
    'credential_version','before_user_version','user_version','audit_event_id','trace_id',
    'revoked_session_count','changed_at','accepted_at')


class SqlAlchemyPasswordChangeResults:
    def __init__(self, *, verifier):
        if verifier is None:raise ValueError('Actual password verifier required')
        self._verifier=verifier

    def get(self,transaction,*,result_id):
        try:
            if not _id(result_id):raise PasswordChangeReplayError()
            row=_session(transaction).execute(select(*(getattr(Row,c) for c in FIELDS))
                .where(Row.result_id==result_id)).one_or_none()
            return None if row is None else PasswordChangeResult(*row)
        except PasswordChangeReplayError:raise
        except Exception:raise PasswordChangeReplayError() from None

    def record(self,transaction,*,draft):
        try:
            if type(draft) is not PasswordChangeResult:raise PasswordChangeReplayError()
            draft.__post_init__()
            for role in ('BEFORE','AFTER'):
                self._credential(transaction,draft,role)
            _session(transaction).execute(insert(Row).values(**{c:getattr(draft,c) for c in FIELDS if c!='accepted_at'}))
            first=self.get(transaction,result_id=draft.result_id)
            if first is None:raise PasswordChangeReplayError()
            return first
        except PasswordChangeReplayError:raise
        except Exception:raise PasswordChangeReplayError() from None

    def verify_credential_password(self,transaction,*,result,role,password):
        return self.verify_password_source(source=self.password_source(transaction,result=result,role=role),password=password)

    def password_source(self,transaction,*,result,role):
        """Detached exact BEFORE/AFTER source; not the latest User credential."""
        try:
            if (type(result) is not PasswordChangeResult or type(role) is not str or role not in ('BEFORE','AFTER')):
                raise PasswordChangeReplayError()
            result.__post_init__()
            if self.get(transaction,result_id=result.result_id)!=result:raise PasswordChangeReplayError()
            row=self._credential(transaction,result,role)
            return PasswordHashResult(row.password_hash,row.algorithm_id,dict(row.parameter_set))
        except PasswordChangeReplayError:raise
        except Exception:raise PasswordChangeReplayError() from None

    def verify_password_source(self,*,source,password):
        """Real KDF without database access; no authority is cached."""
        try:
            self._validate_source(source)
            if type(password) is not memoryview or not 1<=len(password)<=1024:raise PasswordChangeReplayError()
            matched=self._verifier.verify_password(password,password_hash=source.password_hash,
                algorithm_id=source.algorithm_id,parameter_set=source.parameter_set)
            if type(matched) is not bool:raise PasswordChangeReplayError()
            return matched
        except PasswordChangeReplayError:raise
        except Exception:raise PasswordChangeReplayError() from None

    def require_password_source(self,transaction,*,result,role,source):
        """Fresh exact first and source comparison; no KDF and no permission."""
        try:
            self._validate_source(source)
            if self.password_source(transaction,result=result,role=role)!=source:raise PasswordChangeReplayError()
        except PasswordChangeReplayError:raise
        except Exception:raise PasswordChangeReplayError() from None

    @staticmethod
    def _validate_source(source):
        if type(source) is not PasswordHashResult:raise PasswordChangeReplayError()
        SqlAlchemyUserCreateResultRepository._validate_hash(source.password_hash,source.algorithm_id,source.parameter_set)

    @staticmethod
    def _credential(transaction,result,role):
        credential_id=result.before_credential_id if role=='BEFORE' else result.credential_id
        version=result.before_credential_version if role=='BEFORE' else result.credential_version
        row=_session(transaction).execute(select(Credential.password_hash,Credential.algorithm_id,
            Credential.parameter_set,Credential.changed_at,Credential.changed_by,Credential.must_change_password)
            .where(Credential.password_credential_id==credential_id,Credential.user_id==result.user_id,
                Credential.credential_version==version)).one_or_none()
        if (row is None or type(row.must_change_password) is not bool or not _time(row.changed_at)
            or row.changed_at>result.changed_at
            or role=='AFTER' and (row.must_change_password is not False or row.changed_by!=result.user_id)):
            raise PasswordChangeReplayError()
        SqlAlchemyUserCreateResultRepository._validate_hash(row.password_hash,row.algorithm_id,row.parameter_set)
        return row
