# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,631  
**Projected savings:** $12,502  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,207 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Lowest-carbon region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._

## Phạm vi và khả năng tái lập

Dữ liệu tổng hợp seed=25; giá và hệ số điện/carbon là snapshot minh họa của lab.
Không sử dụng GPU thật, cloud account hoặc API key.
M3/M5 quy đổi 30 ngày; extension carbon dùng days thực tế của từng job.

| CSV | Số dòng |
|---|---|
| price_catalog.csv | 7 |
| gpu_telemetry.csv | 264 |
| token_usage.csv | 2400 |
| workloads.csv | 8 |

## Inference unit economics

| Chỉ tiêu | Baseline | Optimized |
|---|---|---|
| USD/ngày | 48.874161 | 8.650797 |
| USD/1M-token | 6.488 | 1.148 |

Tổng token/ngày: 7,533,027; tổng input + output, không cộng cached input lần hai.
USD/1M-token ở đây chỉ bao gồm inference, không chia chi phí training vào sản lượng inference.

### Đóng góp theo thứ tự cascade → cache → batch → phí ghi

| Giai đoạn | USD/ngày | USD/1M-token | Savings thêm USD/ngày |
|---|---|---|---|
| Baseline: large, no cache, no batch | 48.874161 | 6.487984 | 0.000000 |
| Cascade | 11.475643 | 1.523377 | 37.398518 |
| Cascade + cache gate (reads only) | 10.279188 | 1.364549 | 1.196455 |
| Cascade + cache gate + batch (reads only) | 8.484623 | 1.126323 | 1.794565 |
| Optimized including amortized writes | 8.650797 | 1.148383 | -0.166174 |

Cascade đóng góp lớn nhất trong inference. Phần đóng góp phụ thuộc thứ tự áp dụng.
Phí ghi làm savings giảm, nên dòng cuối có incremental savings âm.
Batch phù hợp cho eval/xử lý nền; không áp dụng tùy ý cho chat cần phản hồi ngay.
0.50 × 0.10 = 0.05 là mô hình chiết khấu input; output không tự được giảm 90% bởi cache.

## Extension 3 — Cache economics

Giả định mặc định: 10 reads/prefix; phí ghi BỔ SUNG = 1.25 × giá input.
Phí ghi nằm ngoài chi phí request thông thường, không hưởng giảm giá batch và được phân bổ đều cho reads.
Giả định mỗi prefix được tái sử dụng trong cùng model/điều kiện batch.
CSV không có prefix_id hoặc reads/prefix: các reads dưới đây là kịch bản, không phải số đo.

Hòa vốn: n × P × B × (1 − 0.10) >= W, với W là phí ghi bổ sung USD/1M token.

| Model | Batch | P USD/1M | W USD/1M | Reads hòa vốn |
|---|---|---|---|---|
| small | 0 | 0.20 | 0.25 | 1.388889 |
| small | 1 | 0.20 | 0.25 | 2.777778 |
| large | 0 | 3.00 | 3.75 | 1.388889 |
| large | 1 | 3.00 | 3.75 | 2.777778 |

Cần ít nhất 2 reads không batch, hoặc 3 reads có batch theo giả định trên.

| Reads giả định | USD/ngày | USD/1M-token | Phí ghi USD/ngày | Request bật cache |
|---|---|---|---|---|
| 0 | 9.658588 | 1.282166 | 0.000000 | 0 |
| 1 | 9.658588 | 1.282166 | 0.000000 | 0 |
| 2 | 9.306748 | 1.235459 | 0.799636 | 1985 |
| 3 | 9.038537 | 1.199855 | 0.553914 | 2400 |
| 10 | 8.650797 | 1.148383 | 0.166174 | 2400 |

Mô hình gốc bỏ phí ghi: 8.484623 USD/ngày. Mô hình đầy đủ: 8.650797 USD/ngày.
Không so việc bổ sung một loại chi phí với savings do cải thiện throughput: đây là điều chỉnh phạm vi tính tiền cho đầy đủ.

## M1 — Phân tích hiệu quả

| GPU | Util % | MFU | MBU | Idle giờ/ngày |
|---|---|---|---|---|
| gpu-h100-0 | 94.4 | 0.417 | 0.446 | 0 |
| gpu-h100-1 | 95.2 | 0.408 | 0.44 | 0 |
| gpu-h100-2 | 94.3 | 0.401 | 0.423 | 0 |
| gpu-h100-3 | 93.1 | 0.427 | 0.444 | 0 |
| gpu-h100-4 | 98.2 | 0.194 | 0.207 | 0 |
| gpu-h100-5 | 61.1 | 0.261 | 0.271 | 8 |
| gpu-a100-0 | 31.4 | 0.259 | 0.276 | 0 |
| gpu-a100-1 | 28.0 | 0.236 | 0.247 | 0 |
| gpu-a10g-0 | 25.0 | 0.218 | 0.235 | 0 |
| gpu-a10g-1 | 96.9 | 0.268 | 0.302 | 0 |
| gpu-l4-0 | 40.0 | 0.302 | 0.328 | 0 |

GPU utilization cao nhất: gpu-h100-4, util=98.2%, MFU=0.194.
GPU-Util phản ánh khoảng thời gian GPU hoạt động, không phải tỷ lệ FLOPs đạt được.
Memory stall, kernel nhỏ, đồng bộ hoặc pipeline dữ liệu có thể gây MFU thấp; dataset không chứng minh nguyên nhân cụ thể, cần profiling.
GPU bị flag: gpu-h100-4, gpu-a10g-1.
Idle waste: 20.00 USD/ngày; 600.00 USD/tháng.
Idle chiếm 3.90% chi phí 11 GPU telemetry thuê liên tục 24h/ngày.
Decode có arithmetic intensity thấp nên có thể memory-bound; prefill cao hơn nên có thể compute-bound.
MBU thấp một mình chưa đủ xác nhận memory-bound.

## M3 — Purchasing

| Job | GPU | Tier | On-demand USD/30 ngày | Optimized USD/30 ngày |
|---|---|---|---|---|
| job-train-llm | H100 | spot | 12000 | 7596 |
| job-train-embed | A100 | spot | 2148 | 1393 |
| job-finetune | H100 | spot | 900 | 570 |
| job-infer-chat | A10G | reserved | 4320 | 2592 |
| job-infer-rag | A100 | reserved | 3866 | 2160 |
| job-infer-search | L4 | reserved | 1728 | 972 |
| job-dev-sandbox | A10G | spot | 480 | 203 |
| job-batch-eval | H100 | spot | 225 | 142 |

Purchasing savings: 39.1%.
Các job interruptible và chạy dưới 24h/ngày được đề xuất spot; effective hours cao hơn useful hours do checkpoint 3% và rework theo interruption rate 0.05/giờ.
Inference chạy ổn định được đề xuất reserved. Ngưỡng policy 55% = 13.2h/ngày.
Policy chưa xét độ dài job/cam kết; job ngắn không đủ căn cứ mua reserved 1–3 năm.
M3 tính reserved theo giờ sử dụng thay vì toàn bộ thời gian cam kết, nên chưa phải phép tính TCO của hợp đồng thật.

## M4 — Allocation

| Team | USD/ngày | % chi phí |
|---|---|---|
| assistant | 2.681579 | 31.00 |
| search | 2.503151 | 28.94 |
| eval | 1.800812 | 20.82 |
| rag | 1.665255 | 19.25 |

Team tốn nhiều nhất: assistant. Tag coverage: 91.79%; chargeback ready: True.
Coverage >=80% mở gate theo policy lab; cần xử lý các project còn thiếu trước khi phân bổ thực tế.
M4 và M2 dùng cùng hàm pricing, bao gồm phí ghi cache.
FOCUS-style export là mẫu 50 request, không phải toàn bộ hóa đơn 2.400 request.
Chuẩn hóa trường chi phí giúp tổng hợp đa nhà cung cấp; file mẫu chưa được xác nhận tuân thủ đầy đủ mọi yêu cầu của chuẩn FOCUS.

## Sustainability của traffic thực tế

| Reasoning | Requests | % requests | Tokens | USD/ngày | Wh | % năng lượng |
|---|---|---|---|---|---|---|
| 0 | 2199 | 91.625 | 6291871 | 7.251141 | 1887.5613 | 5.96 |
| 1 | 201 | 8.375 | 1241156 | 1.399657 | 29787.7440 | 94.04 |

Năng lượng theo mô hình toàn traffic: 31675.3053 Wh/ngày, trung bình 13.1980 Wh/request.
Mức 0.24 Wh ở snapshot Sustainability đầu báo cáo là query mẫu 800 token, không phải trung bình traffic.
Hệ số reasoning 80x là giả định hàm wh_per_query; dữ liệu tổng hợp còn có output reasoning dài hơn. Không coi đây là phép đo điện vật lý.
Reasoning chiếm 8.375% request, đã dưới 10%; cap 10% trên traffic hiện tại không tạo savings.

## Ưu tiên và giới hạn

Lever lớn nhất của M5: Purchasing (spot/reserved), 10,040 USD/tháng.
1. Tắt GPU idle theo lịch/TTL; xác nhận nhu cầu trước khi scale xuống.
2. Duy trì cascade có đánh giá chất lượng; cache theo reads hòa vốn; batch các tác vụ phù hợp.
3. Spot có checkpoint cho job linh hoạt; xác nhận nhu cầu dài hạn trước reserved và chọn vùng theo ưu tiên chi phí/carbon.

Right-size util-lies dùng RIGHTSIZE_MAP gốc, chưa có benchmark VRAM/throughput chứng minh savings.
Bốn bucket savings được cộng theo mô phỏng gốc, giả định độc lập. Nếu telemetry và workloads cùng đại diện một tài nguyên, cần đối soát tránh tính trùng.
M5 dùng các giá trị mission đã làm tròn; bảng chi tiết inference dùng raw totals. Chênh lệch vài cent là do làm tròn.
Không cộng chi phí điện tiết kiệm vào savings thuê GPU: điện có thể đã nằm trong giá thuê và kỳ thời gian của extension carbon khác monthly.


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
