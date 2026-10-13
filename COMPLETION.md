# Hoàn thành Lab Day 25 — GPU FinOps

Đã triển khai 5 mission và 2 extension được chấm điểm: **Extension 3 — Cache economics**
và **Extension 5 — Carbon-aware scheduling**. Bonus là tùy chọn, không thuộc phần chấm điểm.

## Chạy lại

Từ thư mục gốc lab, dùng môi trường đã cài:

```powershell
.\.venv\Scripts\python.exe missions/run_all.py
.\.venv\Scripts\python.exe verify.py
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe -m pytest -q extension_tests
```

M5 tự sinh lại báo cáo, bài viết tiếng Việt và các bảng phân tích. Không cần chèn tay vào report.md.
verify.py/test tích hợp sinh lại dữ liệu seed=25 và output.

## File nộp

- outputs/report.md
- outputs/savings.png
- outputs/focus_export.csv
- outputs/writeup.md
- Code extension trong finops/pricing.py và missions/.
- Bằng chứng: outputs/cache_scenarios.csv, carbon_jobs.csv, carbon_regions.csv,
  before_after.csv, outputs/baseline/pre_extension/ và outputs/final/.

## Code đã thay đổi

- finops/pricing.py: thêm cache_is_worth_it, kiểm tra đầu vào và hòa vốn.
- missions/m2_inference_levers.py: gate cache, phân bổ phí ghi và giữ API kết quả gốc.
- missions/m4_allocation.py: cùng hàm tính tiền với M2, có phí ghi cache.
- missions/carbon_scheduling.py: so 5 vùng trên cùng GPU-hours và days thực tế.
- missions/lab_analysis.py: bảng dữ liệu, lever, allocation, reasoning, before/after và write-up.
- missions/m5_report.py: tích hợp hai extension và phân tích, ghi UTF-8.
- extension_tests/test_extensions.py: test bổ sung, tách khỏi tests/ gốc.

## Giả định bắt buộc đọc

- Cache: 10 reads/prefix mặc định; ghi BỔ SUNG bằng 1,25 lần giá input.
  Dataset thiếu prefix_id/reads nên đây là kịch bản giả định, không phải số đo.
  Cached read = 10% giá; batch = 50%; phí ghi không giảm batch, phân bổ đều qua reads.
- Carbon: dùng catalog watts không đổi, days thực tế và cùng lượng công việc.
  Không tính PUE, spot rework, truyền dữ liệu hoặc giá thuê GPU theo vùng.
  Policy cân bằng giả định carbon <=120 gCO2e/kWh rồi chọn điện rẻ nhất.
- M3/M5 vẫn dùng monthly 30 ngày theo lab gốc. Carbon dùng vòng đời job thực tế;
  không cộng savings điện vào savings thuê GPU.
- Right-sizing của M5 là map gốc, chưa có benchmark throughput/VRAM.
- Bốn lever M5 giả định bucket độc lập; triển khai thật cần loại trùng tài nguyên.
- Giá và carbon là snapshot minh họa của lab, không phải dữ liệu thị trường hiện tại.

## Baseline và kiểm tra

outputs/baseline/pre_extension/ lưu dữ liệu, code gốc, output gốc,
results.json và sha256.json trước triển khai. Baseline người dùng đã lưu trước đó
ở outputs/baseline/ được giữ nguyên.

outputs/final/ lưu log chạy và kết quả kiểm tra SHA-256. Bộ tests/ gốc không được sửa.
