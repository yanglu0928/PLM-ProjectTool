"""Auth-owned current identity facts for accepted asynchronous work, not credentials."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CurrentUserFacts:
    user_id: UUID
    deployment_role: str

    def __post_init__(self):
        if (type(self.user_id) is not UUID or not self.user_id.int
                or type(self.deployment_role) is not str
                or self.deployment_role not in {"NONE", "DEPLOYMENT_ADMIN"}):
            raise ValueError("invalid current User facts")


class CurrentUserAccessPort(Protocol):
    def current_enabled_user(self, transaction: object, *, user_id: UUID) -> CurrentUserFacts | None:
        """Lock actual enabled User until caller ends transaction; no Session exemption for HTTP."""
        ...
