"""Explicit, single-role Windows SCM registration; no start or overwrite."""

from __future__ import annotations

import ctypes
import getpass
import os
import re
import struct
import sys
from ctypes import wintypes
from importlib import metadata
from pathlib import Path

from plm_assistant import __version__
from plm_assistant.entrypoints.service_plan_windows import (
    WindowsServicePlanError, build_service_plan,
)
from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    SERVICE_NAMES, SERVICE_WIN32_OWN_PROCESS,
)


SC_MANAGER_CREATE_SERVICE = 0x0002
SERVICE_QUERY_STATUS = 0x0004
SERVICE_DEMAND_START = 0x0003
SERVICE_ERROR_NORMAL = 0x0001
_ACCOUNT = re.compile(r"(?:\.|[A-Za-z0-9_.-]{1,64})\\[A-Za-z0-9_.\-$]{1,64}\Z")


class WindowsServiceInstallError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_SERVICE_INSTALL_UNAVAILABLE")


def verify_installer_runtime(python_exe: Path) -> None:
    """The installer must run from the exact interpreter it registers."""
    try:
        if (sys.platform != "win32" or sys.version_info[:2] != (3, 13)
                or struct.calcsize("P") != 8
                or not isinstance(python_exe, Path)
                or not python_exe.is_absolute()
                or not os.path.samefile(python_exe, sys.executable)
                or metadata.version("plm-project-tool-backend") != __version__):
            raise WindowsServiceInstallError()
    except (OSError, metadata.PackageNotFoundError):
        raise WindowsServiceInstallError() from None


class _NativeServiceControl:
    def __init__(self) -> None:
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        api.OpenSCManagerW.argtypes = (
            wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        api.OpenSCManagerW.restype = wintypes.HANDLE
        api.CreateServiceW.argtypes = (
            wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
            wintypes.LPCWSTR, wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPCWSTR,
            wintypes.LPCWSTR, wintypes.LPCWSTR)
        api.CreateServiceW.restype = wintypes.HANDLE
        api.CloseServiceHandle.argtypes = (wintypes.HANDLE,)
        api.CloseServiceHandle.restype = wintypes.BOOL
        self._api = api

    def open_manager(self):
        return self._api.OpenSCManagerW(None, None, SC_MANAGER_CREATE_SERVICE)

    def create_service(self, manager, *, name: str, binary_path: str,
                       account: str, password_buffer):
        return self._api.CreateServiceW(
            manager, name, name, SERVICE_QUERY_STATUS,
            SERVICE_WIN32_OWN_PROCESS, SERVICE_DEMAND_START,
            SERVICE_ERROR_NORMAL, binary_path, None, None, None,
            account, password_buffer)

    def close_handle(self, handle) -> None:
        self._api.CloseServiceHandle(handle)


def install_fixed_service(role: str, python_exe: Path, bootstrap_yaml: Path,
                          account: str, password: str, *, scm=None) -> None:
    """Create exactly one manual-start service; an existing name is never changed."""
    if (sys.platform != "win32" or type(role) is not str
            or role not in SERVICE_NAMES or type(account) is not str
            or not _ACCOUNT.fullmatch(account)
            or account.upper().startswith(("NT AUTHORITY\\", "NT SERVICE\\"))
            or type(password) is not str or not password or "\x00" in password):
        raise WindowsServiceInstallError()
    try:
        plan = build_service_plan(python_exe, bootstrap_yaml)
        verify_installer_runtime(python_exe)
    except WindowsServicePlanError:
        raise WindowsServiceInstallError() from None
    command = next((item["binary_path"] for item in plan["service_commands"]
                    if item["role"] == role), None)
    if command is None:
        raise WindowsServiceInstallError()
    try:
        control = scm if scm is not None else _NativeServiceControl()
    except Exception:
        raise WindowsServiceInstallError() from None
    manager = service = None
    password_buffer = ctypes.create_unicode_buffer(password)
    try:
        manager = control.open_manager()
        if not manager:
            raise WindowsServiceInstallError()
        service = control.create_service(
            manager, name=SERVICE_NAMES[role], binary_path=command,
            account=account, password_buffer=password_buffer)
        if not service:
            # CreateServiceW refuses existing names. Never reconfigure or delete.
            raise WindowsServiceInstallError()
    except WindowsServiceInstallError:
        raise
    except Exception:
        raise WindowsServiceInstallError() from None
    finally:
        for index in range(len(password_buffer)):
            password_buffer[index] = "\x00"
        if service:
            try:
                control.close_handle(service)
            except Exception:
                pass  # The service may exist; never compensate by deleting it.
        if manager:
            try:
                control.close_handle(manager)
            except Exception:
                pass


def main() -> int:
    if (sys.platform != "win32" or len(sys.argv) != 6
            or sys.argv[1] != "--install" or sys.argv[2] not in SERVICE_NAMES
            or not sys.stdin.isatty()):
        print("Usage: python -m plm_assistant.entrypoints.service_install_windows "
              "--install {API|AUDIT_WORKER|PARSER_WORKER|AI_PROVIDER_WORKER} "
              "<absolute-python.exe> <absolute-bootstrap.yaml> <account>",
              file=sys.stderr)
        return 2
    try:
        role, python_exe, bootstrap_yaml, account = sys.argv[2:]
        build_service_plan(Path(python_exe), Path(bootstrap_yaml))
        verify_installer_runtime(Path(python_exe))
        if not _ACCOUNT.fullmatch(account):
            raise WindowsServiceInstallError()
        password = getpass.getpass("Service account password: ")
        try:
            install_fixed_service(role, Path(python_exe),
                                  Path(bootstrap_yaml), account, password)
        finally:
            del password
    except (WindowsServicePlanError, WindowsServiceInstallError, EOFError):
        print("Windows service registration rejected; no start attempted. "
              "If CreateServiceW succeeded, inspect exact SCM entry before "
              "any recovery action.", file=sys.stderr)
        return 1
    print("Service registration requested; manual start and independent "
          "SCM/account/resource verification remain required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
