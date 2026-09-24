"""Exact Host/Origin gate for browser credential submission."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable


_ORIGIN = re.compile(
    r"(?P<scheme>https?)://(?P<host>[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])"
    r"(?::(?P<port>[0-9]{1,5}))?\Z",
    re.ASCII,
)


class LoginOriginError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("AUTH_CSRF_INVALID")


def _parse_origin(value: str) -> tuple[str, str]:
    if type(value) is not str or len(value) > 256:
        raise LoginOriginError()
    match = _ORIGIN.fullmatch(value)
    if match is None:
        raise LoginOriginError()
    scheme, host, port = match.group("scheme", "host", "port")
    if port is not None and not 1 <= int(port) <= 65_535:
        raise LoginOriginError()
    canonical_host = host.lower()
    if scheme == "http":
        bare = canonical_host[1:-1] if canonical_host.startswith("[") else canonical_host
        try:
            loopback = ipaddress.ip_address(bare).is_loopback
        except ValueError:
            loopback = bare == "localhost"
        if not loopback:
            raise LoginOriginError()
    authority = canonical_host + (f":{port}" if port is not None else "")
    return f"{scheme}://{authority}", authority


class LoginOriginPolicy:
    """Configured origin is authoritative; forwarded headers are never trusted."""

    def __init__(self, allowed_origins: Iterable[str]) -> None:
        if allowed_origins is None:
            raise ValueError("trusted origins are required")
        try:
            parsed = {_parse_origin(origin) for origin in allowed_origins}
        except (LoginOriginError, TypeError) as exc:
            raise ValueError("invalid trusted origin configuration") from exc
        if not parsed or len(parsed) > 16:
            raise ValueError("one to sixteen trusted origins are required")
        self._allowed = frozenset(parsed)

    def require_trusted(self, headers: Iterable[tuple[bytes, bytes]]) -> None:
        hosts, origins = [], []
        try:
            for name, value in headers:
                if name.lower() == b"host":
                    hosts.append(value.decode("ascii"))
                elif name.lower() == b"origin":
                    origins.append(value.decode("ascii"))
        except (AttributeError, TypeError, UnicodeDecodeError):
            raise LoginOriginError() from None
        if len(hosts) != 1 or len(origins) != 1:
            raise LoginOriginError()
        canonical, authority = _parse_origin(origins[0])
        if (canonical, authority) not in self._allowed or hosts[0].lower() != authority:
            raise LoginOriginError()
