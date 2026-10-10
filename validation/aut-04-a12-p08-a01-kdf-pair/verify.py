"""Synthetic, fixed-profile KDF scheduling diagnostic; not HTTP acceptance."""
import json
import math
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from time import perf_counter

from plm_assistant.modules.auth.application.password_capacity import PasswordKdfCapacity
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher, PARAMETERS


def run(mode, round_number, old, new, source):
    hasher = ScryptPasswordHasher()
    capacity = PasswordKdfCapacity(slots=16)
    barrier = Barrier(21)
    lock = Lock()
    counts = {"verify": 0, "hash": 0}
    waits = []

    def compute(kind):
        before = perf_counter()
        assert capacity.acquire(timeout=5) is True
        try:
            with lock:
                waits.append((perf_counter() - before) * 1000)
                counts[kind] += 1
            if kind == "verify":
                with memoryview(old) as view:
                    return hasher.verify_password(view, password_hash=source.password_hash,
                        algorithm_id=source.algorithm_id, parameter_set=source.parameter_set)
            with memoryview(new) as view:
                return hasher.hash_password(view)
        finally:
            capacity.release()

    with ThreadPoolExecutor(max_workers=16) as workers, ThreadPoolExecutor(max_workers=20) as clients:
        # Start calculator threads before the measured simultaneous release.
        ready = Barrier(17)
        warm = [workers.submit(ready.wait) for _ in range(16)]
        ready.wait()
        for future in warm:
            future.result()

        def request():
            barrier.wait()
            start = perf_counter()
            if mode == "sequential":
                matched = compute("verify")
                assert matched is True
                hashed = compute("hash")
            else:
                verify = workers.submit(compute, "verify")
                hashing = workers.submit(compute, "hash")
                # Both finish before any caller can erase its inputs, even on error.
                try:
                    matched = verify.result()
                finally:
                    hashed = hashing.result()
                assert matched is True
            assert hashed.algorithm_id == "SCRYPT" and hashed.parameter_set == PARAMETERS
            return (perf_counter() - start) * 1000, hashed

        futures = [clients.submit(request) for _ in range(20)]
        start = perf_counter()
        barrier.wait()
        results = [future.result() for future in futures]
        wall = (perf_counter() - start) * 1000
    snapshot = capacity.snapshot()
    assert snapshot["active"] == 0 and snapshot["peak"] <= 16
    assert counts == {"verify": 20, "hash": 20}
    # Verify all derived hashes outside the timed section; no fake success.
    for _, hashed in results:
        with memoryview(new) as view:
            assert hasher.verify_password(view, password_hash=hashed.password_hash,
                algorithm_id=hashed.algorithm_id, parameter_set=hashed.parameter_set) is True
    elapsed = sorted(item[0] for item in results)
    row = {"round": round_number, "mode": mode, "clients": 20,
        "actual_kdf_calls": counts, "capacity": snapshot,
        "wall_ms": round(wall, 3), "p95_ms": round(elapsed[math.ceil(.95 * 20) - 1], 3),
        "min_ms": round(elapsed[0], 3), "max_ms": round(elapsed[-1], 3),
        "max_capacity_wait_ms": round(max(waits), 3), "all_hashes_verified": True,
        "http_acceptance_measured": False}
    print("KDF_PAIR_DIAGNOSTIC " + json.dumps(row, sort_keys=True), flush=True)
    return row


def main():
    # Synthetic constants only; no Vault, database, customer data or credentials.
    old = bytearray(b"Synthetic-old-password-only")
    new = bytearray(b"Synthetic-new-password-only")
    try:
        with memoryview(old) as view:
            source = ScryptPasswordHasher().hash_password(view)
        rows = [run(mode, number, old, new, source)
            for number, modes in ((1, ("sequential", "parallel")), (2, ("parallel", "sequential")))
            for mode in modes]
        print("KDF_PAIR_RESULT " + json.dumps({"diagnostic_pass": True,
            "production_changed": False, "default_slots_unchanged": 4,
            "http_performance_pass": None,
            "parallel_below_1s_both_rounds": all(row["p95_ms"] <= 1000
                for row in rows if row["mode"] == "parallel")}, sort_keys=True), flush=True)
    finally:
        old[:] = b"\x00" * len(old)
        new[:] = b"\x00" * len(new)


if __name__ == "__main__":
    main()
