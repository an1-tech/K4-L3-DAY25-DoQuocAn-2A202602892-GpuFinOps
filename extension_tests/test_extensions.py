"""Additional behavioral checks. The original tests/ directory is unchanged."""
import csv
import math

import pytest

from finops import pricing
from missions import carbon_scheduling, lab_analysis
from missions.m2_inference_levers import optimized_request_breakdown, run


@pytest.mark.parametrize("reads,write,price,expected", [
    (1, 0.25, 0.20, False),
    (2, 0.25, 0.20, True),
    (2, 0.25, 0.10, False),
    (3, 0.25, 0.10, True),
    (2, 1.80, 1.0, True),  # Exactly break-even.
    (1, 0.0, 0.20, True),
])
def test_cache_gate_boundary(reads, write, price, expected):
    assert pricing.cache_is_worth_it(reads, write, price) is expected


@pytest.mark.parametrize("args", [
    (-1, 0.25, 0.20, 0.1),
    (1, -0.25, 0.20, 0.1),
    (1, 0.25, -0.20, 0.1),
    (1, 0.25, 0.20, -0.1),
    (1, 0.25, 0.20, 1.1),
    (math.nan, 0.25, 0.20, 0.1),
    (1, math.inf, 0.20, 0.1),
])
def test_cache_gate_rejects_invalid_economics(args):
    with pytest.raises(ValueError):
        pricing.cache_is_worth_it(*args)


def request(batch="0", cached="800"):
    return {
        "input_tokens": "1000", "output_tokens": "200",
        "cached_input_tokens": cached, "is_batch": batch, "route_tier": "small",
    }


def test_low_reuse_skips_write_and_cached_read_discount():
    bill = optimized_request_breakdown(request(), avg_cache_reads=1)
    assert not bill["cache_enabled"]
    assert bill["write_usd"] == 0
    assert bill["cost_usd"] == pytest.approx(0.00028)


def test_cache_write_is_amortized_but_not_batch_discounted():
    regular = optimized_request_breakdown(request(), avg_cache_reads=10)
    batch = optimized_request_breakdown(request(batch="1"), avg_cache_reads=10)
    assert regular["write_usd"] == pytest.approx(0.00002)
    assert batch["write_usd"] == pytest.approx(regular["write_usd"])
    assert batch["cost_usd"] == pytest.approx(0.000088)
    assert regular["cost_usd"] == pytest.approx(0.000156)


def test_batch_changes_break_even_gate():
    assert not optimized_request_breakdown(request(batch="1"), 2)["cache_enabled"]
    assert optimized_request_breakdown(request(batch="1"), 3)["cache_enabled"]


@pytest.mark.parametrize("reads,cached", [(0, "800"), (10, "0")])
def test_no_reuse_or_no_cacheable_input_has_no_write_charge(reads, cached):
    bill = optimized_request_breakdown(request(cached=cached), reads)
    assert not bill["cache_enabled"]
    assert bill["write_usd"] == 0


def test_cached_tokens_cannot_exceed_input():
    clamped = optimized_request_breakdown(request(cached="9999"), 10)
    full_input = optimized_request_breakdown(request(cached="1000"), 10)
    assert clamped == full_input


def test_cache_decision_is_invariant_under_price_scale():
    for reads in [1, 2, 10]:
        assert pricing.cache_is_worth_it(reads, 0.25, 0.20) == pricing.cache_is_worth_it(reads, 3.75, 3.00)


def test_allocation_and_breakdown_reconcile_with_inference():
    evidence = lab_analysis.collect()
    result = run(verbose=False)
    assert sum(r["cost_daily_usd"] for r in evidence["by_team"]) == pytest.approx(result["optimized_daily_raw"])
    assert sum(r["cost_daily_usd"] for r in evidence["reasoning_groups"]) == pytest.approx(result["optimized_daily_raw"])
    stages = evidence["stages"]
    assert sum(r["incremental_savings_daily_usd"] for r in stages) == pytest.approx(
        result["baseline_daily_raw"] - result["optimized_daily_raw"]
    )
    low = next(r for r in evidence["cache_scenarios"] if r["assumed_reads_per_prefix"] == 1)
    assert low["cache_enabled_requests"] == 0
    assert result["optimized_daily_raw"] < low["cost_daily_usd"]
    assert result["optimized_daily_raw"] > evidence["legacy_read_only_daily"]


def test_carbon_uses_actual_days_and_gpu_count(monkeypatch):
    jobs = [{
        "job_id": "short-job", "gpu_type": "sample",
        "hours_per_day": "2", "days": "3", "num_gpus": "4", "interruptible": "1",
    }, {
        "job_id": "not-movable", "gpu_type": "sample",
        "hours_per_day": "24", "days": "30", "num_gpus": "99", "interruptible": "0",
    }]
    monkeypatch.setattr(carbon_scheduling, "load_csv", lambda _: jobs)
    monkeypatch.setattr(carbon_scheduling, "catalog_by_type", lambda: {"sample": {"watts": "100"}})
    result = carbon_scheduling.run(verbose=False, write_outputs=False)
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["gpu_hours"] == 24
    assert result["total_wh"] == 2400
    assert result["before_g"] == pytest.approx(912)
    assert result["after_g"] == pytest.approx(72)
    assert result["saved_g"] == pytest.approx(840)


def test_carbon_keeps_work_constant_across_regions():
    result = carbon_scheduling.run(verbose=False, write_outputs=False)
    for region in result["regions"]:
        assert region["carbon_g"] / region["gco2_per_kwh"] == pytest.approx(result["total_wh"] / 1000)
        assert region["electricity_usd"] / region["usd_per_kwh"] == pytest.approx(result["total_wh"] / 1000)
    assert result["saved_g"] == pytest.approx(result["before_g"] - result["after_g"])
    assert result["cleanest_region"] != result["cheapest_region"]


def test_carbon_empty_selection_exports_valid_headers(monkeypatch, tmp_path):
    monkeypatch.setattr(carbon_scheduling, "load_csv", lambda _: [])
    monkeypatch.setattr(carbon_scheduling, "catalog_by_type", lambda: {})
    monkeypatch.setattr(carbon_scheduling, "ROOT", tmp_path)
    result = carbon_scheduling.run(verbose=False, write_outputs=True)
    assert result["total_wh"] == result["saved_g"] == result["savings_pct"] == 0
    with (tmp_path / "outputs" / "carbon_jobs.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert "carbon_saved_g" in reader.fieldnames
        assert list(reader) == []
