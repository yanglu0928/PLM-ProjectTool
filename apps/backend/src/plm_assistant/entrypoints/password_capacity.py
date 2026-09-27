"""One reset/change KDF budget per composed server process, not all Auth."""
from threading import Lock

from plm_assistant.modules.auth.application.password_capacity import PasswordKdfCapacity

_lock = Lock()
_capacity = None
_slots = None


def get_process_password_capacity(*, slots):
    """Bind once; changing the nonsecret setting requires a process restart."""
    if type(slots) is not int or not 1 <= slots <= 16:
        raise ValueError("AUTH_PASSWORD_CAPACITY_UNAVAILABLE")
    global _capacity, _slots
    with _lock:
        if _capacity is None:
            capacity = PasswordKdfCapacity(slots=slots)
            _capacity, _slots = capacity, slots
        elif slots != _slots:
            raise ValueError("AUTH_PASSWORD_CAPACITY_UNAVAILABLE")
        return _capacity
