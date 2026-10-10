"""Synthetic caller context exit before an exception handler."""
from contextlib import contextmanager


@contextmanager
def owned():
    yield object()


def compact(reject):
    try:
        with owned():
            if reject:raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return 'different error'
    except ValueError:
        raise
    finally:
        if type(reject) is bool:bool(reject)


def expanded(reject):
    try:
        with owned():
            if reject:
                raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return 'different error'
    except ValueError:
        raise
    finally:
        if type(reject) is bool:
            bool(reject)
