# Recommender System — nền nghiên cứu P0 v2

Repository dùng chung cho ba đề tài của Bá Chiến, Trung Chiến và Bảo Long:
chuẩn bị dữ liệu/metric, split cold-start và baseline, đánh giá category theo nhóm warm/cold.
Nhánh `dev` tích hợp kết quả để nhóm review; quy trình đưa lên `main` vẫn theo hồ sơ nghiên cứu.

## Thành phần và tài liệu

| Phần | Nội dung | Tài liệu |
| --- | --- | --- |
| Bá Chiến | Chuẩn hóa raw, thời gian mili giây, dữ liệu trung tính, lọc train-only và mapping category | [P0 data v2](docs/data/PROTOCOL_V2.md) |
| Trung Chiến | Xác minh split/cold 20%, Random/Popularity, ba seed và bộ tải split | [Bàn giao split/baseline](docs/splits/HANDOFF.md) |
| Bảo Long | Group-wise, Cat-Popularity oracle/non-oracle, so sánh trên cùng mẫu | [Bàn giao category](docs/category/HANDOFF.md) |

Kết quả thật, config, input/source hashes và mean/sample std nằm ở:

- [Bảng Random/Popularity](docs/splits/v2/RESULTS.md).
- [Bảng Cat-Popularity và warm/cold](docs/category/v2/RESULTS.md).
- [Hướng dẫn chi tiết phần Bảo Long](docs/category/README_BAO_LONG.md).
- [Luồng nhánh](docs/plans/2026-11-12-work-branches.md) và [hồ sơ nghiên cứu](docs/research-readiness.json).

## Cài môi trường

Git, Python 3.12; Node.js 24+ để kiểm tra workflow. Các baseline hiện tại không cần GPU.

```powershell
git clone --branch dev https://github.com/baolong06/recommender_system.git
cd recommender_system
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

Linux/macOS dùng `.venv/bin/python`. Dependency được khóa phiên bản và SHA-256;
đọc `docs/security.md` khi cần cập nhật môi trường.

## Tải đúng split và chạy lại thực nghiệm

```powershell
.venv\Scripts\python.exe scripts/download_splits_v2.py
.venv\Scripts\python.exe scripts/run_baselines_v2.py --output-dir artifacts/my-baselines-v2 --reference-root docs/data/protocol_v2
.venv\Scripts\python.exe scripts/download_raw.py --dataset diginetica --cache-dir artifacts/kagglehub
.venv\Scripts\python.exe scripts/run_category_v2.py --output-dir artifacts/my-category-v2
```

Bộ tải xác minh ZIP và từng payload, lưu vào `data/protocol_v2/<dataset>/`.
Catalog raw Diginetica dùng để kiểm chứng category mapping; Yoochoose mapping chỉ suy
ra từ final train. Chọn `--dataset` để chạy riêng một dataset. Mỗi lần chạy dùng
output-directory mới. Dữ liệu lớn nằm ở Release; repo giữ code/config/báo cáo và manifest.

Nếu cần tạo lại dữ liệu từ raw:

```powershell
.venv\Scripts\python.exe scripts/download_raw.py --cache-dir artifacts/kagglehub
.venv\Scripts\python.exe scripts/run_protocol_v2.py --dataset all
```

Định dạng Parquet có thể khác byte khi dựng lại trên môi trường khác. Bản category
chính yêu cầu exact split manifest đã bàn giao bởi Trung Chiến; không sửa checksum
để dùng lẫn phiên bản. Bộ legacy trong `data/processed` được giữ để đối chiếu,
không phải input của thực nghiệm v2 này.

## Quy ước đánh giá và trạng thái

- Giữ cold 20% theo U0, seeds 42/43/44, temporal windows và train-only filtering của v2.
- Dùng cùng split/candidates W∪C, giữ item đã xem và K=20 cho các model.
- Random có ba model seed trong mỗi split; mô hình xác định có model_seed trống.
- Oracle biết category target và được ghi là điều kiện đặc quyền. Non-oracle chỉ dùng prefix.
- Yoochoose cold category là N/A khi chưa có catalog độc lập. Mẫu không được hỗ trợ
  phải có lý do/coverage; chỉ so metric trên cùng cohort.
- Mean/std của Random được tính qua model seed trong split, rồi qua ba split mean;
  không coi chín lượt Random là chín split độc lập.
- Yoochoose có tập test nhỏ; Diginetica primary coverage khoảng 76,3% và dùng giả định
  catalog tĩnh. Xem giới hạn đầy đủ trong báo cáo trước khi diễn giải.

Phần code/thực nghiệm đã có kết quả và kiểm chứng; hồ sơ vẫn `in_progress`.
Thống kê/biểu đồ phân phối theo dữ liệu v2 cần bổ sung vào bộ bàn giao chung;
nhóm/giảng viên còn cần review công thức, protocol và báo cáo. Việc tích hợp vào dev
không tự đánh dấu protocol approved hoặc nghiên cứu hoàn tất.

## Kiểm tra và luồng làm việc

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m recommender.smoke --output artifacts/smoke.json
node --test .github/tests/trusted-policy.test.cjs
```

Ba nhánh cá nhân `ba-chien`, `trung-chien`, `bao-long` gửi PR vào `dev`.
Chỉ `dev` gửi PR vào `main` sau khi đáp ứng điều kiện nghiên cứu/review.
Không force-push để đồng bộ, không tắt required checks. Hướng dẫn cá nhân được giữ
trong tài liệu riêng; README trên nhánh tích hợp dùng làm trang đầu chung.
