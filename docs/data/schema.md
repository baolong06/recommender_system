# Schema bàn giao của Bá Chiến

Khung bàn giao ban đầu; cần xác nhận mapping từ file gốc Yoochoose và Diginetica.
Đây chưa phải mô tả một dataset thật đã xử lý.

| Trường | Kiểu chuẩn hóa | Yêu cầu |
| --- | --- | --- |
| session_id | string | Không rỗng; giữ ID thật và quy tắc namespace theo dataset |
| item_id | string | Không mất số 0 đầu; cùng mapping trong event và catalog |
| timestamp | integer | Unix seconds; ghi nguồn timezone và quy tắc đổi đơn vị |
| category_id | string | Giữ mã gốc; thống nhất chính sách thiếu/nhiều category |

Trong PR bộ đọc, bổ sung bảng tên cột gốc -> tên chuẩn cho từng dataset,
các trường hợp dữ liệu lỗi và cách xử lý. Không mặc định hai nguồn có cùng cách lưu category.

`tests/fixtures/raw_events.example.csv` là ví dụ tổng hợp để phát triển bộ đọc/lọc,
có phiên ngắn và item hiếm. Nó không đáp ứng các ngưỡng dữ liệu sạch và không phải dữ liệu P0.
Fixture split đã có trong `tests/fixtures/session_dataset.json` dùng cho smoke riêng.
## Mapping cột gốc -> chuẩn

| Dataset | File gốc | Cột gốc | Cột chuẩn | Quy tắc |
| --- | --- | --- | --- | --- |
| Yoochoose | yoochoose-clicks.dat (không header) | cột 1 | session_id | Đọc dạng chuỗi |
| Yoochoose | | cột 2 (ISO, UTC) | timestamp | Unix seconds, cắt phần mili giây |
| Yoochoose | | cột 3 | item_id | Đọc dạng chuỗi, giữ số 0 đầu |
| Yoochoose | | cột 4 | category_id | Rỗng -> "UNK"; item nhiều category -> category xuất hiện nhiều nhất, đồng hạng chọn mã nhỏ hơn |
| Diginetica | train-item-views.csv (`;`) | sessionId | session_id | Chuỗi |
| Diginetica | | itemId | item_id | Chuỗi |
| Diginetica | | eventdate + timeframe | timestamp | eventdate (UTC) + timeframe(ms) // 1000 |
| Diginetica | product-categories.csv (`;`) | categoryId | category_id | Join theo itemId; thiếu -> "UNK"; trùng itemId giữ dòng đầu |

Trường hợp lỗi: dòng thiếu session/item/timestamp bị bỏ; dòng trùng (cùng session, item, timestamp
sau khi làm tròn giây) bị bỏ, nên hai click khác nhau trong cùng một giây bị gộp.
