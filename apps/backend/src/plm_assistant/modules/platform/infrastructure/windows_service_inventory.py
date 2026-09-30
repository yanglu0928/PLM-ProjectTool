"""Read-only SCM snapshot; never a shutdown or migration clearance."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass, field

from .windows_service_dispatcher import RUNNING, SERVICE_NAMES


SC_MANAGER_CONNECT = 0x0001
SERVICE_QUERY_CONFIG = 0x0001
SERVICE_QUERY_STATUS = 0x0004
SC_STATUS_PROCESS_INFO = 0
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_SERVICE_DOES_NOT_EXIST = 1060
_MAX_CONFIG_BYTES = 8192


class WindowsServiceInventoryError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_SERVICE_INVENTORY_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class ServiceObservation:
    role: str
    service_name: str
    service_type: int
    start_type: int
    error_control: int
    binary_path: str = field(repr=False)
    start_account: str = field(repr=False)
    state: int = 0
    reported_pid: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if (self.role not in SERVICE_NAMES
                or self.service_name != SERVICE_NAMES[self.role]
                or any(type(value) is not int or value < 0 for value in (
                    self.service_type, self.start_type, self.error_control,
                    self.state, self.reported_pid))
                or type(self.binary_path) is not str
                or type(self.start_account) is not str):
            raise WindowsServiceInventoryError()

    @property
    def running_pid(self) -> int | None:
        # Microsoft documents STOP_PENDING as uncertain and STOPPED as invalid.
        return self.reported_pid if self.state == RUNNING and self.reported_pid > 0 else None


class _QueryServiceConfig(ctypes.Structure):
    _fields_ = (
        ("service_type", wintypes.DWORD),
        ("start_type", wintypes.DWORD),
        ("error_control", wintypes.DWORD),
        ("binary_path", wintypes.LPWSTR),
        ("load_order_group", wintypes.LPWSTR),
        ("tag_id", wintypes.DWORD),
        ("dependencies", wintypes.LPWSTR),
        ("start_account", wintypes.LPWSTR),
        ("display_name", wintypes.LPWSTR),
    )


class _ServiceStatusProcess(ctypes.Structure):
    _fields_ = tuple((name, wintypes.DWORD) for name in (
        "service_type", "state", "controls_accepted", "win32_exit_code",
        "service_specific_exit_code", "checkpoint", "wait_hint", "pid",
        "service_flags"))


class _NativeServiceQuery:
    def __init__(self) -> None:
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        api.OpenSCManagerW.argtypes = (
            wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        api.OpenSCManagerW.restype = wintypes.HANDLE
        api.OpenServiceW.argtypes = (
            wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD)
        api.OpenServiceW.restype = wintypes.HANDLE
        api.QueryServiceConfigW.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(_QueryServiceConfig),
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        api.QueryServiceConfigW.restype = wintypes.BOOL
        api.QueryServiceStatusEx.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.BYTE),
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        api.QueryServiceStatusEx.restype = wintypes.BOOL
        api.CloseServiceHandle.argtypes = (wintypes.HANDLE,)
        api.CloseServiceHandle.restype = wintypes.BOOL
        self._api = api

    def read(self, role: str) -> ServiceObservation | None:
        manager = service = None
        try:
            manager = self._api.OpenSCManagerW(None, None, SC_MANAGER_CONNECT)
            if not manager:
                raise WindowsServiceInventoryError()
            service = self._api.OpenServiceW(manager, SERVICE_NAMES[role],
                SERVICE_QUERY_CONFIG | SERVICE_QUERY_STATUS)
            if not service:
                if ctypes.get_last_error() == ERROR_SERVICE_DOES_NOT_EXIST:
                    return None
                raise WindowsServiceInventoryError()

            needed = wintypes.DWORD()
            if (self._api.QueryServiceConfigW(service, None, 0,
                                              ctypes.byref(needed))
                    or ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER
                    or not ctypes.sizeof(_QueryServiceConfig) <= needed.value
                    <= _MAX_CONFIG_BYTES):
                raise WindowsServiceInventoryError()
            buffer = ctypes.create_string_buffer(needed.value)
            config = ctypes.cast(buffer, ctypes.POINTER(_QueryServiceConfig))
            if not self._api.QueryServiceConfigW(service, config,
                                                 needed.value, ctypes.byref(needed)):
                raise WindowsServiceInventoryError()
            status = _ServiceStatusProcess()
            status_size = ctypes.sizeof(status)
            status_buffer = ctypes.cast(ctypes.byref(status),
                                        ctypes.POINTER(wintypes.BYTE))
            if not self._api.QueryServiceStatusEx(service, SC_STATUS_PROCESS_INFO,
                                                  status_buffer, status_size,
                                                  ctypes.byref(needed)):
                raise WindowsServiceInventoryError()
            value = config.contents
            return ServiceObservation(
                role, SERVICE_NAMES[role], value.service_type, value.start_type,
                value.error_control, value.binary_path or "",
                value.start_account or "", status.state, status.pid)
        except WindowsServiceInventoryError:
            raise
        except Exception:
            raise WindowsServiceInventoryError() from None
        finally:
            if service:
                try:
                    self._api.CloseServiceHandle(service)
                except Exception:
                    pass  # Do not mask the fixed diagnostic outcome.
            if manager:
                try:
                    self._api.CloseServiceHandle(manager)
                except Exception:
                    pass


def read_service_observation(role: str, *, reader=None) -> ServiceObservation | None:
    if sys.platform != "win32" or type(role) is not str or role not in SERVICE_NAMES:
        raise WindowsServiceInventoryError()
    try:
        value = (reader if reader is not None else _NativeServiceQuery()).read(role)
    except WindowsServiceInventoryError:
        raise
    except Exception:
        raise WindowsServiceInventoryError() from None
    if value is not None and (type(value) is not ServiceObservation
                              or value.role != role):
        raise WindowsServiceInventoryError()
    return value
