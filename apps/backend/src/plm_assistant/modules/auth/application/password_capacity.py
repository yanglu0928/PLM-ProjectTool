"""Trusted reset/change KDF budget; neither authority nor a secret cache."""
from threading import BoundedSemaphore, Lock, get_ident


class PasswordKdfCapacity:
    """Share one instance between reset/change services in the composition root.

    This does not cover login/create or other processes. Configuration is an
    operator decision, never a request field; changing algorithms is not allowed.
    """

    def __init__(self, *, slots=4):
        if type(slots) is not int or not 1<=slots<=16:
            raise ValueError('AUTH_PASSWORD_CAPACITY_UNAVAILABLE')
        self._slots=slots;self._gate=BoundedSemaphore(slots);self._lock=Lock()
        self._owners={};self._active=0;self._peak=0

    def acquire(self, *, timeout):
        if type(timeout) is not int or timeout!=5:
            raise ValueError('AUTH_PASSWORD_CAPACITY_UNAVAILABLE')
        if not self._gate.acquire(timeout=timeout):return False
        with self._lock:
            owner=get_ident()
            self._owners[owner]=self._owners.get(owner,0)+1
            self._active+=1;self._peak=max(self._peak,self._active)
        return True

    def release(self):
        with self._lock:
            owner=get_ident();held=self._owners.get(owner,0)
            if held<1:raise ValueError('AUTH_PASSWORD_CAPACITY_UNAVAILABLE')
            if held==1:del self._owners[owner]
            else:self._owners[owner]=held-1
            self._active-=1
            self._gate.release()

    def snapshot(self):
        with self._lock:return {'slots':self._slots,'active':self._active,'peak':self._peak}
