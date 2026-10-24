"""Write-only temporary-password equality against immutable reset first source."""
from dataclasses import dataclass,field
from .password_reset_result import PasswordResetResult


class PasswordResetReplayError(RuntimeError):
    def __init__(self,code='AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE'):
        self.code=code if type(code) is str and code in ('AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE',
            'VALIDATION_FAILED','CONFLICT_IDEMPOTENCY') else 'AUTH_PASSWORD_RESET_REPLAY_UNAVAILABLE'
        super().__init__(self.code)


@dataclass(slots=True)
class PasswordResetProof:
    temporary_password:bytearray=field(repr=False)
    def erase(self):
        if type(self.temporary_password) is bytearray:
            self.temporary_password[:]=b'\x00'*len(self.temporary_password)


class PasswordResetReplayVerifier:
    def __init__(self,*,source):
        if source is None:raise ValueError('Actual immutable reset credential source required')
        self._source=source

    def require_match(self,transaction,*,result,proof):
        try:
            if type(result) is not PasswordResetResult or type(proof) is not PasswordResetProof:
                raise PasswordResetReplayError('VALIDATION_FAILED')
            result.__post_init__()
            secret=proof.temporary_password
            if type(secret) is not bytearray or not 1<=len(secret)<=1024 or b'\x00' in secret:
                raise PasswordResetReplayError('VALIDATION_FAILED')
            try:secret.decode('utf-8',errors='strict')
            except UnicodeDecodeError:raise PasswordResetReplayError('VALIDATION_FAILED') from None
            with memoryview(secret) as password:
                matched=self._source.verify_reset_password(transaction,result=result,password=password)
            if matched is False:raise PasswordResetReplayError('CONFLICT_IDEMPOTENCY')
            if matched is not True:raise PasswordResetReplayError()
            return result
        except PasswordResetReplayError:raise
        except Exception:raise PasswordResetReplayError() from None
        finally:
            if type(proof) is PasswordResetProof:proof.erase()
