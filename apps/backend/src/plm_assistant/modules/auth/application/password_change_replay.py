"""Exact before/after password proof; never an authorization capability."""
from dataclasses import dataclass, field
from .password_change_result import PasswordChangeResult


class PasswordChangeReplayError(RuntimeError):
    def __init__(self, code='AUTH_PASSWORD_REPLAY_UNAVAILABLE'):
        self.code=code if type(code) is str and code in (
            'AUTH_PASSWORD_REPLAY_UNAVAILABLE','VALIDATION_FAILED','CONFLICT_IDEMPOTENCY') else 'AUTH_PASSWORD_REPLAY_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(slots=True)
class PasswordChangeProof:
    current_password: bytearray = field(repr=False)
    new_password: bytearray = field(repr=False)

    def erase(self):
        for secret in (self.current_password,self.new_password):
            if type(secret) is bytearray:
                secret[:]=b'\x00'*len(secret)


class PasswordChangeReplayVerifier:
    def __init__(self, *, source):
        if source is None:
            raise ValueError('Actual immutable change credential source required')
        self._source=source

    def require_match(self, transaction, *, result, proof):
        try:
            if type(result) is not PasswordChangeResult or type(proof) is not PasswordChangeProof:
                raise PasswordChangeReplayError('VALIDATION_FAILED')
            result.__post_init__()
            for secret in (proof.current_password,proof.new_password):
                if type(secret) is not bytearray or not 1<=len(secret)<=1024 or b'\x00' in secret:
                    raise PasswordChangeReplayError('VALIDATION_FAILED')
                try:
                    secret.decode('utf-8',errors='strict')
                except UnicodeDecodeError:
                    raise PasswordChangeReplayError('VALIDATION_FAILED') from None
            for role,secret in (('BEFORE',proof.current_password),('AFTER',proof.new_password)):
                view=memoryview(secret)
                try:
                    matched=self._source.verify_credential_password(transaction,result=result,role=role,password=view)
                finally:
                    view.release()
                if matched is False:
                    raise PasswordChangeReplayError('CONFLICT_IDEMPOTENCY')
                if matched is not True:
                    raise PasswordChangeReplayError()
            return result
        except PasswordChangeReplayError:
            raise
        except Exception:
            raise PasswordChangeReplayError() from None
        finally:
            if type(proof) is PasswordChangeProof:
                proof.erase()
