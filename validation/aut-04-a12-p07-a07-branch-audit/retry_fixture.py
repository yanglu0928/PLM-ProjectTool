"""Synthetic retry-handler/finally layout, no actual retry or product state."""


def compact(reject):
    try:
        if reject:raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return compact(False)
    except ValueError:raise
    except Exception:raise ValueError('Synthetic fixed error') from None
    finally:
        if type(reject) is bool:bool(reject)


def expanded(reject):
    try:
        if reject:
            raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return expanded(False)
    except ValueError:
        raise
    except Exception:
        raise ValueError('Synthetic fixed error') from None
    finally:
        if type(reject) is bool:
            bool(reject)
