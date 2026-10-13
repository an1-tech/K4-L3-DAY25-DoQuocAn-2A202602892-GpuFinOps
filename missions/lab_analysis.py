"""Reproducible lab evidence and Vietnamese interpretation; no cloud calls."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from missions._common import ROOT, load_csv, catalog_by_type, num
from missions.m2_inference_levers import (
    MODEL_PRICES, CACHE_AVG_READS, CACHE_WRITE_MULTIPLIER,
    optimized_request_breakdown, run as inference_run,
)
from finops import allocation, pricing, sustainability


def table(headers, rows):
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(map(str, row)) + " |" for row in rows)
    return "\n".join(lines)


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def collect():
    rows = load_csv("token_usage.csv")
    total_tokens = sum(int(num(r["input_tokens"])) + int(num(r["output_tokens"])) for r in rows)
    costs = dict.fromkeys([
        "Baseline: large, no cache, no batch",
        "Cascade",
        "Cascade + cache gate (reads only)",
        "Cascade + cache gate + batch (reads only)",
        "Optimized including amortized writes",
    ], 0.0)
    legacy_cost = 0.0
    priced = []
    for row in rows:
        inp, out = int(num(row["input_tokens"])), int(num(row["output_tokens"]))
        pin, pout = MODEL_PRICES[row["route_tier"]]
        batch = bool(int(num(row["is_batch"])))
        cached = int(num(row["cached_input_tokens"]))
        bill = optimized_request_breakdown(row)
        no_batch = optimized_request_breakdown(dict(row, is_batch="0"))
        keys = list(costs)
        costs[keys[0]] += pricing.request_cost(inp, out, *MODEL_PRICES["large"])
        costs[keys[1]] += pricing.request_cost(inp, out, pin, pout)
        costs[keys[2]] += no_batch["cost_usd"] - no_batch["write_usd"]
        costs[keys[3]] += bill["cost_usd"] - bill["write_usd"]
        costs[keys[4]] += bill["cost_usd"]
        legacy_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=batch)
        priced.append(dict(
            row, cost=bill["cost_usd"], total_tokens=inp + out,
            wh=sustainability.wh_per_query(inp + out, is_reasoning=bool(int(row["is_reasoning"]))),
        ))

    stages = []
    previous = None
    for stage, cost in costs.items():
        stages.append({
            "stage": stage, "cost_daily_usd": cost,
            "usd_per_million_tokens": pricing.dollars_per_million(cost, total_tokens),
            "incremental_savings_daily_usd": 0.0 if previous is None else previous - cost,
        })
        previous = cost

    scenarios = []
    for reads in [0.0, 1.0, 2.0, 3.0, 10.0]:
        result = inference_run(verbose=False, avg_cache_reads=reads)
        scenarios.append({
            "assumed_reads_per_prefix": reads,
            "cost_daily_usd": result["optimized_daily_raw"],
            "usd_per_million_tokens": pricing.dollars_per_million(result["optimized_daily_raw"], total_tokens),
            "write_daily_usd": result["cache_write_daily"],
            "cache_enabled_requests": result["cache_enabled_requests"],
            "savings_pct": (1 - result["optimized_daily_raw"] / result["baseline_daily_raw"]) * 100,
        })

    by_team = allocation.cost_by_tag(priced, "team")
    total_cost = sum(by_team.values())
    teams = [{
        "team": team, "cost_daily_usd": cost, "cost_share_pct": cost / total_cost * 100,
    } for team, cost in sorted(by_team.items(), key=lambda item: -item[1])]
    coverage = allocation.tag_coverage(priced, ["team", "project"])
    groups = []
    total_wh = sum(row["wh"] for row in priced)
    for flag in [0, 1]:
        subset = [row for row in priced if int(row["is_reasoning"]) == flag]
        cost = sum(row["cost"] for row in subset)
        wh = sum(row["wh"] for row in subset)
        tokens = sum(row["total_tokens"] for row in subset)
        groups.append({
            "is_reasoning": flag, "requests": len(subset),
            "request_share_pct": len(subset) / len(priced) * 100,
            "tokens": tokens, "token_share_pct": tokens / total_tokens * 100,
            "cost_daily_usd": cost, "cost_share_pct": cost / total_cost * 100,
            "energy_wh": wh, "energy_share_pct": wh / total_wh * 100,
        })

    cat = catalog_by_type()
    thresholds = []
    for tier, (pin, _) in MODEL_PRICES.items():
        for batch in [False, True]:
            denominator = pin * (0.5 if batch else 1.0) * 0.90
            thresholds.append({
                "model_tier": tier, "batch": int(batch),
                "input_price_per_m": pin, "additional_write_price_per_m": CACHE_WRITE_MULTIPLIER * pin,
                "break_even_reads": CACHE_WRITE_MULTIPLIER * pin / denominator,
            })
    files = ["price_catalog.csv", "gpu_telemetry.csv", "token_usage.csv", "workloads.csv"]
    return {
        "data_rows": {name: len(load_csv(name)) for name in files},
        "data_sha256": {
            name: hashlib.sha256((Path(ROOT) / "data" / name).read_bytes()).hexdigest() for name in files
        },
        "total_tokens": total_tokens, "stages": stages, "cache_scenarios": scenarios,
        "cache_thresholds": thresholds, "legacy_read_only_daily": legacy_cost,
        "by_team": teams, "tag_coverage": coverage,
        "chargeback_ready": allocation.chargeback_ready(coverage),
        "reasoning_groups": groups, "traffic_energy_wh": total_wh,
        "traffic_energy_per_query_wh": total_wh / len(rows),
        "fleet_on_demand_daily": sum(
            num(cat[gtype]["on_demand_hr"]) * 24
            for gtype in {row["gpu_id"]: row["gpu_type"] for row in load_csv("gpu_telemetry.csv")}.values()
        ),
    }


def report_sections(evidence, r1, r2, r3, levers):
    e = evidence
    highest = max(r1["summary"], key=lambda row: row["gpu_util_pct"])
    largest = max(levers, key=levers.get)
    lines = [
        "## Phạm vi và khả năng tái lập",
        "",
        "Dữ liệu tổng hợp seed=25; giá và hệ số điện/carbon là snapshot minh họa của lab.",
        "Không sử dụng GPU thật, cloud account hoặc API key.",
        "M3/M5 quy đổi 30 ngày; extension carbon dùng days thực tế của từng job.",
        "",
        table(["CSV", "Số dòng"], [[name, count] for name, count in e["data_rows"].items()]),
        "",
        "## Inference unit economics",
        "",
        table(["Chỉ tiêu", "Baseline", "Optimized"], [
            ["USD/ngày", f'{r2["baseline_daily_raw"]:.6f}', f'{r2["optimized_daily_raw"]:.6f}'],
            ["USD/1M-token", f'{r2["baseline_per_m"]:.3f}', f'{r2["optimized_per_m"]:.3f}'],
        ]),
        "",
        f'Tổng token/ngày: {e["total_tokens"]:,}; tổng input + output, không cộng cached input lần hai.',
        "USD/1M-token ở đây chỉ bao gồm inference, không chia chi phí training vào sản lượng inference.",
        "",
        "### Đóng góp theo thứ tự cascade → cache → batch → phí ghi",
        "",
        table(["Giai đoạn", "USD/ngày", "USD/1M-token", "Savings thêm USD/ngày"], [
            [r["stage"], f'{r["cost_daily_usd"]:.6f}', f'{r["usd_per_million_tokens"]:.6f}',
             f'{r["incremental_savings_daily_usd"]:.6f}'] for r in e["stages"]
        ]),
        "",
        "Cascade đóng góp lớn nhất trong inference. Phần đóng góp phụ thuộc thứ tự áp dụng.",
        "Phí ghi làm savings giảm, nên dòng cuối có incremental savings âm.",
        "Batch phù hợp cho eval/xử lý nền; không áp dụng tùy ý cho chat cần phản hồi ngay.",
        "0.50 × 0.10 = 0.05 là mô hình chiết khấu input; output không tự được giảm 90% bởi cache.",
        "",
        "## Extension 3 — Cache economics",
        "",
        f"Giả định mặc định: {CACHE_AVG_READS:g} reads/prefix; phí ghi BỔ SUNG = {CACHE_WRITE_MULTIPLIER:g} × giá input.",
        "Phí ghi nằm ngoài chi phí request thông thường, không hưởng giảm giá batch và được phân bổ đều cho reads.",
        "Giả định mỗi prefix được tái sử dụng trong cùng model/điều kiện batch.",
        "CSV không có prefix_id hoặc reads/prefix: các reads dưới đây là kịch bản, không phải số đo.",
        "",
        "Hòa vốn: n × P × B × (1 − 0.10) >= W, với W là phí ghi bổ sung USD/1M token.",
        "",
        table(["Model", "Batch", "P USD/1M", "W USD/1M", "Reads hòa vốn"], [
            [r["model_tier"], r["batch"], f'{r["input_price_per_m"]:.2f}',
             f'{r["additional_write_price_per_m"]:.2f}', f'{r["break_even_reads"]:.6f}']
            for r in e["cache_thresholds"]
        ]),
        "",
        "Cần ít nhất 2 reads không batch, hoặc 3 reads có batch theo giả định trên.",
        "",
        table(["Reads giả định", "USD/ngày", "USD/1M-token", "Phí ghi USD/ngày", "Request bật cache"], [
            [f'{r["assumed_reads_per_prefix"]:g}', f'{r["cost_daily_usd"]:.6f}',
             f'{r["usd_per_million_tokens"]:.6f}', f'{r["write_daily_usd"]:.6f}',
             r["cache_enabled_requests"]] for r in e["cache_scenarios"]
        ]),
        "",
        f'Mô hình gốc bỏ phí ghi: {e["legacy_read_only_daily"]:.6f} USD/ngày. '
        f'Mô hình đầy đủ: {r2["optimized_daily_raw"]:.6f} USD/ngày.',
        "Không so việc bổ sung một loại chi phí với savings do cải thiện throughput: "
        "đây là điều chỉnh phạm vi tính tiền cho đầy đủ.",
        "",
        "## M1 — Phân tích hiệu quả",
        "",
        table(["GPU", "Util %", "MFU", "MBU", "Idle giờ/ngày"], [
            [r["gpu_id"], r["gpu_util_pct"], r["mfu"], r["mbu"], r["idle_hours"]]
            for r in r1["summary"]
        ]),
        "",
        f'GPU utilization cao nhất: {highest["gpu_id"]}, util={highest["gpu_util_pct"]}%, MFU={highest["mfu"]}.',
        "GPU-Util phản ánh khoảng thời gian GPU hoạt động, không phải tỷ lệ FLOPs đạt được.",
        "Memory stall, kernel nhỏ, đồng bộ hoặc pipeline dữ liệu có thể gây MFU thấp; "
        "dataset không chứng minh nguyên nhân cụ thể, cần profiling.",
        f'GPU bị flag: {", ".join(r["gpu_id"] for r in r1["lies"])}.',
        f'Idle waste: {r1["idle_waste_daily"]:.2f} USD/ngày; {r1["idle_waste_daily"] * 30:.2f} USD/tháng.',
        f'Idle chiếm {r1["idle_waste_daily"] / e["fleet_on_demand_daily"] * 100:.2f}% '
        "chi phí 11 GPU telemetry thuê liên tục 24h/ngày.",
        "Decode có arithmetic intensity thấp nên có thể memory-bound; prefill cao hơn nên có thể compute-bound.",
        "MBU thấp một mình chưa đủ xác nhận memory-bound.",
        "",
        "## M3 — Purchasing",
        "",
        table(["Job", "GPU", "Tier", "On-demand USD/30 ngày", "Optimized USD/30 ngày"], [
            [r["job_id"], r["gpu_type"], r["tier"], r["on_demand"], r["optimized"]]
            for r in r3["recommendations"]
        ]),
        "",
        f'Purchasing savings: {r3["savings_pct"]:.1f}%.',
        "Các job interruptible và chạy dưới 24h/ngày được đề xuất spot; effective hours "
        "cao hơn useful hours do checkpoint 3% và rework theo interruption rate 0.05/giờ.",
        "Inference chạy ổn định được đề xuất reserved. Ngưỡng policy 55% = 13.2h/ngày.",
        "Policy chưa xét độ dài job/cam kết; job ngắn không đủ căn cứ mua reserved 1–3 năm.",
        "M3 tính reserved theo giờ sử dụng thay vì toàn bộ thời gian cam kết, nên chưa phải "
        "phép tính TCO của hợp đồng thật.",
        "",
        "## M4 — Allocation",
        "",
        table(["Team", "USD/ngày", "% chi phí"], [
            [r["team"], f'{r["cost_daily_usd"]:.6f}', f'{r["cost_share_pct"]:.2f}']
            for r in e["by_team"]
        ]),
        "",
        f'Team tốn nhiều nhất: {e["by_team"][0]["team"]}. '
        f'Tag coverage: {e["tag_coverage"] * 100:.2f}%; chargeback ready: {e["chargeback_ready"]}.',
        "Coverage >=80% mở gate theo policy lab; cần xử lý các project còn thiếu trước khi phân bổ thực tế.",
        "M4 và M2 dùng cùng hàm pricing, bao gồm phí ghi cache.",
        "FOCUS-style export là mẫu 50 request, không phải toàn bộ hóa đơn 2.400 request.",
        "Chuẩn hóa trường chi phí giúp tổng hợp đa nhà cung cấp; file mẫu chưa được xác nhận "
        "tuân thủ đầy đủ mọi yêu cầu của chuẩn FOCUS.",
        "",
        "## Sustainability của traffic thực tế",
        "",
        table(["Reasoning", "Requests", "% requests", "Tokens", "USD/ngày", "Wh", "% năng lượng"], [
            [r["is_reasoning"], r["requests"], f'{r["request_share_pct"]:.3f}', r["tokens"],
             f'{r["cost_daily_usd"]:.6f}', f'{r["energy_wh"]:.4f}', f'{r["energy_share_pct"]:.2f}']
            for r in e["reasoning_groups"]
        ]),
        "",
        f'Năng lượng theo mô hình toàn traffic: {e["traffic_energy_wh"]:.4f} Wh/ngày, '
        f'trung bình {e["traffic_energy_per_query_wh"]:.4f} Wh/request.',
        "Mức 0.24 Wh ở snapshot Sustainability đầu báo cáo là query mẫu 800 token, "
        "không phải trung bình traffic.",
        "Hệ số reasoning 80x là giả định hàm wh_per_query; dữ liệu tổng hợp còn có output "
        "reasoning dài hơn. Không coi đây là phép đo điện vật lý.",
        f'Reasoning chiếm {e["reasoning_groups"][1]["request_share_pct"]:.3f}% request, '
        "đã dưới 10%; cap 10% trên traffic hiện tại không tạo savings.",
        "",
        "## Ưu tiên và giới hạn",
        "",
        f'Lever lớn nhất của M5: {largest}, {levers[largest]:,} USD/tháng.',
        "1. Tắt GPU idle theo lịch/TTL; xác nhận nhu cầu trước khi scale xuống.",
        "2. Duy trì cascade có đánh giá chất lượng; cache theo reads hòa vốn; batch các tác vụ phù hợp.",
        "3. Spot có checkpoint cho job linh hoạt; xác nhận nhu cầu dài hạn trước reserved "
        "và chọn vùng theo ưu tiên chi phí/carbon.",
        "",
        "Right-size util-lies dùng RIGHTSIZE_MAP gốc, chưa có benchmark VRAM/throughput chứng minh savings.",
        "Bốn bucket savings được cộng theo mô phỏng gốc, giả định độc lập. "
        "Nếu telemetry và workloads cùng đại diện một tài nguyên, cần đối soát tránh tính trùng.",
        "M5 dùng các giá trị mission đã làm tròn; bảng chi tiết inference dùng raw totals. "
        "Chênh lệch vài cent là do làm tròn.",
        "Không cộng chi phí điện tiết kiệm vào savings thuê GPU: điện có thể đã nằm trong giá thuê "
        "và kỳ thời gian của extension carbon khác monthly.",
        "",
    ]
    return "\n".join(lines)


def writeup(e, r1, r2, r3, r5, carbon):
    top = e["by_team"][0]
    stages = e["stages"]
    low = next(r for r in e["cache_scenarios"] if r["assumed_reads_per_prefix"] == 1)
    lies_text = "; ".join(
        f'{r["gpu_id"]}: util {r["gpu_util_pct"]:.1f}%, MFU {r["mfu"]:.3f}'
        for r in r1["lies"]
    )
    idle_text = "; ".join(
        f'{r["gpu_id"]} idle {r["idle_hours"]} giờ/ngày'
        for r in r1["summary"] if r["idle_hours"]
    )
    return f"""# GPU FinOps — Đỗ Quốc An — 2A202602892

## Phạm vi và kết quả

Lab chạy thuần Python trên dữ liệu tổng hợp seed=25, không cần GPU/cloud/API key.
Bốn CSV gồm 7 loại GPU, 264 bản ghi telemetry, 2.400 request và 8 workload.
Giá GPU/model, giá điện và carbon là snapshot minh họa của lab, không phải báo giá hiện tại.

Inference baseline là {r2['baseline_daily_raw']:.6f} USD/ngày
({r2['baseline_per_m']:.3f} USD/1M-token); optimized sau tính phí ghi cache là
{r2['optimized_daily_raw']:.6f} USD/ngày ({r2['optimized_per_m']:.3f} USD/1M-token),
giảm {r2['savings_pct']:.1f}% với cùng {r2['total_tokens']:,} input + output token.
USD/1M-token này chỉ tính inference.

M5 dự toán baseline {r5['baseline_monthly']:,} USD/tháng, optimized
{r5['optimized_monthly']:,} USD/tháng, tiết kiệm
{sum(r5['levers'].values()):,} USD/tháng ({r5['total_savings_pct']:.1f}%).
Bốn lever và số tiền cụ thể nằm trong report.md/savings.png. Purchasing đóng góp
lớn nhất: {r5['levers']['Purchasing (spot/reserved)']:,} USD/tháng.
M3 giảm {r3['savings_pct']:.1f}% nhờ spot/reserved nhưng quy đổi mọi job về 30 ngày.

## Hiệu quả GPU và phân bổ

{lies_text}. GPU hoạt động nhiều không đồng nghĩa đạt nhiều FLOPs.
Truy cập bộ nhớ, đồng bộ, kernel nhỏ hoặc pipeline dữ liệu có thể là nguyên nhân,
nhưng cần profiling để xác nhận. MFU thấp không tự chứng minh có thể hạ GPU
mà giữ nguyên chất lượng/throughput.

{idle_text}: lãng phí {r1['idle_waste_daily']:.2f} USD/ngày,
tương đương {r1['idle_waste_daily'] * 30:.0f} USD/tháng.
Idle chiếm {r1['idle_waste_daily'] / e['fleet_on_demand_daily'] * 100:.2f}%
chi phí fleet telemetry nếu thuê 24h/ngày.

M4 dùng cùng cách tính với M2, gồm phí ghi cache. Team {top['team']} chiếm
{top['cost_share_pct']:.2f}% chi phí inference. Tag coverage
{e['tag_coverage'] * 100:.2f}% vượt gate 80%; cần hoàn thiện các tag project thiếu.
Export FOCUS-style chỉ là mẫu 50 request để minh họa chuẩn hóa chi phí đa nhà cung cấp.

## Extension 3 — Kinh tế cache

Đã thêm cache_is_worth_it() vào pricing và gate trước khi áp dụng cache trong M2.
CSV không có prefix_id/reads; dùng giả định 1 và 10 reads/prefix cùng các kịch bản
0, 2, 3 để kiểm tra biên. Phí ghi bổ sung giả định bằng 1,25 lần giá input,
cached read trả 10% giá input; phí ghi không được giảm batch và phân bổ đều qua reads.

Hòa vốn n × P × B × 0,90 >= W: cần 2 reads không batch, 3 reads có batch.
Một read/prefix không hòa vốn nên tắt cache: {low['cost_daily_usd']:.6f} USD/ngày,
{low['usd_per_million_tokens']:.3f} USD/1M-token.
Mười reads/prefix bật cache: {r2['optimized_daily_raw']:.6f} USD/ngày,
{r2['optimized_per_m']:.3f} USD/1M-token, gồm {r2['cache_write_daily']:.6f}
USD/ngày phí ghi.

Mô hình gốc bỏ phí ghi chỉ báo {e['legacy_read_only_daily']:.6f} USD/ngày.
Savings giảm nhẹ sau bổ sung phí là kết quả trung thực hơn, không phải regression.
Trong inference, cascade đóng góp lớn nhất theo thứ tự đo:
{stages[1]['incremental_savings_daily_usd']:.6f} USD/ngày; đóng góp phụ thuộc thứ tự
cascade → cache → batch. Batch không phù hợp chat cần phản hồi ngay.
discount_stack=0,05 minh họa 0,50 × 0,10 trên input, không áp mức giảm cache lên output.

## Extension 5 — Carbon-aware scheduling

Đã tính 5 job interruptible với days thực tế, tổng {carbon['total_wh'] / 1000:,.0f} kWh,
giữ nguyên GPU-hours giữa các vùng. Giả định watts bằng catalog, không tính PUE,
rework do spot, truyền dữ liệu hoặc khác biệt giá thuê GPU.

Chuyển us-east-1 sang {carbon['cleanest_region']} giảm carbon từ
{carbon['before_g']:,.0f} xuống {carbon['after_g']:,.0f} gCO2e:
giảm {carbon['saved_g']:,.0f} gCO2e ({carbon['saved_g'] / 1000:.2f} kg),
tương đương {carbon['savings_pct']:.1f}%.
Điện rẻ nhất là {carbon['cheapest_region']}; carbon thấp nhất là {carbon['cleanest_region']}.
Policy cân bằng giả định carbon <=120 gCO2e/kWh rồi chọn giá thấp nhất cho kết quả
{carbon['balanced_region']}. Chi phí và carbon năm vùng được xuất thành CSV/report.

Job nền linh hoạt phù hợp chuyển vùng hơn dịch vụ cần latency thấp.
Cần kiểm tra GPU availability, framework, vị trí dữ liệu và latency.
Không cộng savings điện vào savings thuê GPU để tránh tính trùng.

## Khuyến nghị và giới hạn

Ưu tiên (1) tắt GPU idle theo lịch/TTL, (2) cascade có kiểm tra chất lượng và cache
theo hòa vốn, (3) spot có checkpoint rồi đánh giá cam kết reserved và vùng carbon.
Job chạy nhiều giờ nhưng chỉ vài ngày chưa đủ căn cứ cam kết 1–3 năm.
M3 chưa tính toàn bộ giờ cam kết; right-sizing dùng map cố định chưa có benchmark.
Tổng M5 giả định bucket độc lập; tài nguyên trùng nhau phải được đối soát.

Snapshot 0,24 Wh/query dùng query mẫu 800 token. Traffic thực tế theo mô hình
80x reasoning có trung bình {e['traffic_energy_per_query_wh']:.4f} Wh/request.
Reasoning chiếm {e['reasoning_groups'][1]['request_share_pct']:.3f}% request,
đã dưới 10%, nên cap 10% hiện tại có savings bằng 0.

## Kiểm tra và tái lập

Chạy .venv/Scripts/python.exe missions/run_all.py, verify.py và -m pytest -q.
Log kiểm tra nằm ở outputs/final/; baseline gốc ở outputs/baseline/pre_extension/.
Hai extension có test riêng trong extension_tests/; không sửa test gốc.
Manifest SHA-256 lưu bằng chứng dữ liệu so sánh và test gốc không thay đổi.
"""


def export(e, r1, r2, r3, r5, carbon):
    out = Path(ROOT) / "outputs"
    out.mkdir(exist_ok=True)
    for filename, records in [
        ("inference_steps.csv", e["stages"]),
        ("cache_scenarios.csv", e["cache_scenarios"]),
        ("cache_thresholds.csv", e["cache_thresholds"]),
        ("allocation_by_team.csv", e["by_team"]),
        ("reasoning_breakdown.csv", e["reasoning_groups"]),
        ("gpu_efficiency.csv", r1["summary"]),
        ("purchasing_recommendations.csv", r3["recommendations"]),
    ]:
        write_csv(out / filename, records)
    before_inference = round((r2["baseline_daily"] - round(e["legacy_read_only_daily"], 2)) * 30)
    before_savings = sum(r5["levers"].values()) - r5["levers"]["Inference (cascade/cache/batch)"] + before_inference
    baseline = r2["baseline_daily"] * 30 + r3["on_demand_monthly"]
    comparison = [
        {"metric": "optimized_inference_daily", "before": e["legacy_read_only_daily"], "after": r2["optimized_daily_raw"]},
        {"metric": "optimized_inference_usd_per_m", "before": pricing.dollars_per_million(e["legacy_read_only_daily"], e["total_tokens"]), "after": pricing.dollars_per_million(r2["optimized_daily_raw"], e["total_tokens"])},
        {"metric": "modeled_platform_optimized_monthly", "before": round(baseline - before_savings), "after": r5["optimized_monthly"]},
        {"metric": "modeled_platform_savings_monthly", "before": before_savings, "after": sum(r5["levers"].values())},
    ]
    write_csv(out / "before_after.csv", comparison)
    (out / "analysis.json").write_text(
        json.dumps(dict(e, m1=r1, m2=r2, m3=r3, m5=r5, carbon=carbon), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out / "writeup.md").write_text(writeup(e, r1, r2, r3, r5, carbon), encoding="utf-8")
