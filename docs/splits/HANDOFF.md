# Bàn giao Trung Chiến — P0 v2

Trung Chiến tiếp nhận PR #3 của Bá Chiến trên dev, tái tạo cả hai dataset từ raw
đúng SHA-256, xác minh split và thực thi Random/Popularity. Xem
[RESULTS.md](v2/RESULTS.md) và [bảng từng lượt](v2/runs.csv).

## Người nhận lấy đúng split

Từ checkout nhánh `trung-chien`, cài môi trường như README ở root rồi chạy:

```powershell
python scripts/download_splits_v2.py
```

[GitHub Release](https://github.com/baolong06/recommender_system/releases/tag/trung-chien-p0-v2-2026-11-13)
chứa hai ZIP theo dataset, mỗi ZIP có neutral, validation/test, U0, train/cold/incidental/
candidates/category mapping của cả ba seed và manifest chính xác. Mỗi asset dưới 2 GiB.
`docs/splits/v2/delivery.json` ghi SHA-256 ZIP và từng payload. Bộ tải kiểm tra cả hai lớp.
Đầu ra là `data/protocol_v2/<dataset>/`. Có thể dùng `--dataset diginetica` hoặc `yoochoose`.
Dataset directory đã tồn tại sẽ không bị ghi đè; dùng `--output-dir` mới nếu cần.

## Chạy lại kết quả

```powershell
python scripts/run_baselines_v2.py --input-root data/protocol_v2 --output-dir artifacts/reproduced-baselines --reference-root docs/data/protocol_v2
```

Runner kiểm tra toàn bộ input rồi mới fit; cùng payload/interpreter/config phải tạo cùng
`runs.json` và `summary.json`. Source hashes và commit đã thực thi có trong `v2/manifest.json`.
Khi tái tạo từ raw bằng `scripts/run_protocol_v2.py`, encoding Parquet có thể khác theo
nền tảng; runner dùng manifest hash mới và đối chiếu semantic audit với dev, không giả
checksum cũ. Không trộn với `data/processed` legacy.

## Hợp đồng cho Bảo Long

Với mỗi dataset và seed, dùng đúng `splits/seed-<seed>/train.parquet`,
`candidates.parquet`, `cold_items.parquet`, `category_mapping.parquet`; validation/test
là hai file chung dưới `splits/`. Không tự random-split lại hoặc refit bằng holdout.

- C=ceil(20%×U0), chọn SHA-256 như protocol v2. Candidates W∪C; I0/natural-unseen
  không vào primary metric nhưng phải báo coverage. Không nối qua event OOV/bị xóa.
- Dùng `recommender.data.examples_v2.iter_examples` và metric chung. Query identity
  gồm dataset/split/window/session/raw_row_index; một phiên có nhiều next-item target.
- Giữ item đã xem. Báo K=20, overall/warm/controlled-cold và số mẫu; nhóm không có mẫu ghi N/A.
- Đối chiếu đúng split ID và data_manifest_sha256 trong `v2/runs.csv`, không chỉ tên dataset.
- Random có ba model seed trong mỗi split. Popularity xác định và model_seed trống.
  Mean/std giữa split dùng ba split mean; không coi chín lượt Random là chín split độc lập.
- Diginetica category dùng catalog tĩnh theo giả định đã ghi; Yoochoose cold category
  vẫn không có nguồn độc lập. Không lấy target category cho non-oracle hoặc relabel N/A thành 0.

## Bằng chứng đã thực hiện

- [x] Raw hashes và semantic split audit khớp bàn giao dev cho hai dataset.
- [x] Ba seed 42/43/44; cold không vào train, train/holdout khác phiên và khác cửa sổ.
- [x] Candidates/support bằng số đếm train thực tế; segment không bắc cầu; coverage đếm lại.
- [x] Random/Popularity validation/test đầy đủ, 144 dòng kết quả và tổng hợp sample std.
- [x] 36 dòng Popularity được đối chiếu bằng SQL độc lập, sai số cho phép 1e-12.
- [x] 114 test Python, 13 test workflow, Ruff và smoke đạt local.
- [ ] Bảo Long xác nhận đã nhận và dùng bộ split này.
- [ ] Review độc lập/phê duyệt protocol và báo cáo nghiên cứu của nhóm.

Các ô chưa xác nhận không được tự đánh dấu chỉ vì code/CI thành công. Phần CatPopularity
và kết luận so sánh mô hình thuộc bước tiếp theo. Xem giới hạn Yoochoose test nhỏ và
coverage Diginetica trong RESULTS.md trước khi diễn giải metric.
