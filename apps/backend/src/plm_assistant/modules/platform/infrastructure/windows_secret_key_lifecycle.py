"""Explicit, local-only Windows Secret key provisioning and recovery."""

from __future__ import annotations

import secrets
from pathlib import Path

from plm_assistant.modules.platform.infrastructure.secret_key_backup import (
    decrypt_backup, encrypt_backup, read_backup,
    valid_key_ref, write_backup,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


class SecretKeyLifecycleError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("secret key lifecycle unavailable")


def provision_new(*, key_ref: str, backup_path: Path,
                  passphrase: str, provider: WindowsSecretKeyProvider | None = None) -> None:
    """Create an encrypted recovery file before installing a fresh vault key."""
    source = provider or WindowsSecretKeyProvider()
    try:
        if not valid_key_ref(key_ref) or source.resolve_key(key_ref) is not None:
            raise SecretKeyLifecycleError()
        key = secrets.token_bytes(32)
        write_backup(backup_path, encrypt_backup(
            key_ref=key_ref, master_key=key, passphrase=passphrase,
        ))
        source.install_new(key_ref, key)
    except Exception:
        raise SecretKeyLifecycleError() from None


def export_backup(*, key_ref: str, backup_path: Path,
                  passphrase: str, provider: WindowsSecretKeyProvider | None = None) -> None:
    """Create a new encrypted backup of an existing vault key, without replacing it."""
    source = provider or WindowsSecretKeyProvider()
    try:
        if not valid_key_ref(key_ref):
            raise SecretKeyLifecycleError()
        key = source.resolve_key(key_ref)
        if type(key) is not bytes or len(key) != 32:
            raise SecretKeyLifecycleError()
        write_backup(backup_path, encrypt_backup(
            key_ref=key_ref, master_key=key, passphrase=passphrase,
        ))
    except Exception:
        raise SecretKeyLifecycleError() from None


def restore_backup(*, backup_path: Path, passphrase: str,
                   provider: WindowsSecretKeyProvider | None = None) -> str:
    """Authenticate an offline backup and install only if the target is absent."""
    source = provider or WindowsSecretKeyProvider()
    try:
        ref, key = decrypt_backup(read_backup(backup_path), passphrase=passphrase)
        source.install_new(ref, key)
        return ref
    except Exception:
        raise SecretKeyLifecycleError() from None
