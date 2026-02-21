#!/usr/bin/env python3
"""Run simple HTTP load tests for candidate Cloud Run profiles.

Example:
  python3 scripts/load_test_profiles.py --url http://127.0.0.1:8000/
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import statistics
import time
import urllib.request
from dataclasses import dataclass

# Cloud Run on-demand pricing assumptions (USD, us-central1 style rates).
VCPU_PER_SEC_USD = 0.000024
MEM_GIB_PER_SEC_USD = 0.0000025
REQUEST_PER_MILLION_USD = 0.40


@dataclass(frozen=True)
class Profile:
    name: str
    cpu: float
    memory_gib: float
    concurrency: int
    min_instances: int
    max_instances: int
    request_count: int
    client_concurrency: int


PROFILES: list[Profile] = [
    Profile("cpu1-mem1g-conc1", cpu=1.0, memory_gib=1.0, concurrency=1, min_instances=0, max_instances=10, request_count=200, client_concurrency=8),
    Profile("cpu1-mem1g-conc2", cpu=1.0, memory_gib=1.0, concurrency=2, min_instances=0, max_instances=20, request_count=200, client_concurrency=16),
    Profile("cpu2-mem2g-conc4", cpu=2.0, memory_gib=2.0, concurrency=4, min_instances=0, max_instances=20, request_count=200, client_concurrency=32),
]


def request_once(url: str, timeout_s: float) -> float:
    started = time.perf_counter()
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status}")
        _ = resp.read()
    return (time.perf_counter() - started) * 1000


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return float("nan")
    idx = math.ceil((p / 100) * len(sorted_values)) - 1
    idx = min(max(idx, 0), len(sorted_values) - 1)
    return sorted_values[idx]


def estimated_cost_per_1k(profile: Profile, avg_latency_ms: float) -> float:
    latency_s = avg_latency_ms / 1000
    instance_seconds_per_req = latency_s / profile.concurrency
    cpu_cost = profile.cpu * instance_seconds_per_req * VCPU_PER_SEC_USD
    mem_cost = profile.memory_gib * instance_seconds_per_req * MEM_GIB_PER_SEC_USD
    request_cost = REQUEST_PER_MILLION_USD / 1_000_000
    return (cpu_cost + mem_cost + request_cost) * 1000


def run_profile(profile: Profile, url: str, timeout_s: float) -> dict:
    latencies: list[float] = []
    failures = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=profile.client_concurrency) as pool:
        futures = [pool.submit(request_once, url, timeout_s) for _ in range(profile.request_count)]
        for f in concurrent.futures.as_completed(futures):
            try:
                latencies.append(f.result())
            except Exception:
                failures += 1

    latencies.sort()
    p95 = percentile(latencies, 95)
    avg = statistics.mean(latencies) if latencies else float("nan")

    return {
        "profile": profile.name,
        "cpu": profile.cpu,
        "memory_gib": profile.memory_gib,
        "concurrency": profile.concurrency,
        "min_instances": profile.min_instances,
        "max_instances": profile.max_instances,
        "requests": profile.request_count,
        "successes": len(latencies),
        "failures": failures,
        "avg_latency_ms": round(avg, 2),
        "p95_latency_ms": round(p95, 2),
        "cost_per_1k_usd": round(estimated_cost_per_1k(profile, avg), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--output", default="docs/load-test-results.json")
    args = parser.parse_args()

    results = [run_profile(profile, args.url, args.timeout_s) for profile in PROFILES]

    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(results, fp, indent=2)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
