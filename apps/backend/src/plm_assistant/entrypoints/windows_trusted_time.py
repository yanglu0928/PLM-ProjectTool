"""Windows composition for the protected trusted-time HMAC key source."""

from __future__ import annotations

from plm_assistant.modules.license.infrastructure.trusted_time_integrity import (
    HmacTrustedTimeIntegrity, TRUSTED_TIME_KEY_REF, TrustedTimeKeyResolverPort,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


class ProductionTrustedTimeStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("trusted time key unavailable")


def create_windows_trusted_time_integrity(
    *, resolver: TrustedTimeKeyResolverPort | None = None,
) -> HmacTrustedTimeIntegrity:
    """Refuse startup unless the separate current-account Vault key exists."""
    try:
        integrity = HmacTrustedTimeIntegrity(
            resolver or WindowsSecretKeyProvider(), key_ref=TRUSTED_TIME_KEY_REF,
        )
        integrity.require_available()
        return integrity
    except Exception:
        raise ProductionTrustedTimeStartupError() from None
