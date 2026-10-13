"""M2: cascade, cache gate/write amortization, and batch economics."""
from __future__ import annotations
import os as _os
import sys as _sys
from math import isfinite
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from missions._common import load_csv, num
from finops import pricing
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
CACHE_AVG_READS = 10.0
CACHE_WRITE_MULTIPLIER = 1.25

def optimized_request_breakdown(row, avg_cache_reads=CACHE_AVG_READS):
    if not isfinite(avg_cache_reads) or avg_cache_reads < 0:
        raise ValueError("avg_cache_reads must be non-negative")
    inp = int(num(row["input_tokens"]))
    out = int(num(row["output_tokens"]))
    cached = min(max(0, int(num(row["cached_input_tokens"]))), inp)
    batch = bool(int(num(row["is_batch"])))
    pin, pout = MODEL_PRICES[row["route_tier"]]
    batch_mult = 0.50 if batch else 1.0
    write_per_m = CACHE_WRITE_MULTIPLIER * pin
    use_cache = (
        cached > 0 and avg_cache_reads > 0
        and pricing.cache_is_worth_it(
            avg_cache_reads, write_per_m, pin * batch_mult
        )
    )
    write_usd = cached / 1e6 * write_per_m / avg_cache_reads if use_cache else 0.0
    cost_usd = pricing.request_cost(
        inp, out, pin, pout,
        cached_in=cached if use_cache else 0,
        batch=batch,
    ) + write_usd
    return {"cost_usd": cost_usd, "write_usd": write_usd, "cache_enabled": use_cache}

def run(verbose=True, avg_cache_reads=CACHE_AVG_READS):
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = write_cost = 0.0
    total_tokens = cache_requests = 0
    for row in rows:
        inp = int(num(row["input_tokens"]))
        out = int(num(row["output_tokens"]))
        total_tokens += inp + out
        base_cost += pricing.request_cost(inp, out, *MODEL_PRICES["large"])
        bill = optimized_request_breakdown(row, avg_cache_reads)
        opt_cost += bill["cost_usd"]
        write_cost += bill["write_usd"]
        cache_requests += int(bill["cache_enabled"])
    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    if verbose:
        print("== M2 Inference Cost Levers + Cache Economics ==")
        print(f"requests={len(rows)} tokens={total_tokens:,}")
        print(f"baseline:  ${base_cost:.4f}/day ${base_pm:.6f}/1M-token")
        print(f"optimized: ${opt_cost:.4f}/day ${opt_pm:.6f}/1M-token")
        print(f"savings: {pct:.2f}%")
        print(f"Assumed reads/prefix: {avg_cache_reads}")
        print(f"Cache-enabled requests: {cache_requests}")
        print(f"Amortized additional cache writes: ${write_cost:.6f}/day")
    return {
        "baseline_daily_raw": base_cost,
        "optimized_daily_raw": opt_cost,
        "baseline_daily": round(base_cost, 2),
        "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3),
        "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(pct, 1),
        "total_tokens": total_tokens,
        "cache_avg_reads": avg_cache_reads,
        "cache_enabled_requests": cache_requests,
        "cache_write_daily": write_cost,
    }


if __name__ == "__main__":
    run()
