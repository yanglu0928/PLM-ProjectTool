"""Explicit Windows Worker identity construction; never provision on startup."""

from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.platform.infrastructure.windows_system_actor import (
    SystemActorMaterialPort, WindowsSystemActor,
)


def create_windows_system_actor(
    *, resolver: SystemActorMaterialPort | None = None,
) -> WindowsSystemActor:
    return WindowsSystemActor(
        resolver=WindowsSecretKeyProvider() if resolver is None else resolver,
    )
