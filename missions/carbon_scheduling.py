"""Compare interruptible jobs on equal useful GPU-hours, using actual job days."""
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from missions._common import load_csv, num, catalog_by_type
from finops.sustainability import (
    REGION_CARBON, REGION_PRICE_KWH, carbon_g, energy_cost_usd,
)

def run(verbose=True, write_outputs=True):
    cat = catalog_by_type()
    cleanest = min(REGION_CARBON, key=REGION_CARBON.get)
    cheapest = min(REGION_PRICE_KWH, key=REGION_PRICE_KWH.get)
    eligible = [r for r, intensity in REGION_CARBON.items() if intensity <= 120]
    balanced = min(eligible, key=REGION_PRICE_KWH.get)
    jobs = []
    for job in load_csv("workloads.csv"):
        if int(num(job["interruptible"])) != 1:
            continue
        gpu_hours = num(job["hours_per_day"]) * num(job["days"]) * num(job["num_gpus"])
        wh = gpu_hours * num(cat[job["gpu_type"]]["watts"])
        before = carbon_g(wh, "us-east-1")
        after = carbon_g(wh, cleanest)
        jobs.append({
            "job_id": job["job_id"], "days": int(num(job["days"])),
            "gpu_hours": gpu_hours, "energy_wh": wh,
            "carbon_before_g": before, "carbon_after_g": after,
            "carbon_saved_g": before - after,
        })
    total_wh = sum(j["energy_wh"] for j in jobs)
    regions = [{
        "region": region,
        "usd_per_kwh": REGION_PRICE_KWH[region],
        "gco2_per_kwh": REGION_CARBON[region],
        "electricity_usd": energy_cost_usd(total_wh, region),
        "carbon_g": carbon_g(total_wh, region),
    } for region in REGION_CARBON]
    saved = sum(j["carbon_saved_g"] for j in jobs)
    lines = [
        "## Carbon-aware Scheduling",
        "",
        "Period: actual days in workloads.csv; not a 30-day monthly projection.",
        "Assumptions: constant catalog watts; equal GPU-hours in all regions;",
        "no PUE, transfer costs, spot rework, or GPU rental differences included.",
        "",
        "| Job | GPU-hours | Wh | Before gCO2e | After gCO2e | Saved gCO2e |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for j in jobs:
        lines.append(
            f"| {j['job_id']} | {j['gpu_hours']:.0f} | {j['energy_wh']:.0f} "
            f"| {j['carbon_before_g']:.0f} | {j['carbon_after_g']:.0f} "
            f"| {j['carbon_saved_g']:.0f} |"
        )
    lines += [
        "",
        "| Region | USD/kWh | gCO2e/kWh | Electricity USD | Carbon gCO2e |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in regions:
        lines.append(
            f"| {r['region']} | {r['usd_per_kwh']:.3f} | {r['gco2_per_kwh']} "
            f"| {r['electricity_usd']:.3f} | {r['carbon_g']:.0f} |"
        )
    lines += [
        "",
        f"Total energy: {total_wh:.0f} Wh.",
        f"Total carbon saved at {cleanest}: {saved:.0f} gCO2e.",
        f"Cheapest electricity: {cheapest}. Lowest carbon: {cleanest}.",
        f"Budget rule (assumed): carbon <= 120 gCO2e/kWh, then lowest price: {balanced}.",
        "Check GPU availability, software compatibility, latency, and data residency before migration.",
        "Electricity is not added as an extra saving to the GPU rental savings in M5.",
    ]
    md = "\n".join(lines)
    if write_outputs:
        out = ROOT / "outputs"
        out.mkdir(exist_ok=True)
        for filename, records in [
            ("carbon_jobs.csv", jobs), ("carbon_regions.csv", regions),
        ]:
            with (out / filename).open("w", newline="", encoding="utf-8") as f:
                fields = (list(records[0]) if records else [
                    "job_id", "days", "gpu_hours", "energy_wh",
                    "carbon_before_g", "carbon_after_g", "carbon_saved_g",
                ])
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
        (out / "carbon_extension.md").write_text(md, encoding="utf-8")
    if verbose:
        print(md)
    return {
        "markdown": md, "jobs": jobs, "regions": regions, "saved_g": saved,
        "total_wh": total_wh, "cleanest_region": cleanest,
        "cheapest_region": cheapest, "balanced_region": balanced,
        "before_g": carbon_g(total_wh, "us-east-1"),
        "after_g": carbon_g(total_wh, cleanest),
        "savings_pct": (saved / carbon_g(total_wh, "us-east-1") * 100
                        if total_wh else 0.0),
    }

if __name__ == "__main__":
    run()
