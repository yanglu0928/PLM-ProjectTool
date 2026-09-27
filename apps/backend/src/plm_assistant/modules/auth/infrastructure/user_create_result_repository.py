"""Auth-owned first view and private original Credential1 verification, read-only."""
import re
from sqlalchemy import select
from .user_orm import UserCreateResultRow, PasswordCredentialRow
from .user_repository import _session
from .scrypt_password import ALGORITHM_ID, PARAMETERS, N, R, P, SALT_BYTES, DKLEN, ENCODED_LEN
from ..application.user_read import UserReadView, _id
from ..application.user_create_result import UserCreateResult
from ..application.user_create_replay import UserCreateReplayError


class SqlAlchemyUserCreateResultRepository:
    def __init__(self, *, verifier):
        if verifier is None: raise ValueError('Actual password verifier required')
        self._verifier=verifier

    def get(self, transaction, *, user_id):
        try:
            if not _id(user_id): raise UserCreateReplayError()
            row=_session(transaction).execute(select(
                UserCreateResultRow.user_id,UserCreateResultRow.username_display,UserCreateResultRow.account_state,
                UserCreateResultRow.deployment_role,UserCreateResultRow.credential_version,UserCreateResultRow.created_at,
                UserCreateResultRow.updated_at,UserCreateResultRow.lock_version,UserCreateResultRow.credential_id,
                UserCreateResultRow.actor_id,UserCreateResultRow.audit_event_id,UserCreateResultRow.trace_id,
                UserCreateResultRow.accepted_at).where(UserCreateResultRow.user_id==user_id)).one_or_none()
            if row is None:return None
            return UserCreateResult(UserReadView(*row[:8]), *row[8:])
        except UserCreateReplayError:raise
        except Exception:raise UserCreateReplayError() from None

    def verify_initial_password(self, transaction, *, result, password):
        try:
            if type(result) is not UserCreateResult:raise UserCreateReplayError()
            result.__post_init__()
            if self.get(transaction,user_id=result.first_view.user_id)!=result:
                raise UserCreateReplayError()
            row=_session(transaction).execute(select(PasswordCredentialRow.password_hash,
                PasswordCredentialRow.algorithm_id,PasswordCredentialRow.parameter_set,
                PasswordCredentialRow.changed_at,PasswordCredentialRow.must_change_password).where(
                PasswordCredentialRow.password_credential_id==result.credential_id,
                PasswordCredentialRow.user_id==result.first_view.user_id,
                PasswordCredentialRow.credential_version==1,
                PasswordCredentialRow.changed_by==result.actor_id)).one_or_none()
            if (row is None or row.must_change_password is not False
                or not result.first_view.created_at<=row.changed_at<=result.first_view.updated_at):
                raise UserCreateReplayError()
            self._validate_hash(row.password_hash,row.algorithm_id,row.parameter_set)
            matched=self._verifier.verify_password(password,password_hash=row.password_hash,
                algorithm_id=row.algorithm_id,parameter_set=row.parameter_set)
            if type(matched) is not bool:raise UserCreateReplayError()
            return matched
        except UserCreateReplayError:raise
        except Exception:raise UserCreateReplayError() from None

    @staticmethod
    def _validate_hash(encoded, algorithm, parameters):
        if (type(algorithm) is not str or algorithm!=ALGORITHM_ID
            or type(parameters) is not dict or parameters!=PARAMETERS
            or any(type(v) is not int for v in parameters.values())
            or type(encoded) is not str or len(encoded)!=ENCODED_LEN):
            raise UserCreateReplayError()
        parts=encoded.split('$')
        if (len(parts)!=8 or parts[:6]!=['','scrypt','1',str(N),str(R),str(P)]
            or not re.fullmatch('[0-9a-f]{'+str(SALT_BYTES*2)+'}',parts[6])
            or not re.fullmatch('[0-9a-f]{'+str(DKLEN*2)+'}',parts[7])):
            raise UserCreateReplayError()
