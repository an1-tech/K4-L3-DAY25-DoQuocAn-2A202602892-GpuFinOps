# GPU FinOps — Đỗ Quốc An — 2A202602892

## Phạm vi và kết quả

Lab chạy thuần Python trên dữ liệu tổng hợp seed=25, không cần GPU/cloud/API key.
Bốn CSV gồm 7 loại GPU, 264 bản ghi telemetry, 2.400 request và 8 workload.
Giá GPU/model, giá điện và carbon là snapshot minh họa của lab, không phải báo giá hiện tại.

Inference baseline là 48.874161 USD/ngày
(6.488 USD/1M-token); optimized sau tính phí ghi cache là
8.650797 USD/ngày (1.148 USD/1M-token),
giảm 82.3% với cùng 7,533,027 input + output token.
USD/1M-token này chỉ tính inference.

M5 dự toán baseline 27,133 USD/tháng, optimized
14,631 USD/tháng, tiết kiệm
12,502 USD/tháng (46.1%).
Bốn lever và số tiền cụ thể nằm trong report.md/savings.png. Purchasing đóng góp
lớn nhất: 10,040 USD/tháng.
M3 giảm 39.1% nhờ spot/reserved nhưng quy đổi mọi job về 30 ngày.

## Hiệu quả GPU và phân bổ

gpu-h100-4: util 98.2%, MFU 0.194; gpu-a10g-1: util 96.9%, MFU 0.268. GPU hoạt động nhiều không đồng nghĩa đạt nhiều FLOPs.
Truy cập bộ nhớ, đồng bộ, kernel nhỏ hoặc pipeline dữ liệu có thể là nguyên nhân,
nhưng cần profiling để xác nhận. MFU thấp không tự chứng minh có thể hạ GPU
mà giữ nguyên chất lượng/throughput.

gpu-h100-5 idle 8 giờ/ngày: lãng phí 20.00 USD/ngày,
tương đương 600 USD/tháng.
Idle chiếm 3.90%
chi phí fleet telemetry nếu thuê 24h/ngày.

M4 dùng cùng cách tính với M2, gồm phí ghi cache. Team assistant chiếm
31.00% chi phí inference. Tag coverage
91.79% vượt gate 80%; cần hoàn thiện các tag project thiếu.
Export FOCUS-style chỉ là mẫu 50 request để minh họa chuẩn hóa chi phí đa nhà cung cấp.

## Extension 3 — Kinh tế cache

Đã thêm cache_is_worth_it() vào pricing và gate trước khi áp dụng cache trong M2.
CSV không có prefix_id/reads; dùng giả định 1 và 10 reads/prefix cùng các kịch bản
0, 2, 3 để kiểm tra biên. Phí ghi bổ sung giả định bằng 1,25 lần giá input,
cached read trả 10% giá input; phí ghi không được giảm batch và phân bổ đều qua reads.

Hòa vốn n × P × B × 0,90 >= W: cần 2 reads không batch, 3 reads có batch.
Một read/prefix không hòa vốn nên tắt cache: 9.658588 USD/ngày,
1.282 USD/1M-token.
Mười reads/prefix bật cache: 8.650797 USD/ngày,
1.148 USD/1M-token, gồm 0.166174
USD/ngày phí ghi.

Mô hình gốc bỏ phí ghi chỉ báo 8.484623 USD/ngày.
Savings giảm nhẹ sau bổ sung phí là kết quả trung thực hơn, không phải regression.
Trong inference, cascade đóng góp lớn nhất theo thứ tự đo:
37.398518 USD/ngày; đóng góp phụ thuộc thứ tự
cascade → cache → batch. Batch không phù hợp chat cần phản hồi ngay.
discount_stack=0,05 minh họa 0,50 × 0,10 trên input, không áp mức giảm cache lên output.

## Extension 5 — Carbon-aware scheduling

Đã tính 5 job interruptible với days thực tế, tổng 1,789 kWh,
giữ nguyên GPU-hours giữa các vùng. Giả định watts bằng catalog, không tính PUE,
rework do spot, truyền dữ liệu hoặc khác biệt giá thuê GPU.

Chuyển us-east-1 sang europe-north1 giảm carbon từ
679,820 xuống 53,670 gCO2e:
giảm 626,150 gCO2e (626.15 kg),
tương đương 92.1%.
Điện rẻ nhất là us-east-wa; carbon thấp nhất là europe-north1.
Policy cân bằng giả định carbon <=120 gCO2e/kWh rồi chọn giá thấp nhất cho kết quả
us-east-wa. Chi phí và carbon năm vùng được xuất thành CSV/report.

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
80x reasoning có trung bình 13.1980 Wh/request.
Reasoning chiếm 8.375% request,
đã dưới 10%, nên cap 10% hiện tại có savings bằng 0.

## Kiểm tra và tái lập

Chạy .venv/Scripts/python.exe missions/run_all.py, verify.py và -m pytest -q.
Log kiểm tra nằm ở outputs/final/; baseline gốc ở outputs/baseline/pre_extension/.
Hai extension có test riêng trong extension_tests/; không sửa test gốc.
Manifest SHA-256 lưu bằng chứng dữ liệu so sánh và test gốc không thay đổi.
