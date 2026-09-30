"""Windows SCM host for independently verified API and Worker roles."""

from __future__ import annotations

import asyncio
import ipaddress
import sys
from contextlib import ExitStack
from pathlib import Path
from threading import Event, Thread
from time import sleep
from typing import Callable

from plm_assistant.modules.platform.infrastructure.windows_service_dispatcher import (
    WindowsServiceDispatcherError, run_windows_service,
)


class WindowsApiServiceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_API_SERVICE_UNAVAILABLE")


class WindowsAuditServiceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_AUDIT_SERVICE_UNAVAILABLE")


class WindowsParserServiceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("WINDOWS_PARSER_SERVICE_UNAVAILABLE")


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


def run_audit_loop_service(database: object, loop: object, data_root: Path,
                           stop_event: Event,
                           ready: Callable[[], None]) -> None:
    """Retain STOP_PENDING until the loop, heartbeat and DB are quiescent."""
    if (type(stop_event) is not Event or not callable(ready)
            or not isinstance(data_root, Path) or not data_root.is_absolute()):
        raise WindowsAuditServiceError()
    from plm_assistant.modules.platform.infrastructure.runtime_process_identity import (
        register_runtime_process,
    )

    relay_halt = Event()

    def relay_stop() -> None:
        while not relay_halt.wait(.05):
            if stop_event.is_set():
                loop.request_stop()
                return

    relay = Thread(target=relay_stop, name="plm-audit-scm-stop", daemon=False)
    with ExitStack() as stack:
        try:
            stack.enter_context(register_runtime_process("AUDIT_WORKER", data_root))
            relay.start()
            ready()
            result = loop.run(stop_requested=stop_event.is_set)
            if result.reason != "STOPPED" or not stop_event.is_set():
                raise WindowsAuditServiceError()
        finally:
            # An uncertain heartbeat must never become a clean SCM STOPPED.
            try:
                loop.request_stop()
            except Exception:
                pass
            relay_halt.set()
            if relay.ident is not None:
                relay.join()
            while True:
                try:
                    with loop.quiescent():
                        database.dispose()
                    break
                except Exception:
                    sleep(.05)


def run_audit_service(settings_path: Path, stop_event: Event,
                      ready: Callable[[], None]) -> None:
    if (sys.platform != "win32" or not isinstance(settings_path, Path)
            or not settings_path.is_absolute()):
        raise WindowsAuditServiceError()
    from plm_assistant.entrypoints.worker_windows import create_windows_audit_worker
    from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
        load_bootstrap_settings,
    )

    settings = load_bootstrap_settings(settings_path.resolve(strict=True))
    database, loop = create_windows_audit_worker(settings)
    run_audit_loop_service(database, loop, settings.data_root, stop_event, ready)


def run_parser_loop_service(database: object, loop: object, data_root: Path,
                            stop_event: Event,
                            ready: Callable[[], None]) -> None:
    """Stop cooperatively and retain the process until OCR/heartbeat quiesce."""
    if (type(stop_event) is not Event or not callable(ready)
            or not isinstance(data_root, Path) or not data_root.is_absolute()):
        raise WindowsParserServiceError()
    from plm_assistant.modules.platform.infrastructure.runtime_process_identity import (
        register_runtime_process,
    )

    relay_halt = Event()

    def relay_stop() -> None:
        while not relay_halt.wait(.05):
            if stop_event.is_set():
                loop.request_stop()
                return

    relay = Thread(target=relay_stop, name="plm-parser-scm-stop", daemon=False)
    with ExitStack() as stack:
        try:
            stack.enter_context(register_runtime_process("PARSER_WORKER", data_root))
            relay.start()
            ready()
            result = loop.run()
            if result.reason != "STOPPED" or not stop_event.is_set():
                raise WindowsParserServiceError()
        finally:
            try:
                loop.request_stop()
            except Exception:
                pass
            relay_halt.set()
            if relay.ident is not None:
                relay.join()
            while True:
                try:
                    with loop.quiescent():
                        database.dispose()
                    break
                except Exception:
                    sleep(.05)


def run_parser_service(settings_path: Path, stop_event: Event,
                       ready: Callable[[], None]) -> None:
    if (sys.platform != "win32" or not isinstance(settings_path, Path)
            or not settings_path.is_absolute()):
        raise WindowsParserServiceError()
    from plm_assistant.entrypoints.parser_worker_windows import create_windows_parser_worker
    from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
        load_bootstrap_settings,
    )

    settings = load_bootstrap_settings(settings_path.resolve(strict=True))
    database, loop = create_windows_parser_worker(settings)
    run_parser_loop_service(database, loop, settings.data_root, stop_event, ready)


def main() -> int:
    if (sys.platform != "win32" or len(sys.argv) != 3
            or sys.argv[1] not in ("API", "AUDIT_WORKER", "PARSER_WORKER")
            or not Path(sys.argv[2]).is_absolute()):
        print("Usage: python -m plm_assistant.entrypoints.service_windows "
              "{API|AUDIT_WORKER|PARSER_WORKER} <absolute-bootstrap.yaml>",
              file=sys.stderr)
        return 2
    try:
        role = sys.argv[1]
        settings_path = Path(sys.argv[2])
        runner = {"API": run_api_service, "AUDIT_WORKER": run_audit_service,
                  "PARSER_WORKER": run_parser_service}[role]
        run_windows_service(role, lambda stop, ready:
            runner(settings_path, stop, ready))
        return 0
    except WindowsServiceDispatcherError:
        print("Windows service unavailable; SCM lifecycle rejected.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
