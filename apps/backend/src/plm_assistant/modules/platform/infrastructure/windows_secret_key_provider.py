"""Read-only Secret master-key source in the current Windows account's vault.

Provisioning and independent recovery are deliberately separate release tasks.
This adapter never creates, rotates, logs, or exports master-key material.
"""

from __future__ import annotations

import ctypes
import hmac
import sys
from ctypes import wintypes

from plm_assistant.modules.platform.infrastructure.secret_key_backup import valid_key_ref
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    _Credential,
)


_TARGET_PREFIX = "PLMProjectTool/SecretKey/"
class WindowsSecretKeyProvider:
    """Resolve exactly one 256-bit key under the process logon account."""

    def resolve_key(self, key_ref: str) -> bytes | None:
        if not valid_key_ref(key_ref):
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

    def install_new(self, key_ref: str, master_key: bytes) -> None:
        """Install a new target only; never intentionally replace an existing key."""
        if (not valid_key_ref(key_ref) or type(master_key) is not bytes
                or len(master_key) != 32 or sys.platform != "win32"):
            raise RuntimeError("secret key installation unavailable")
        target = _TARGET_PREFIX + key_ref
        try:
            library = ctypes.WinDLL("Advapi32", use_last_error=True)
            library.CredReadW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            library.CredReadW.restype = wintypes.BOOL
            library.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
            library.CredWriteW.restype = wintypes.BOOL
            library.CredFree.argtypes = [ctypes.c_void_p]
            library.CredFree.restype = None
            existing = ctypes.POINTER(_Credential)()
            try:
                if library.CredReadW(target, 1, 0, ctypes.byref(existing)):
                    raise RuntimeError("secret key installation unavailable")
                # ERROR_NOT_FOUND only. Access denied and other errors must fail closed.
                if ctypes.get_last_error() != 1168:
                    raise RuntimeError("secret key installation unavailable")
            finally:
                if existing:
                    library.CredFree(existing)
            blob = (ctypes.c_ubyte * 32).from_buffer_copy(master_key)
            credential = _Credential()
            credential.Type = 1
            credential.TargetName = target
            credential.CredentialBlobSize = 32
            credential.CredentialBlob = blob
            credential.Persist = 2
            credential.UserName = "plm-project-tool"
            if not library.CredWriteW(ctypes.byref(credential), 0):
                raise RuntimeError("secret key installation unavailable")
            if not hmac.compare_digest(self.resolve_key(key_ref) or b"", master_key):
                raise RuntimeError("secret key installation unavailable")
        except Exception:
            raise RuntimeError("secret key installation unavailable") from None
        finally:
            if "blob" in locals():
                ctypes.memset(ctypes.addressof(blob), 0, 32)
