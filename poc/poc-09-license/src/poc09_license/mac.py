from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import LicenseError


_MAC_HEX = re.compile(r"^[0-9A-F]{12}$")


@dataclass(frozen=True)
class MacCandidate:
    interface: str
    mac: str
    status: str


def normalize_mac(value: str) -> str:
    if not isinstance(value, str):
        raise LicenseError("LICENSE_MAC_INVALID", "MAC address must be text")
    compact = re.sub(r"[:.\-\s]", "", value).upper()
    if not _MAC_HEX.fullmatch(compact) or compact in {"000000000000", "FFFFFFFFFFFF"}:
        raise LicenseError("LICENSE_MAC_INVALID", "MAC address must contain 12 usable hexadecimal digits")
    return ":".join(compact[index : index + 2] for index in range(0, 12, 2))


def machine_fingerprint(mac: str) -> str:
    return hashlib.sha256(normalize_mac(mac).encode("ascii")).hexdigest()


def select_mac(candidates: Iterable[MacCandidate], selected_mac: str | None) -> MacCandidate:
    if selected_mac is None or not str(selected_mac).strip():
        raise LicenseError("LICENSE_MAC_SELECTION_REQUIRED", "An operator must select one discovered MAC address")
    selected = normalize_mac(selected_mac)
    available = {normalize_mac(candidate.mac): candidate for candidate in candidates}
    if selected not in available:
        raise LicenseError("LICENSE_MAC_NOT_AVAILABLE", "The selected MAC address is not in the discovered list")
    candidate = available[selected]
    return MacCandidate(candidate.interface, selected, candidate.status)


def _discover_windows() -> list[MacCandidate]:
    command = (
        "[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
        "@(Get-NetAdapter | Where-Object {$_.MacAddress} | "
        "Select-Object InterfaceDescription,MacAddress,Status) | ConvertTo-Json -Compress"
    )
    process = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )
    if process.returncode != 0:
        raise LicenseError("LICENSE_MAC_DISCOVERY_FAILED", "Windows network adapter discovery failed")
    try:
        raw = json.loads(process.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise LicenseError("LICENSE_MAC_DISCOVERY_FAILED", "Windows network adapter output was invalid") from exc
    rows = raw if isinstance(raw, list) else [raw]
    result: list[MacCandidate] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("MacAddress"):
            continue
        try:
            normalized = normalize_mac(str(row["MacAddress"]))
        except LicenseError:
            continue
        result.append(
            MacCandidate(str(row.get("InterfaceDescription", "unknown")), normalized, str(row.get("Status", "unknown")))
        )
    return result


def _discover_linux() -> list[MacCandidate]:
    result: list[MacCandidate] = []
    for address_path in sorted(Path("/sys/class/net").glob("*/address")):
        try:
            normalized = normalize_mac(address_path.read_text(encoding="ascii").strip())
        except (OSError, LicenseError):
            continue
        state_path = address_path.parent / "operstate"
        try:
            status = state_path.read_text(encoding="ascii").strip()
        except OSError:
            status = "unknown"
        result.append(MacCandidate(address_path.parent.name, normalized, status))
    return result


def discover_mac_candidates() -> list[MacCandidate]:
    system = platform.system().lower()
    if system == "windows":
        candidates = _discover_windows()
    elif system == "linux":
        candidates = _discover_linux()
    else:
        raise LicenseError("LICENSE_OS_UNSUPPORTED", "MAC discovery supports Windows and Linux only")
    unique = {candidate.mac: candidate for candidate in candidates}
    ordered = sorted(unique.values(), key=lambda item: (item.status.lower() != "up", item.interface, item.mac))
    if not ordered:
        raise LicenseError("LICENSE_MAC_NOT_FOUND", "No usable MAC address was discovered")
    return ordered
