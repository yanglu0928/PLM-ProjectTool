"""Process signals request cooperative Parser shutdown, never resource disposal."""

from contextlib import contextmanager
import signal
from threading import Event, Lock, Thread, current_thread, main_thread

from plm_assistant.modules.parser.application.worker_loop import ParserWorkerLoop


_registration = Lock()
_poisoned = False


@contextmanager
def parser_worker_signals(loop: ParserWorkerLoop):
    global _poisoned
    if (type(loop) is not ParserWorkerLoop or current_thread() is not main_thread()
            or _poisoned or not _registration.acquire(blocking=False)):
        raise RuntimeError("Parser signal adapter unavailable")
    requested = [False]
    halt = Event()
    installed = []
    bridge = None
    clean = True

    def handler(signum, frame):
        requested[0] = True  # No locks, DB, logging or file I/O here.

    def relay():
        while not halt.wait(.05):
            if requested[0]:
                loop.request_stop()
                return

    try:
        numbers = (signal.SIGINT, signal.SIGTERM) + (
            (signal.SIGBREAK,) if hasattr(signal, "SIGBREAK") else ())
        for number in numbers:
            previous = signal.getsignal(number)
            signal.signal(number, handler)
            installed.append((number, previous))
        bridge = Thread(target=relay, name="plm-parser-stop-relay", daemon=False)
        bridge.start()
        yield
    finally:
        halt.set()
        if bridge is not None and bridge.ident is not None:
            bridge.join(timeout=2)
            if bridge.is_alive():
                clean = False
        for number, previous in reversed(installed):
            try:
                signal.signal(number, previous)
            except Exception:
                clean = False
        if not clean:
            _poisoned = True
        _registration.release()
        if not clean:
            raise RuntimeError("Parser signal adapter unavailable; restart required") from None


def run_parser_worker_process(loop: ParserWorkerLoop, *, max_cycles=None):
    if (type(loop) is not ParserWorkerLoop
            or max_cycles is not None and
            (type(max_cycles) is not int or not 1 <= max_cycles <= 100000)):
        raise ValueError("Bounded Parser process required")
    try:
        with parser_worker_signals(loop):
            return loop.run(max_cycles=max_cycles)
    except Exception:
        raise RuntimeError("Parser worker process unavailable") from None
