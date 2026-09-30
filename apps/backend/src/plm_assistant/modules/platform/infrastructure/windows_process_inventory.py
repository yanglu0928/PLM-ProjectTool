"""Read-only Windows process candidates; never a maintenance clearance."""

from __future__ import annotations

import ctypes
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath


_SID = re.compile(r"S-\d-\d+(?:-\d+)+\Z", re.ASCII)
_PRODUCT_ENTRY = re.compile(
    r"plm_assistant[./\\]entrypoints[./\\]"
    r"(?:serve_windows|worker_windows|parser_worker_windows|"
    r"maintenance_windows|bootstrap_admin)\b", re.IGNORECASE)
_MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024

_SNAPSHOT_COMMAND = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$rows = @(
    foreach ($process in Get-CimInstance Win32_Process -ErrorAction Stop) {
        [PSCustomObject]@{
            pid = [int]$process.ProcessId
            name = [string]$process.Name
            executable_path = $process.ExecutablePath
            command_line = $process.CommandLine
        }
    }
)
ConvertTo-Json -InputObject $rows -Depth 3 -Compress
"""


class WindowsProcessInventoryError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_PROCESS_INVENTORY_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class ProcessObservation:
    pid: int
    name: str
    owner_sid: str | None
    executable_path: str | None = field(repr=False)
    command_line: str | None = field(repr=False)


@dataclass(frozen=True, slots=True)
class ProcessFinding:
    pid: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessAssessment:
    checked_processes: int
    unreadable_processes: int
    findings: tuple[ProcessFinding, ...]
    classification: str = "DIAGNOSTIC_ONLY"


def assess_processes(observations: tuple[ProcessObservation, ...], *,
                     deployment_sid: str, runtime_root: PureWindowsPath,
                     observer_pid: int) -> ProcessAssessment:
    """Conservative candidate classification, never an OS quiescence proof."""
    if (type(observations) is not tuple or type(deployment_sid) is not str
            or not _SID.fullmatch(deployment_sid)
            or type(runtime_root) is not PureWindowsPath
            or not runtime_root.is_absolute() or len(runtime_root.parts) < 2
            or runtime_root.drive.startswith("\\\\")
            or type(observer_pid) is not int or observer_pid <= 0):
        raise WindowsProcessInventoryError()
    root = tuple(part.casefold() for part in runtime_root.parts)
    findings: list[ProcessFinding] = []
    unreadable = 0
    for process in observations:
        if (type(process) is not ProcessObservation or type(process.pid) is not int
                or process.pid < 0 or type(process.name) is not str
                or process.owner_sid is not None and type(process.owner_sid) is not str
                or process.executable_path is not None
                and type(process.executable_path) is not str
                or process.command_line is not None
                and type(process.command_line) is not str):
            raise WindowsProcessInventoryError()
        if process.pid == observer_pid:
            continue  # This read-only diagnostic is intentionally running.
        if process.owner_sid is None or process.command_line is None:
            unreadable += 1
        reasons: list[str] = []
        if process.owner_sid == deployment_sid:
            reasons.append("DEPLOYMENT_ACCOUNT")
        if process.executable_path:
            executable = PureWindowsPath(process.executable_path)
            path_parts = tuple(part.casefold() for part in executable.parts)
            if path_parts[:len(root)] == root:
                reasons.append("RUNTIME_ROOT")
        if process.command_line and _PRODUCT_ENTRY.search(process.command_line):
            reasons.append("PRODUCT_ENTRYPOINT")
        if reasons:
            findings.append(ProcessFinding(process.pid, tuple(reasons)))
    return ProcessAssessment(len(observations), unreadable,
                             tuple(sorted(findings, key=lambda item: item.pid)))


def collect_windows_processes() -> tuple[ProcessObservation, ...]:
    if sys.platform != "win32":
        raise WindowsProcessInventoryError()
    try:
        directory = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetSystemDirectoryW(
            directory, len(directory))
        if not 0 < length < len(directory):
            raise WindowsProcessInventoryError()
        executable = Path(directory.value) / "WindowsPowerShell/v1.0/powershell.exe"
        if not executable.is_file():
            raise WindowsProcessInventoryError()
        result = subprocess.run(
            [str(executable), "-NoProfile", "-NonInteractive", "-Command",
             _SNAPSHOT_COMMAND], capture_output=True, timeout=30, check=False)
        if result.returncode != 0 or len(result.stdout) > _MAX_SNAPSHOT_BYTES:
            raise WindowsProcessInventoryError()
        rows = json.loads(result.stdout.decode("utf-8-sig"))
        if type(rows) is not list or not rows:
            raise WindowsProcessInventoryError()
        owner_sid = _windows_sid_reader()
        return tuple(ProcessObservation(
            pid=row["pid"], name=row["name"], owner_sid=owner_sid(row["pid"]),
            executable_path=row["executable_path"], command_line=row["command_line"],
        ) for row in rows)
    except Exception:
        # Never disclose a process command line, local path or PowerShell output.
        raise WindowsProcessInventoryError() from None


def _windows_sid_reader():
    """Query process token owner without per-process CIM round trips."""
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int,
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p,
                                               ctypes.POINTER(ctypes.c_wchar_p)]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL

    def read(pid: int) -> str | None:
        if type(pid) is not int or pid <= 0:
            return None
        process = kernel.OpenProcess(0x1000, False, pid)
        if not process:
            return None
        try:
            token = wintypes.HANDLE()
            if not advapi.OpenProcessToken(process, 0x0008, ctypes.byref(token)):
                return None
            try:
                size = wintypes.DWORD()
                advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
                if not 0 < size.value <= 4096:
                    return None
                buffer = ctypes.create_string_buffer(size.value)
                if not advapi.GetTokenInformation(token, 1, buffer, size.value,
                                                 ctypes.byref(size)):
                    return None
                sid_pointer = ctypes.c_void_p.from_buffer(buffer).value
                if not sid_pointer:
                    return None
                result = ctypes.c_wchar_p()
                if not advapi.ConvertSidToStringSidW(sid_pointer,
                                                     ctypes.byref(result)):
                    return None
                try:
                    return result.value
                finally:
                    kernel.LocalFree(ctypes.cast(result, wintypes.HLOCAL))
            finally:
                kernel.CloseHandle(token)
        finally:
            kernel.CloseHandle(process)

    return read
