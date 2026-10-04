"""Caller-owned immutable reset first and exact original temporary-password KDF."""
from sqlalchemy import select,insert
from .user_repository import _session
from .user_orm import PasswordResetResultRow as Row,PasswordCredentialRow as Credential
from .user_create_result_repository import SqlAlchemyUserCreateResultRepository
from ..application.password_reset_result import PasswordResetResult
from ..application.password_reset_replay import PasswordResetReplayError
from ..application.ports.password_hash import PasswordHashResult
from ..application.user_read import _id,_time

FIELDS=('result_id','user_id','actor_id','before_credential_id','credential_id','before_credential_version',
    'credential_version','before_user_version','user_version','target_state','audit_event_id','trace_id',
    'revoked_session_count','changed_at','accepted_at')


class SqlAlchemyPasswordResetResults:
    def __init__(self,*,verifier):
        if verifier is None:raise ValueError('Actual password verifier required')
        self._verifier=verifier

    def get(self,transaction,*,result_id):
        try:
            if not _id(result_id):raise PasswordResetReplayError()
            row=_session(transaction).execute(select(*(getattr(Row,c) for c in FIELDS))
                .where(Row.result_id==result_id)).one_or_none()
            return None if row is None else PasswordResetResult(*row)
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None

    def record(self,transaction,*,draft):
        try:
            if type(draft) is not PasswordResetResult:raise PasswordResetReplayError()
            draft.__post_init__()
            self._credential(transaction,draft)
            _session(transaction).execute(insert(Row).values(**{c:getattr(draft,c) for c in FIELDS if c!='accepted_at'}))
            first=self.get(transaction,result_id=draft.result_id)
            if first is None:raise PasswordResetReplayError()
            return first
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None

    def verify_reset_password(self,transaction,*,result,password):
        return self.verify_password_source(source=self.password_source(transaction,result=result),password=password)

    def password_source(self,transaction,*,result):
        """Detached exact historical source, never current authority or ORM state."""
        try:
            if type(result) is not PasswordResetResult:raise PasswordResetReplayError()
            result.__post_init__()
            if self.get(transaction,result_id=result.result_id)!=result:raise PasswordResetReplayError()
            row=self._credential(transaction,result)
            return PasswordHashResult(row.password_hash,row.algorithm_id,dict(row.parameter_set))
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None

    def verify_password_source(self,*,source,password):
        """Real KDF with no transaction; the caller controls the resource bound."""
        try:
            self._validate_source(source)
            if type(password) is not memoryview or not 1<=len(password)<=1024:raise PasswordResetReplayError()
            matched=self._verifier.verify_password(password,password_hash=source.password_hash,
                algorithm_id=source.algorithm_id,parameter_set=source.parameter_set)
            if type(matched) is not bool:raise PasswordResetReplayError()
            return matched
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None

    def require_password_source(self,transaction,*,result,source):
        """Recheck actual immutable first/source, without KDF or authorization."""
        try:
            self._validate_source(source)
            if self.password_source(transaction,result=result)!=source:raise PasswordResetReplayError()
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None

    @staticmethod
    def _validate_source(source):
        if type(source) is not PasswordHashResult:raise PasswordResetReplayError()
        SqlAlchemyUserCreateResultRepository._validate_hash(source.password_hash,source.algorithm_id,source.parameter_set)

    @staticmethod
    def _credential(transaction,result):
        row=_session(transaction).execute(select(Credential.password_hash,Credential.algorithm_id,Credential.parameter_set,
            Credential.must_change_password,Credential.changed_by,Credential.changed_at).where(
            Credential.password_credential_id==result.credential_id,Credential.user_id==result.user_id,
            Credential.credential_version==result.credential_version)).one_or_none()
        if (row is None or row.must_change_password is not True or row.changed_by!=result.actor_id
            or not _time(row.changed_at) or row.changed_at>result.changed_at):raise PasswordResetReplayError()
        SqlAlchemyUserCreateResultRepository._validate_hash(row.password_hash,row.algorithm_id,row.parameter_set)
        return row
