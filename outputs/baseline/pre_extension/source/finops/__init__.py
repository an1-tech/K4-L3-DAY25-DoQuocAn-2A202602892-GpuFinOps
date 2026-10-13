"""finops — the reusable GPU cost-optimization engine for Lab 25.

Modules:
  metrics        MFU / MBU / roofline / GPU-Util-lie detection
  pricing        $/1M-token, discount stack, break-even, tier choice, spot-checkpoint sim
  allocation     cost-by-tag, tag coverage, showback->chargeback gate, FOCUS export
  sustainability Wh/query, carbon, tokens-per-watt
  report         baseline-vs-optimized report + savings waterfall
"""
from . import metrics, pricing, allocation, sustainability, report  # noqa: F401

__all__ = ["metrics", "pricing", "allocation", "sustainability", "report"]
