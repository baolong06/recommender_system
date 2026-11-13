# Bàn giao Bảo Long — group-wise và Cat-Popularity P0 v2

Nhận nguyên bộ split Trung Chiến, xác minh SHA-256, metadata được phép và chạy bốn
baseline trên cùng dữ liệu. Xem [báo cáo](v2/RESULTS.md), [kết quả từng lượt](v2/runs.csv),
[paired differences](v2/paired_differences.json) và [provenance](v2/manifest.json).

## Cài, tải và tái lập

Cài dependency lock và package theo README nhánh `bao-long`, rồi từ root:

```powershell
python scripts/download_splits_v2.py
python scripts/download_raw.py --dataset diginetica --cache-dir artifacts/kagglehub
python scripts/run_category_v2.py --output-dir artifacts/reproduced-category-v2
python scripts/verify_category_results.py --input-root data/protocol_v2 --runs artifacts/reproduced-category-v2/runs.json --output artifacts/independent-category-check.json
```

Raw Diginetica catalog chỉ dùng xác minh mapping. Yoochoose tái dựng mapping từ final
train, không đọc category trong holdout. Split ID/data_manifest_sha256 phải khớp bảng
Trung Chiến; runner từ chối payload hoặc reference bị sửa. Mọi lần chạy dùng thư mục
output mới. Cùng input/config/interpreter phải tạo cùng runs/summary/paired differences.

Không chia lại split, không refit validation/test, giữ candidates W∪C và K=20. Dùng
ba split seed 42/43/44, Random có ba model seed bên trong mỗi split. Dữ liệu lớn đã
có ở [Release của Trung Chiến](https://github.com/baolong06/recommender_system/releases/tag/trung-chien-p0-v2-2026-11-13);
báo cáo nhỏ và công thức được version trong nhánh này.

## Hợp đồng code và cách đọc kết quả

`GroupMetrics(k).add(target, ranking, group, reason)` chấm streaming theo target.
`ranking=None` yêu cầu lý do không hỗ trợ. Kết quả có n_eligible/n/support_fraction,
metric theo mẫu, status ok/partial/N/A và thống kê lý do. Hàm `evaluate_groups` cũ
giữ schema output để các caller trước đây dùng lại.

`CategoryPopularity.predict_non_oracle(prefix)` chỉ nhận prefix. Modal category
được chọn theo số occurrence; hòa lấy occurrence gần nhất. Không có category biết
được thì fallback global Popularity. `predict_oracle(target_category)` chỉ nhận
category từ mapping hợp lệ; UNK trả không hỗ trợ. Cả hai ưu tiên cùng category, rồi
train event count giảm dần, ID chuỗi tăng dần; không thay candidate hay tạo cold count.

Các dòng `full-primary` là Random/Popularity kiểm chứng lại với Trung Chiến. Các dòng
`oracle-supported` và `non-oracle-supported` chứa Cat cùng các baseline trên **đúng
cùng target được Cat hỗ trợ**. Chỉ so trong cùng cohort. Không lấy overall partial
so trực tiếp với full-primary. n là số target chấm, không phải số phiên; cold N/A
khác cold có mẫu nhưng score=0. Phần chênh lệch đã ghép theo dataset/window/seed/group.

Oracle có thông tin nhãn category, không tương đương deployable non-oracle và không
bảo đảm upper bound metric với ranking cố định. Yoochoose cold Cat là N/A vì không
có catalog độc lập. Diginetica metadata lịch sử chưa được xác minh; chỉ dùng giả định
catalog tĩnh theo protocol. Giữ nguyên các giới hạn này trong bảng hoặc bài báo.

## Trạng thái bàn giao

Phần thực thi kỹ thuật, tái lập và CI được ghi ở RESULTS.md. Việc người khác review,
nhóm xác nhận công thức/protocol và phê duyệt nội dung bài báo là các bước còn mở.
Không đánh dấu research-readiness complete, không thay status protocol thành approved
hoặc tự merge dev/main chỉ vì test đạt. PR của `bao-long` được cập nhật theo thành phẩm
cuối để người khác review code và số liệu cùng nhau.
