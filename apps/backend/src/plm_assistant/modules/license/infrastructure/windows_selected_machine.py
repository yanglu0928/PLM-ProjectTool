"""Verify the explicitly selected License MAC against local Windows adapters."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes

from plm_assistant.modules.license.application.license_validation import normalize_mac


_BUFFER_OVERFLOW = 111
_MAX_BUFFER = 1_048_576
_MAX_ADAPTERS = 1024
_INCLUDE_ALL_INTERFACES = 0x0100


class SelectedMachineUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("selected machine unavailable")


class _AdapterHeader(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.c_void_p),
        ("AdapterName", ctypes.c_void_p),
        ("FirstUnicastAddress", ctypes.c_void_p),
        ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p),
        ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_void_p),
        ("Description", ctypes.c_void_p),
        ("FriendlyName", ctypes.c_void_p),
        ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.ULONG),
    ]


def windows_local_macs() -> frozenset[str]:
    """Enumerate six-byte MACs without parsing localized command output."""
    if sys.platform != "win32":
        raise SelectedMachineUnavailable()
    try:
        library = ctypes.WinDLL("Iphlpapi", use_last_error=True)
        library.GetAdaptersAddresses.argtypes = [
            wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG),
        ]
        library.GetAdaptersAddresses.restype = wintypes.ULONG
        size = wintypes.ULONG(15_360)
        for _ in range(3):
            if not 0 < size.value <= _MAX_BUFFER:
                raise SelectedMachineUnavailable()
            buffer = ctypes.create_string_buffer(size.value)
            result = library.GetAdaptersAddresses(
                0, _INCLUDE_ALL_INTERFACES, None, buffer, ctypes.byref(size),
            )
            if result == _BUFFER_OVERFLOW:
                continue
            if result != 0:
                raise SelectedMachineUnavailable()
            values: set[str] = set()
            pointer = ctypes.addressof(buffer)
            seen: set[int] = set()
            while pointer:
                if pointer in seen or len(seen) >= _MAX_ADAPTERS:
                    raise SelectedMachineUnavailable()
                seen.add(pointer)
                adapter = ctypes.cast(pointer, ctypes.POINTER(_AdapterHeader)).contents
                if adapter.Length < ctypes.sizeof(_AdapterHeader):
                    raise SelectedMachineUnavailable()
                if adapter.PhysicalAddressLength == 6:
                    raw = bytes(adapter.PhysicalAddress[:6])
                    try:
                        values.add(normalize_mac(raw.hex()))
                    except Exception:
                        pass
                pointer = adapter.Next
            return frozenset(values)
        raise SelectedMachineUnavailable()
    except Exception:
        raise SelectedMachineUnavailable() from None


class WindowsSelectedMachine:
    def __init__(self, configured_mac: str | None,
                 *, enumerate_macs: Callable[[], frozenset[str]] = windows_local_macs) -> None:
        self._configured_mac = configured_mac
        self._enumerate_macs = enumerate_macs

    def selected_mac(self) -> str:
        try:
            selected = normalize_mac(self._configured_mac)
            actual = self._enumerate_macs()
            if type(actual) is not frozenset or selected not in actual:
                raise SelectedMachineUnavailable()
            return selected
        except Exception:
            raise SelectedMachineUnavailable() from None
