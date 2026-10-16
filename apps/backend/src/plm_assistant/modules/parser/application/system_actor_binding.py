"""Pin one controlled Worker identity per Parser state transition."""

from __future__ import annotations

import uuid


class ParserSystemActorUnavailable(RuntimeError):
    pass


class ParserSystemActorBinding:
    def __init__(self, *, system_actor_id: uuid.UUID | None = None,
                 system_actor: object | None = None) -> None:
        if (system_actor_id is None) == (system_actor is None):
            raise ValueError("Exactly one Parser system actor source required")
        if system_actor_id is not None and (
                type(system_actor_id) is not uuid.UUID or system_actor_id.int == 0):
            raise ValueError("Invalid Parser system actor")
        if system_actor is not None and not callable(getattr(system_actor, "assert_current", None)):
            raise ValueError("Controlled Parser system actor required")
        self._fixed = system_actor_id
        self._source = system_actor

    def capture(self) -> uuid.UUID:
        try:
            value = self._fixed if self._source is None else self._source.assert_current()
            if type(value) is not uuid.UUID or value.int == 0:
                raise ValueError()
            return value
        except Exception:
            raise ParserSystemActorUnavailable() from None

    def assert_same(self, identity: uuid.UUID) -> None:
        if type(identity) is not uuid.UUID or self.capture() != identity:
            raise ParserSystemActorUnavailable()
