"""Read-only Secret master-key source in the current Windows account's vault.

Provisioning and independent recovery are deliberately separate release tasks.
This adapter never creates, rotates, logs, or exports master-key material.
"""

from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    _Credential,
)


_TARGET_PREFIX = "PLMProjectTool/SecretKey/"
_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z", re.ASCII)


class WindowsSecretKeyProvider:
    """Resolve exactly one 256-bit key under the process logon account."""

    def resolve_key(self, key_ref: str) -> bytes | None:
        if type(key_ref) is not str or _REFERENCE.fullmatch(key_ref) is None:
            return None
        if sys.platform != "win32":
            return None
        credential = ctypes.POINTER(_Credential)()
        try:
            library = ctypes.WinDLL("Advapi32", use_last_error=True)
            library.CredReadW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            library.CredReadW.restype = wintypes.BOOL
            library.CredFree.argtypes = [ctypes.c_void_p]
            library.CredFree.restype = None
            if not library.CredReadW(
                _TARGET_PREFIX + key_ref, 1, 0, ctypes.byref(credential)
            ):
                return None
            blob = credential.contents
            if blob.CredentialBlobSize != 32 or not blob.CredentialBlob:
                return None
            return ctypes.string_at(blob.CredentialBlob, 32)
        except Exception:
            return None
        finally:
            if credential:
                library.CredFree(credential)
