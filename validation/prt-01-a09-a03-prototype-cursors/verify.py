"""Windows 11 current-account Vault proof for Prototype cursor KeyRefs."""

from __future__ import annotations

import ctypes
import secrets
import sys
import uuid
from ctypes import wintypes
from datetime import datetime, timezone

from plm_assistant.entrypoints.windows_prototype_cursor import (
    PROTOTYPE_CURSOR_KEY_REFS,
    ProductionPrototypeCursorStartupError,
    create_windows_prototype_cursor_codecs,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)


_PREFIX = "PLMProjectTool/SecretKey/"


def main() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows proof required")
    suffix = uuid.uuid4().hex
    temporary = {
        formal: f"prt-a09-a03-{index}-{suffix}"
        for index, formal in enumerate(PROTOTYPE_CURSOR_KEY_REFS, start=1)
    }
    vault = WindowsSecretKeyProvider()
    if any(vault.resolve_key(ref) is not None for ref in temporary.values()):
        raise RuntimeError("temporary target collision")
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    library.CredDeleteW.restype = wintypes.BOOL

    class Remapped:
        def resolve_key(self, key_ref: str) -> bytes | None:
            return vault.resolve_key(temporary[key_ref])

    installed: dict[str, bytes] = {}
    try:
        for ref in temporary.values():
            key = secrets.token_bytes(32)
            vault.install_new(ref, key)
            installed[ref] = key
        codecs = create_windows_prototype_cursor_codecs(resolver=Remapped())
        project, package = uuid.uuid4(), uuid.uuid4()
        session = secrets.token_bytes(32)
        instant = datetime.now(timezone.utc)
        token = codecs.package.encode(
            project_id=project, session_token=session, page_size=50,
            updated_at=instant, package_id=package,
        )
        missing = temporary[PROTOTYPE_CURSOR_KEY_REFS[2]]
        if not library.CredDeleteW(_PREFIX + missing, 1, 0):
            raise RuntimeError("temporary key deletion failed")
        with_missing = False
        try:
            create_windows_prototype_cursor_codecs(resolver=Remapped())
        except ProductionPrototypeCursorStartupError:
            with_missing = True
        if not with_missing:
            raise AssertionError("missing KeyRef did not fail closed")
        vault.install_new(missing, installed[missing])
        restored = create_windows_prototype_cursor_codecs(resolver=Remapped())
        assert restored.package.decode(
            token, project_id=project, session_token=session, page_size=50,
        ) == (instant, package)
        print(
            "PASS: five temporary current-account Windows Vault KeyRefs; "
            "missing-key startup fail-closed; restored key validates old cursor; "
            "only owned temporary refs used"
        )
    finally:
        for ref in temporary.values():
            library.CredDeleteW(_PREFIX + ref, 1, 0)
        if any(vault.resolve_key(ref) is not None for ref in temporary.values()):
            raise RuntimeError("temporary KeyRef cleanup failed")


if __name__ == "__main__":
    main()
