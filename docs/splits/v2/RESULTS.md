# Kết quả baseline P0 v2 — Trung Chiến

Chạy thực tế trên raw Kaggle v1 khớp SHA-256 của bàn giao Bá Chiến. Dữ liệu được tái tạo
với commit `5eab92a`; mã baseline chạy ở commit `0256489`. Audit raw hash, cửa sổ, số lượng
và coverage khớp `dev` PR #3. Bytes Parquet trên Windows có thể khác bản Linux của Bá Chiến;
split ID lấy từ manifest thực tế, không mượn checksum của lần chạy khác.

Primary K=20. Giá trị bên dưới là tỷ lệ 0..1, mean ± sample std (ddof=1) qua ba split seed.
Random được lấy mean ba model seed trong từng split trước khi tổng hợp giữa split.
Các nhóm warm/cold khác số mẫu giữa seed; overall là trung bình micro theo event trong mỗi lượt,
không phải trung bình hai nhóm. Không dùng test để thay K, seed hoặc cửa sổ.

| Dataset | Model | Nhóm test | HR@20 | MRR@20 | NDCG@20 |
| --- | --- | --- | ---: | ---: | ---: |
| diginetica | Popularity | cold | 0.00000000 ± 0.00000000 | 0.00000000 ± 0.00000000 | 0.00000000 ± 0.00000000 |
| diginetica | Popularity | overall | 0.00844388 ± 0.00092022 | 0.00207090 ± 0.00012290 | 0.00345390 ± 0.00028649 |
| diginetica | Popularity | warm | 0.01054729 ± 0.00117097 | 0.00258677 ± 0.00016216 | 0.00431442 ± 0.00037091 |
| diginetica | Random | cold | 0.00044075 ± 0.00006833 | 0.00008401 ± 0.00003935 | 0.00016067 ± 0.00004475 |
| diginetica | Random | overall | 0.00054536 ± 0.00005515 | 0.00009510 ± 0.00001827 | 0.00018994 ± 0.00002539 |
| diginetica | Random | warm | 0.00057128 ± 0.00005225 | 0.00009776 ± 0.00001336 | 0.00019713 ± 0.00002111 |
| yoochoose | Popularity | cold | 0.00000000 ± 0.00000000 | 0.00000000 ± 0.00000000 | 0.00000000 ± 0.00000000 |
| yoochoose | Popularity | overall | 0.00644122 ± 0.00199224 | 0.00098569 ± 0.00014495 | 0.00211249 ± 0.00047528 |
| yoochoose | Popularity | warm | 0.00807077 ± 0.00273389 | 0.00122813 ± 0.00021450 | 0.00264099 ± 0.00068051 |
| yoochoose | Random | cold | 0.00071920 ± 0.00062288 | 0.00004514 ± 0.00003937 | 0.00017616 ± 0.00015273 |
| yoochoose | Random | overall | 0.00061345 ± 0.00035140 | 0.00015178 ± 0.00006888 | 0.00024974 ± 0.00001996 |
| yoochoose | Random | warm | 0.00057850 ± 0.00030290 | 0.00017420 ± 0.00008673 | 0.00026324 ± 0.00001733 |

## Số mẫu và coverage

| Dataset | Split seed | Test warm | Test controlled-cold | Loại khỏi primary | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| diginetica | 42 | 43,184 | 11,215 | 16,890 | 76.3077% |
| diginetica | 43 | 44,040 | 10,357 | 16,892 | 76.3049% |
| diginetica | 44 | 43,448 | 10,951 | 16,890 | 76.3077% |
| yoochoose | 42 | 1,138 | 311 | 3 | 99.7934% |
| yoochoose | 43 | 1,142 | 307 | 3 | 99.7934% |
| yoochoose | 44 | 1,221 | 228 | 3 | 99.7934% |

## Diễn giải và giới hạn

- Popularity cold HR/MRR/NDCG bằng 0 trong **lần chạy và K=20 này**: có hơn 20 item warm điểm dương, còn mọi controlled-cold có count=0. Không suy rộng thành định lý cho mọi K/candidate.
- Random có thể đạt điểm ở nhóm cold vì cold vẫn nằm trong candidates; các seed có thể bằng 0 khi ít mẫu. Không thay seed dựa vào kết quả.
- Yoochoose test có 479 phiên, 1.452 target trước loại và 1.449 target primary mỗi seed; độ bất định lớn. Đây không phải tuyên bố tái tạo benchmark ngoài dự án.
- Diginetica loại khoảng 23,69% target khỏi primary; đã báo rõ coverage, không xem đó là accuracy.
- C là cold do can thiệp trên train, không chứng minh thời điểm sản phẩm xuất hiện trên thị trường.
- Category/cold CatPopularity của Yoochoose vẫn N/A khi thiếu catalog độc lập. Chưa triển khai CatPopularity, chưa xác nhận Bảo Long đã nhận hoặc nhóm đã phê duyệt báo cáo.

## Bằng chứng

- `runs.csv` / `runs.json`: 144 dòng từng dataset/split seed/model seed/window/group, kèm split ID và input manifest hash.
- `summary.json`: mean/sample std theo model seed trong split và theo ba split mean.
- `split_acceptance.json`: kiểm tra checksum, cold selection, train/candidate/support, session/time, segments, coverage và đối chiếu dev.
- `manifest.json`: commit/source hashes, config, môi trường và checksum các file kết quả.
- `data_manifests/`: manifest dữ liệu chính xác của lần chạy local; các path nguồn tuyệt đối là provenance lịch sử. Loader dùng input-root hiện tại và đường dẫn payload tương đối, không yêu cầu máy khác có cùng ổ đĩa.
- `delivery.json`: ZIP, URL, SHA-256 và inventory từng file để người nhận lấy cùng split.
- `independent_metric_check.json`: đối chiếu toàn bộ 36 dòng Popularity bằng phép đếm/rank/metric SQL độc lập.
- 114 test Python, 13 test workflow, Ruff và smoke đã chạy đạt tại local; CI GitHub xác nhận riêng sau push.
