# Chạy và sử dụng dữ liệu P0 v2

V2 triển khai quyết định nghiên cứu tại
[protocol v2](../plans/2026-11-13-data-protocol-v2-research-review.md).
Dữ liệu v1/legacy được giữ để đối chiếu; không được gộp vào bộ split v2.

## Cài và chạy

Python 3.12, đủ dung lượng cho dữ liệu gốc, các split và SQL spill tạm.
Không cần GPU. Chạy từ root repository:

```bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe thay cho .venv/bin/python
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python scripts/download_raw.py --cache-dir /path/with/enough/free/space/kagglehub
.venv/bin/python scripts/run_protocol_v2.py --dataset all
```

Kaggle v1 được cố định cùng SHA-256 ba file cần dùng. Bộ tải không thay thế file hiện có
nếu checksum sai. Có thể tự đặt file gốc đúng `data/raw/<dataset>/` để chạy offline.
Kaggle public có thể cần đăng nhập tùy môi trường; không commit credential vào repo.

Có thể chọn `--dataset diginetica` hoặc `--dataset yoochoose`, `--raw-dir`, `--output-dir`,
`--batch-size`. Các ngưỡng nghiên cứu đã cố định theo version; config không khớp sẽ bị từ chối.
Chạy lại dùng output-directory mới, không ghi đè kết quả cũ. File manifest chỉ xuất sau
khi toàn bộ kiểm tra thành công; thư mục chạy dở không phải bản bàn giao.

## Đầu ra

Mỗi dataset có:

- `neutral.parquet`: mọi event hợp lệ, chưa lọc support, có `raw_context`, `raw_row_index`,
  `timestamp_ms`, `timestamp`, `category_id` và `exact_duplicate`. Flag không có nghĩa tự xóa.
- `splits/validation.parquet`, `splits/test.parquet`: dòng sự kiện nguyên bản trong mỗi cửa sổ,
  sort theo session, timestamp_ms, raw_row_index; không xóa item chỉ vì chưa có trong train.
- `splits/preholdout_items.parquet`: universe U0 trước cold intervention.
- `splits/seed-42/`, `seed-43/`, `seed-44/`: train, cold_items, incidental_items, candidates,
  category_mapping. Manifest ghi vị trí chính xác và schema của từng bản chạy.
- `manifest.json`: raw/code/config hashes, thống kê lọc, cửa sổ UTC, audit theo seed,
  coverage target, category coverage và hash/dung lượng mỗi file.

Neutral `category_id` của Yoochoose luôn UNK: không fit category từ toàn corpus.
Muốn dùng category, join `category_mapping.parquet` theo item_id cho từng seed. Mapping được
fit từ final train; chỉ nhận context 1..12, hòa theo số nguyên. 0/S/brand không phải category.
Diginetica dùng catalog tĩnh theo giả định biết metadata lúc inference; chưa chứng minh thời điểm
catalog được công bố trong lịch sử. Thiếu/xung đột mapping được kiểm tra thay vì chọn tùy ý.

## Dùng split để đánh giá

Tập C có đúng ceil(0,20×|U0|) item cho từng seed. Không đổi C dựa vào target test.
Sau khi xóa C, train được cắt thành đoạn liên tiếp, bỏ đoạn dưới hai sự kiện; không nối
hai phía qua event bị xóa. Ngưỡng support5 là trước intervention; support warm cuối có thể
nhỏ hơn5. Không re-core sau intervention.

Candidate chính là W∪C, W gồm item còn xuất hiện trong train cuối. I0 gồm item không phải C
nhưng mất hết support sau khi cắt đoạn. Target I0/ngoài candidate không vào primary metrics;
luôn báo số lượng loại và coverage trong manifest. Tỷ lệ20% có mẫu số U0, không phải W∪C cuối.

Dùng iterator `recommender.data.examples_v2` để tạo prefix/target khi đánh giá thay vì
lưu tất cả prefix mở rộng làm nhân dung lượng. Prefix chỉ có quá khứ, giữ vị trí OOV bằng
sentinel; không xóa OOV rồi nối chuỗi. Cùng seed phải dùng cùng train/candidates/mapping cho
mọi model. Giữ item từng xem trong candidates vì next-item có thể lặp.

Các file train có `parent_session_id` để audit thời gian/phiên, `session_id` đoạn để huấn luyện.
Không coi các đoạn của một phiên gốc là các người dùng khác nhau.

Cat-Popularity and group-wise evaluation are implemented in `src/recommender/category.py`,
`src/recommender/category_evaluation.py` and `scripts/run_category_v2.py`. Yoochoose cold category
is recorded N/A without an independent catalog; it is never replaced by zero. Diginetica can use
the static catalog under the assumption described above. Non-oracle does not read target category;
oracle is a separate privileged condition and must not be mixed into non-oracle results. See
`docs/category/v2/RESULTS.md` for executed results and matched-cohort comparisons.

## Kiểm tra và bàn giao

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
node --test .github/tests/trusted-policy.test.cjs
```

Test fixture chạy offline trong CI. Chạy full raw là tác vụ dữ liệu riêng, không tự tải nhiều GB
mỗi lần push. Runner đọc lại Parquet để kiểm tra session/time disjoint, cold train rỗng,
segment không bắc cầu, seed/hash selection và coverage. Các số metric mô hình và research-readiness
vẫn chưa tự động hoàn tất chỉ vì pipeline dữ liệu đã chạy đúng.
