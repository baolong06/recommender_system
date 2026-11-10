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
