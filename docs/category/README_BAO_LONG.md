# bao-long — Cat-Popularity và đánh giá warm/cold P0 v2

Phần Bảo Long dùng nguyên bộ bàn giao của Bá Chiến và Trung Chiến, triển khai công cụ
đánh giá theo nhóm cùng Cat-Popularity oracle/non-oracle. Làm việc trên `bao-long`,
review qua PR vào `dev`; việc phê duyệt báo cáo và đưa lên `main` vẫn tách riêng.

## Kết quả và tài liệu

- [Báo cáo nghiên cứu](v2/RESULTS.md): điểm từng nhóm, mean/std, coverage,
  chênh lệch trên cùng tập mẫu và giới hạn diễn giải.
- [Hợp đồng và hướng dẫn bàn giao](HANDOFF.md).
- [Kết quả từng lượt](v2/runs.csv), [tổng hợp](v2/summary.json),
  [so sánh paired](v2/paired_differences.json), [manifest](v2/manifest.json).
- [Công thức chốt trước khi chạy](../plans/2026-11-13-bao-long-category-design.md)
  và [config thực nghiệm](../../configs/category_v2.toml).
- [Bộ split cố định của Trung Chiến](../splits/HANDOFF.md).

## Cài và chạy lại

Git, Python 3.12, Node.js 24+ để kiểm tra workflow; không cần GPU.

```powershell
git clone --branch bao-long https://github.com/baolong06/recommender_system.git
cd recommender_system
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.venv\Scripts\python.exe scripts/download_splits_v2.py
.venv\Scripts\python.exe scripts/download_raw.py --dataset diginetica --cache-dir artifacts/kagglehub
.venv\Scripts\python.exe scripts/run_category_v2.py --output-dir artifacts/my-category-v2
```

Linux/macOS thay interpreter bằng `.venv/bin/python`. Chọn `--dataset yoochoose` hoặc
`diginetica` để chạy một bộ. Raw catalog Diginetica được dùng để kiểm chứng mapping;
runner không chạy lại split và không dùng raw holdout làm thống kê fit. Yoochoose chỉ
cần final train để tái dựng mapping. Dùng output-directory mới, không ghi đè kết quả cũ.
Dataset exact hash phải khớp bảng Trung Chiến; nếu tự dựng lại với encoding khác cần
lập bản tham chiếu mới, không sửa checksum để bỏ qua xác minh.

Kiểm chứng độc lập các dòng Cat-Popularity và Popularity trên matched cohorts:

```powershell
.venv\Scripts\python.exe scripts/verify_category_results.py --input-root data/protocol_v2 --runs artifacts/my-category-v2/runs.json --output artifacts/my-category-v2-independent.json
```

## Thuật toán và thông tin được phép

| Chế độ | Chọn category | Ranking |
| --- | --- | --- |
| Non-oracle | Category biết được xuất hiện nhiều nhất trong prefix; hòa chọn lần xuất hiện cuối | Item cùng category trước, rồi số event final train giảm dần, ID chuỗi tăng dần |
| Oracle | Được biết category target từ mapping được phép, không truyền target ID | Cùng luật ranking; đây là điều kiện đặc quyền |

Không có category prefix thì non-oracle fallback Popularity. Oracle thiếu category
thì N/A. Cả hai giữ cùng candidates W∪C, giữ item đã xem, cùng K=20, cùng metric và
ba split seed 42/43/44. Random chạy thêm ba model seed trong mỗi split; mô hình xác
định có model_seed trống. Không refit trên validation/test hoặc chọn seed từ kết quả test.

Yoochoose chỉ suy category thật 1..12 từ final train. Cold không có catalog độc lập nên
Cat-Popularity cold primary là N/A. Diginetica dùng catalog tĩnh với giả định metadata
có sẵn lúc inference; chưa có chứng minh thời điểm catalog được công bố trong lịch sử.

Công thức không thêm pseudo-count hoặc vector cho cold item. Biết category không bảo
đảm rank cao: trong category, cold có số đếm bằng 0 và đứng sau item warm có count dương.
Oracle cũng không phải bảo đảm upper bound accuracy cho công thức ranking cố định này.

## Đọc đúng bảng kết quả

- Nhóm dựa vào **target**, không dựa vào history. Overall lấy trung bình theo mẫu.
- `n_eligible` là target thuộc primary candidates, `n` là mẫu mô hình thực sự hỗ trợ.
  `support_fraction=n/n_eligible`; nhóm thiếu mẫu có `status=partial`; n=0 có metric null/N/A.
- Các target ngoài candidates vẫn được báo trong split coverage và giữ vị trí OOV trong prefix.
- So sánh category với Random/Popularity ở cùng `cohort` (`oracle-supported` hoặc
  `non-oracle-supported`). Không so điểm partial với baseline trên full-primary.
- Mean/std của Random được tính qua model seed trong split, sau đó qua ba split mean;
  sample std dùng ddof=1. Chênh lệch paired chỉ mô tả, không phải kiểm định ý nghĩa thống kê.
- Giữ số thấp, 0 và N/A. Không khuyến nghị mô hình từ kết quả P0; báo cáo mô tả hiện tượng.

## File triển khai và kiểm thử

| File | Vai trò |
| --- | --- |
| `src/recommender/evaluation.py` | GroupMetrics streaming và giao diện evaluate_groups cũ |
| `src/recommender/category.py` | Hai giao diện dự đoán tách ranh giới oracle |
| `src/recommender/category_metadata.py` | Tái dựng mapping từ nguồn được phép |
| `src/recommender/category_evaluation.py` | Chấm nhóm, matched cohorts và chênh lệch paired |
| `scripts/run_category_v2.py` | Xác minh input, chạy bốn baseline và xuất provenance |
| `scripts/verify_category_results.py` | Tính độc lập bằng SQL counts + analytical rank |
| `tests/test_category.py` | Test tính tay, chống đọc target, missing metadata, N/A và tái lập |

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m recommender.smoke --output artifacts/smoke.json
node --test .github/tests/trusted-policy.test.cjs
```

Dữ liệu lớn giữ ở Release của Trung Chiến; repo lưu code/config/báo cáo nhỏ. Gia cố CI
đã tích hợp cùng nền chung, không thay thế nhiệm vụ nghiên cứu. Xem `docs/security.md`
về activation của trusted workflow trên main. Không tắt required checks hoặc tự duyệt
báo cáo để đưa research-readiness thành complete.
