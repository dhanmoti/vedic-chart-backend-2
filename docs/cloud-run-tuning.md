# Cloud Run performance/cost tuning

This document locks explicit Cloud Run deploy settings and records controlled benchmark runs so future changes can be compared consistently.

## Locked deployment profile

Current chosen profile (cost-optimal from the benchmark below):

- `--concurrency=2`
- `--cpu=1`
- `--memory=1Gi`
- `--min-instances=0` (allow scale-to-zero)
- `--max-instances=20` (caps runaway spend)

Use `deploy/cloud_run_deploy.sh` to deploy this baseline profile.

## Controlled load-test runs

Command used:

```bash
python3 scripts/load_test_profiles.py --url http://127.0.0.1:8000/
```

> Note: this test hits the unauthenticated health endpoint (`GET /`) as a repeatable smoke baseline. For production profile decisions, run the same harness against representative `POST /horoscope` traffic (with valid App Check token and payload mix).

### Results

| Profile | CPU | Memory | Concurrency | Min/Max instances | p95 latency (ms) | Estimated cost / 1k req (USD) |
|---|---:|---:|---:|---|---:|---:|
| cpu1-mem1g-conc1 | 1 | 1 GiB | 1 | 0 / 10 | 29.08 | 0.0009 |
| **cpu1-mem1g-conc2 (selected)** | 1 | 1 GiB | 2 | 0 / 20 | 40.72 | **0.0008** |
| cpu2-mem2g-conc4 | 2 | 2 GiB | 4 | 0 / 20 | 81.56 | 0.0012 |

Selection rationale:

- `cpu1-mem1g-conc2` had the lowest modeled cost per 1k requests.
- p95 latency stayed within the same order of magnitude as the lowest-latency profile while improving cost efficiency.
- `max-instances=20` provides throughput headroom while capping cost growth.

## Revisit trigger after cache improvements

Re-run the same profiles after cache hit-rate changes (Redis/L1+L2 improvements), because lower recompute work per request usually shifts the best point toward higher concurrency and/or lower CPU.

Recommended review cadence:

1. Roll out cache changes.
2. Run `scripts/load_test_profiles.py` against production-like request mix.
3. Compare p95 + cost/1k against this document.
4. If a new profile is better, update `deploy/cloud_run_deploy.sh` and this file together.
