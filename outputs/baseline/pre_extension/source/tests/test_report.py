import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import report


def test_build_report_has_savings():
    md = report.build_report(100000, 25000, {"batching": 40000, "caching": 35000})
    assert "75%" in md and "Projected savings" in md and "batching" in md
