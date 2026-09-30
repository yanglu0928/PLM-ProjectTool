"""Windows SCM host: API role only until Worker runners are independently verified."""

from __future__ import annotations

import asyncio
import ipaddress
import sys
from pathlib import Path
from threading import Event
from typing import Callable

from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    WindowsServiceDispatcherError, run_windows_service,
)


class WindowsApiServiceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_API_SERVICE_UNAVAILABLE")


def run_uvicorn_service(app_factory: Callable[[], object], *, host: str,
                        port: int, data_root: Path, log_level: str,
                        stop_event: Event, ready: Callable[[], None]) -> None:
    """Announce readiness only after lifespan startup and socket bind."""
    if (not callable(app_factory) or not callable(ready)
            or type(stop_event) is not Event or not isinstance(data_root, Path)
            or not data_root.is_absolute() or type(port) is not int
            or not 0 <= port <= 65535 or type(log_level) is not str):
        raise WindowsApiServiceError()
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise WindowsApiServiceError()
    except ValueError:
        raise WindowsApiServiceError() from None

    # Delayed imports keep SCM dispatcher startup independent of heavy app imports.
    import uvicorn
    from plm_assistant.modules.platform.infrastructure.runtime_process_identity import (
        register_runtime_process,
    )

    with register_runtime_process("API", data_root):
        app = app_factory()
        server = uvicorn.Server(uvicorn.Config(
            app, host=host, port=port, log_level=log_level,
            workers=1, proxy_headers=False, forwarded_allow_ips=""))

        async def supervise() -> None:
            task = asyncio.create_task(server.serve())
            announced = False
            try:
                while not task.done():
                    if stop_event.is_set():
                        server.should_exit = True
                    elif server.started and not announced:
                        ready()
                        announced = True
                    await asyncio.sleep(.025)
                await task
                if not announced or not stop_event.is_set():
                    raise WindowsApiServiceError()
            finally:
                if not task.done():
                    server.should_exit = True
                    await task

        asyncio.run(supervise())


def run_api_service(settings_path: Path, stop_event: Event,
                    ready: Callable[[], None]) -> None:
    if (sys.platform != "win32" or not isinstance(settings_path, Path)
            or not settings_path.is_absolute()):
        raise WindowsApiServiceError()
    from plm_assistant.entrypoints.production_login import (
        create_production_platform_write_app,
    )
    from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
        load_bootstrap_settings,
    )

    settings = load_bootstrap_settings(settings_path.resolve(strict=True))
    run_uvicorn_service(lambda: create_production_platform_write_app(settings),
        host=settings.bind_host, port=settings.bind_port,
        data_root=settings.data_root, log_level=settings.log_level.value.lower(),
        stop_event=stop_event, ready=ready)


def main() -> int:
    if (sys.platform != "win32" or len(sys.argv) != 3
            or sys.argv[1] != "API" or not Path(sys.argv[2]).is_absolute()):
        print("Usage: python -m plm_assistant.entrypoints.service_windows "
              "API <absolute-bootstrap.yaml>", file=sys.stderr)
        return 2
    try:
        settings_path = Path(sys.argv[2])
        run_windows_service("API", lambda stop, ready:
            run_api_service(settings_path, stop, ready))
        return 0
    except WindowsServiceDispatcherError:
        print("Windows API service unavailable; SCM lifecycle rejected.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
