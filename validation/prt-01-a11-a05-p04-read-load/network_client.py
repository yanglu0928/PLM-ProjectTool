"""Separate-process synthetic HTTP client for one isolated local verifier."""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import sys
import time

import httpx


async def main(payload: dict) -> dict:
    base_url = payload["base_url"]
    if not (type(base_url) is str and base_url.startswith("http://127.0.0.1:")):
        raise ValueError("isolated loopback URL required")
    prefix, headers = payload["prefix"], payload["headers"]
    items = ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE")
    times: dict[str, dict[str, float]] = {}
    clock_probe = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=base_url, timeout=30.0, trust_env=False,
    ) as client:
        async def round_of(url: str, group: str, round_no: int,
                           request_headers: dict[str, str],
                           *, expect_business: bool) -> float:
            ready = asyncio.Event()

            async def one(index: int) -> float:
                await ready.wait()
                probe_id = f"{group}:{round_no}:{index}"
                marks = times.setdefault(probe_id, {})
                started = marks["client_start"] = time.perf_counter()
                response = await client.get(
                    url, headers={**request_headers, "x-prt-probe-id": probe_id},
                )
                finished = marks["client_end"] = time.perf_counter()
                assert response.status_code == 200
                if expect_business:
                    assert response.headers["etag"] == '"v10"'
                    assert response.json()["data"]["stage_key"] == "PROTOTYPE"
                return (finished - started) * 1000

            tasks = [asyncio.create_task(one(index)) for index in range(20)]
            ready.set()
            samples = sorted(await asyncio.gather(*tasks))
            return samples[math.ceil(.95 * len(samples)) - 1]

        health = [await round_of("/health/live", "HEALTH", round_no, {},
                                 expect_business=False)
                  for round_no in range(1, 4)]
        metrics = {}
        for item in items:
            url = f"{prefix}/checklist-items/{item}/qualification"
            warm = await client.get(url, headers=headers)
            assert warm.status_code == 200
            rounds = [await round_of(url, item, round_no, headers,
                                     expect_business=True)
                      for round_no in range(1, 4)]
            metrics[item] = statistics.median(rounds)
    return {"clock_probe": clock_probe, "health": statistics.median(health),
            "metrics": metrics, "times": times}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main(json.load(sys.stdin)))))
