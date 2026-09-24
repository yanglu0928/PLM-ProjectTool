"""Windows Credential Manager source for the process account's database URL."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from plm_assistant.modules.platform.infrastructure.database import validate_database_url


DEFAULT_TARGET = "PLMProjectTool/Database"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_MAX_BLOB_BYTES = 2_560


class DatabaseCredentialError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("database credential unavailable")


class _FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FileTime),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _api() -> ctypes.WinDLL:
    if sys.platform != "win32":
        raise DatabaseCredentialError()
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
    return library


def _target(value: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 256 or "\x00" in value:
        raise DatabaseCredentialError()
    return value


def _validate_secret_url(value: str) -> None:
    if type(value) is not str or "\x00" in value:
        raise DatabaseCredentialError()
    parsed = validate_database_url(value)
    if not parsed.host or not parsed.username or not parsed.password:
        raise DatabaseCredentialError()


def read_database_url(*, target: str = DEFAULT_TARGET) -> str:
    """Read the URL for this Windows logon account; never expose OS error text."""

    api = _api()
    credential = ctypes.POINTER(_Credential)()
    try:
        if not api.CredReadW(_target(target), _CRED_TYPE_GENERIC, 0, ctypes.byref(credential)):
            raise DatabaseCredentialError()
        blob = credential.contents
        if not 0 < blob.CredentialBlobSize <= _MAX_BLOB_BYTES or not blob.CredentialBlob:
            raise DatabaseCredentialError()
        raw = ctypes.string_at(blob.CredentialBlob, blob.CredentialBlobSize)
        url = raw.decode("utf-8", errors="strict")
        _validate_secret_url(url)
        return url
    except Exception:
        raise DatabaseCredentialError() from None
    finally:
        if credential:
            api.CredFree(credential)


def write_database_url(url: str, *, target: str = DEFAULT_TARGET) -> None:
    """Provision or rotate this account's Generic Credential locally."""

    try:
        name = _target(target)
        _validate_secret_url(url)
        raw = bytearray(url.encode("utf-8"))
        if not 0 < len(raw) <= _MAX_BLOB_BYTES:
            raise DatabaseCredentialError()
        api = _api()
        blob = (ctypes.c_ubyte * len(raw)).from_buffer(raw)
        credential = _Credential()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = name
        credential.CredentialBlobSize = len(raw)
        credential.CredentialBlob = blob
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "plm-project-tool"
        if not api.CredWriteW(ctypes.byref(credential), 0):
            raise DatabaseCredentialError()
    except Exception:
        raise DatabaseCredentialError() from None
    finally:
        if "raw" in locals():
            raw[:] = b"\x00" * len(raw)
