## Carbon-aware Scheduling

Period: actual days in workloads.csv; not a 30-day monthly projection.
Assumptions: constant catalog watts; equal GPU-hours in all regions;
no PUE, transfer costs, spot rework, or GPU rental differences included.

| Job | GPU-hours | Wh | Before gCO2e | After gCO2e | Saved gCO2e |
|---|---:|---:|---:|---:|---:|
| job-train-llm | 2240 | 1568000 | 595840 | 47040 | 548800 |
| job-train-embed | 200 | 80000 | 30400 | 2400 | 28000 |
| job-finetune | 36 | 25200 | 9576 | 756 | 8820 |
| job-dev-sandbox | 352 | 52800 | 20064 | 1584 | 18480 |
| job-batch-eval | 90 | 63000 | 23940 | 1890 | 22050 |

| Region | USD/kWh | gCO2e/kWh | Electricity USD | Carbon gCO2e |
|---|---:|---:|---:|---:|
| us-east-1 | 0.120 | 380 | 214.680 | 679820 |
| us-west-2 | 0.070 | 120 | 125.230 | 214680 |
| europe-north1 | 0.090 | 30 | 161.010 | 53670 |
| europe-central2 | 0.180 | 660 | 322.020 | 1180740 |
| us-east-wa | 0.055 | 90 | 98.395 | 161010 |

Total energy: 1789000 Wh.
Total carbon saved at europe-north1: 626150 gCO2e.
Cheapest electricity: us-east-wa. Lowest carbon: europe-north1.
Budget rule (assumed): carbon <= 120 gCO2e/kWh, then lowest price: us-east-wa.
Check GPU availability, software compatibility, latency, and data residency before migration.
Electricity is not added as an extra saving to the GPU rental savings in M5.