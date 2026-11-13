# trung-chien — Split và baseline P0 v2

Phần Trung Chiến tiếp nhận dữ liệu của Bá Chiến trên `dev` (PR #3), kiểm tra split
và chạy Random/Popularity để bàn giao cho Bảo Long. Phát triển trên `trung-chien`,
review qua PR vào `dev`; bước đưa lên `main` vẫn theo quy trình chung của nhóm.

## Bộ bàn giao

- [Hướng dẫn và kết quả](docs/splits/HANDOFF.md).
- [Bảng kết quả từng lượt](docs/splits/v2/runs.csv), [tổng hợp mean/sample std](docs/splits/v2/summary.json).
- [Kiểm tra split/rò rỉ](docs/splits/v2/split_acceptance.json) và [provenance kết quả](docs/splits/v2/manifest.json).
- [Manifest tải split](docs/splits/v2/delivery.json): file dataset, SHA-256 và URL tải đúng phiên bản.
- [Protocol dữ liệu](docs/data/PROTOCOL_V2.md) và [cấu hình baseline](configs/baselines_v2.toml).

Kết quả được tính từ dữ liệu thật, không lấy fixture làm số liệu P0. Trạng thái review
và phê duyệt nghiên cứu vẫn tách khỏi việc chạy code thành công; CatPopularity thuộc phần
Bảo Long, chưa có trong runner này.

## Cài môi trường

Git, Python 3.12; Node.js 24+ để kiểm tra workflow. Không cần GPU.

```powershell
git clone --branch trung-chien https://github.com/baolong06/recommender_system.git
cd recommender_system
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

Linux/macOS thay đường dẫn interpreter bằng `.venv/bin/python`.

## Tải cùng split và chạy baseline

```powershell
.venv\Scripts\python.exe scripts/download_splits_v2.py
.venv\Scripts\python.exe scripts/run_baselines_v2.py --input-root data/protocol_v2 --output-dir artifacts/my-baselines-v2 --reference-root docs/data/protocol_v2
```

Bộ tải xác minh ZIP và từng file, lưu dữ liệu vào `data/protocol_v2/<dataset>/`.
Chọn `--dataset diginetica` hoặc `--dataset yoochoose` để tải/chạy riêng một bộ.
Dùng output-directory mới mỗi lần chạy để giữ phiên bản; không chỉnh file sau khi đã ghi manifest.

Nếu cần tái tạo split từ raw thay vì tải bộ đã bàn giao:

```powershell
.venv\Scripts\python.exe scripts/download_raw.py --cache-dir artifacts/kagglehub
.venv\Scripts\python.exe scripts/run_protocol_v2.py --dataset all
```

Đây là P0-data-v2, khác bộ legacy trong `data/processed`. Không trộn hai phiên bản.
Dựng lại trên hệ điều hành/phiên bản thư viện khác có thể thay đổi bytes Parquet; runner
kiểm tra raw hash và audit theo bàn giao, đồng thời cấp split ID từ manifest thực tế.

## Luật đánh giá

- Giữ temporal windows, lọc train-only, C=ceil(20%×U0), segmentation và candidates W∪C từ v2.
- Ba split seed 42/43/44. Random chạy thêm ba model seed 42/43/44 trên mỗi split;
  Popularity xác định, model_seed trống và chỉ fit final train một lần cho mỗi split.
- K=20 được chọn trước khi đọc metric test, theo đề xuất v2. Không chọn K/seed/cutoff từ test.
- Popularity đếm event train, hòa chọn item ID tăng dần theo chuỗi. Giữ item từng xem trong candidates.
- Random lấy top-K không hoàn lại, RNG riêng theo query identity và các seed; không đọc target/category.
- Dùng chung HR/MRR/NDCG trong `recommender.metrics`; báo overall/warm/controlled-cold và số mẫu.
- Target I0/ngoài candidates bị loại khỏi primary metric nhưng vẫn báo coverage; OOV vẫn giữ vị trí trong prefix.
- Tổng hợp Random qua model seed trong từng split, rồi mean và sample std (ddof=1) của ba split mean.
  Không coi chín lượt Random là chín split độc lập. Nhóm không có mẫu ghi N/A/null.
- Không refit bằng validation/test. Yoochoose test cuối ngày chỉ có 479 phiên/1.452 target trước loại;
  đây là hạn chế thống kê của cửa sổ hiện tại, không âm thầm đổi ngày để làm kết quả tốt hơn.

## File triển khai

| File | Vai trò |
| --- | --- |
| `src/recommender/data/protocol_v2.py` | Bộ dựng split đã nhận từ Bá Chiến |
| `src/recommender/splits/acceptance.py` | Xác minh checksum, cold, candidates/support, thời gian/phiên và coverage |
| `src/recommender/data/examples_v2.py` | Iterator prefix/target giữ vị trí OOV |
| `src/recommender/baselines_v2.py` | Random/Popularity và tổng hợp kết quả |
| `scripts/run_baselines_v2.py` | Chạy dữ liệu thật, xuất bảng và manifest |
| `scripts/package_splits_v2.py`, `scripts/download_splits_v2.py` | Bàn giao đúng file giữa các máy |
| `tests/test_baselines_v2.py` | Test tính tay, seed, kiểm tra rò rỉ, tamper và đóng gói/tải |

Các file `configs/split.example.toml` và manifest `*.example.*` là mẫu lịch sử,
không phải cấu hình runner hoặc số liệu thực nghiệm. Dùng cấu hình v2 nêu trên.

## Kiểm tra và đẩy thay đổi

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m recommender.smoke --output artifacts/smoke.json
node --test .github/tests/trusted-policy.test.cjs
git push origin trung-chien
```

Chỉ stage code/config/báo cáo nhỏ; dữ liệu lớn nằm ở Release. Khi nhận dev, xử lý
README theo hướng dẫn của nhánh cá nhân và review riêng các thay đổi khác.
