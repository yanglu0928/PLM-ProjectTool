"""Synthetic line layout experiment, no product policy or database."""


def compact(reject):
    try:
        if reject:raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return 'different error'
    except ValueError:
        return 'denied'


def expanded(reject):
    try:
        if reject:
            raise ValueError('Synthetic rejection')
        return 'accepted'
    except LookupError:
        return 'different error'
    except ValueError:
        return 'denied'
