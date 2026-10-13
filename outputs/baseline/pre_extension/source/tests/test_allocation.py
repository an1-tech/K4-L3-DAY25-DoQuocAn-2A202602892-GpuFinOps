import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import allocation


def test_cost_by_tag():
    rows = [{"team": "a", "cost": 10}, {"team": "a", "cost": 5}, {"team": "b", "cost": 2}]
    by = allocation.cost_by_tag(rows, "team")
    assert by["a"] == 15 and by["b"] == 2


def test_tag_coverage_and_gate():
    rows = [{"team": "a", "project": "x"}, {"team": "", "project": "y"}]
    cov = allocation.tag_coverage(rows, ["team", "project"])
    assert abs(cov - 0.5) < 1e-9
    assert allocation.chargeback_ready(0.85) is True
    assert allocation.chargeback_ready(0.5) is False


def test_focus_rows():
    rows = [{"team": "a", "project": "x", "cost": 1.23, "gpu_id": "g0"}]
    focus = allocation.to_focus_rows(rows)
    assert focus[0]["ServiceCategory"] == "AI and Machine Learning"
    assert focus[0]["BilledCost"] == 1.23 and focus[0]["Tags"]["team"] == "a"
