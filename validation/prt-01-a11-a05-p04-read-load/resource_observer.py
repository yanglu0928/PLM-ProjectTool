"""Bounded Windows host-resource sampling for synthetic verifier diagnostics."""

from __future__ import annotations

import ctypes
import math
import statistics
import sys
import threading
import time
from collections.abc import Callable
from ctypes import wintypes


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _filetime_value(value: _FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def cpu_percent(previous: tuple[int, int], current: tuple[int, int]) -> float | None:
    """Calculate busy percentage from (idle, total) GetSystemTimes counters."""
    previous_idle, previous_total = previous
    current_idle, current_total = current
    idle_delta = current_idle - previous_idle
    total_delta = current_total - previous_total
    if total_delta <= 0 or idle_delta < 0 or idle_delta > total_delta:
        return None
    return round(100.0 * (total_delta - idle_delta) / total_delta, 2)


def read_windows_sample(
    previous: tuple[int, int] | None,
) -> tuple[tuple[int, int], float | None, float]:
    if sys.platform != "win32":
        raise OSError("unsupported platform")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("counter unavailable")
    current = (
        _filetime_value(idle),
        _filetime_value(kernel) + _filetime_value(user),
    )
    memory = _MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("counter unavailable")
    cpu = cpu_percent(previous, current) if previous is not None else None
    available_mb = round(float(memory.ullAvailPhys) / (1024 * 1024), 1)
    return current, cpu, available_mb


def _percentile95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def summarize_samples(
    cpu_samples: list[float], memory_samples: list[float], elapsed_seconds: float
) -> dict[str, object]:
    if not cpu_samples or not memory_samples:
        return {
            "status": "UNAVAILABLE",
            "scope": "verifier_process",
            "sample_count": min(len(cpu_samples), len(memory_samples)),
            "elapsed_seconds": round(max(0.0, elapsed_seconds), 3),
        }
    return {
        "status": "AVAILABLE",
        "scope": "verifier_process",
        "sample_count": min(len(cpu_samples), len(memory_samples)),
        "cpu_percent_p95": _percentile95(cpu_samples),
        "cpu_percent_max": max(cpu_samples),
        "available_memory_mb_min": min(memory_samples),
        "available_memory_mb_median": round(statistics.median(memory_samples), 1),
        "elapsed_seconds": round(max(0.0, elapsed_seconds), 3),
    }


class ResourceObserver:
    """Samples aggregate CPU/memory counters; never exposes host identity or raw errors."""

    def __init__(
        self,
        reader: Callable[
            [tuple[int, int] | None],
            tuple[tuple[int, int], float | None, float],
        ] = read_windows_sample,
        interval_seconds: float = 0.5,
    ) -> None:
        self._reader = reader
        self._interval = max(0.1, interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous: tuple[int, int] | None = None
        self._cpu: list[float] = []
        self._memory: list[float] = []
        self._unavailable = False
        self._started = 0.0

    def start(self) -> None:
        self._started = time.monotonic()
        self._thread = threading.Thread(
            target=self._collect, name="prt-resource-observer", daemon=True
        )
        self._thread.start()

    def _collect(self) -> None:
        while not self._stop.is_set():
            try:
                counters, cpu_value, available_mb = self._reader(self._previous)
                self._previous = counters
                self._memory.append(float(available_mb))
                if cpu_value is not None:
                    self._cpu.append(float(cpu_value))
            except Exception:
                self._unavailable = True
                return
            self._stop.wait(self._interval)

    def stop(self) -> dict[str, object]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        elapsed = max(0.0, time.monotonic() - self._started)
        if self._unavailable:
            return {
                "status": "UNAVAILABLE",
                "scope": "verifier_process",
                "sample_count": 0,
                "elapsed_seconds": round(elapsed, 3),
            }
        return summarize_samples(self._cpu, self._memory, elapsed)
