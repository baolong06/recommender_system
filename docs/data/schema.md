# Schema bàn giao của Bá Chiến

Schema pipeline Yoochoose và Diginetica; manifest và dữ liệu nghiên cứu vẫn cần review.

| Trường | Kiểu chuẩn hóa | Yêu cầu |
| --- | --- | --- |
| session_id | string | Không rỗng; giữ ID thật và quy tắc namespace theo dataset |
| item_id | string | Không mất số 0 đầu; cùng mapping trong event và catalog |
| timestamp | int64 | Unix seconds UTC, để tương thích |
| timestamp_ms | int64 | Unix milliseconds UTC; dùng để sắp xếp và loại click trùng |
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
| Yoochoose | | cột 2 (ISO, UTC) | timestamp | Unix seconds + timestamp_ms giữ mili giây |
| Yoochoose | | cột 3 | item_id | Đọc dạng chuỗi, giữ số 0 đầu |
| Yoochoose | | cột 4 | category_id | Rỗng -> "UNK"; item nhiều category -> category xuất hiện nhiều nhất, đồng hạng chọn mã nhỏ hơn |
| Diginetica | train-item-views.csv (`;`) | sessionId | session_id | Chuỗi |
| Diginetica | | itemId | item_id | Chuỗi |
| Diginetica | | eventdate + timeframe | timestamp | eventdate (UTC) + timeframe(ms); giữ cả giây và mili giây |
| Diginetica | product-categories.csv (`;`) | categoryId | category_id | Join theo itemId; thiếu -> "UNK"; trùng itemId giữ dòng đầu |

Dòng thiếu session/item hoặc ngày/offset lỗi được giữ đến cleaning để ghi số lượng raw,
rồi bỏ ở bước drop_missing. ID chỉ có khoảng trắng được coi là thiếu. Timestamp trước epoch
bị loại ở drop_invalid_timestamp. Offset Diginetica phải là số nguyên không âm.
Dữ liệu sau cleaning được validate trước khi xuất Parquet.

Loại trùng theo session_id, item_id, timestamp_ms, giữ thứ tự stable khi cùng thời điểm.
Hai click cách nhau mili giây trong cùng một giây vẫn được giữ. Hàm cleaning vẫn nhận fixture
cũ chỉ có timestamp giây; các reader thật luôn trả timestamp_ms. Quy tắc này cần được nhóm
duyệt trước khi chốt protocol nghiên cứu.

Các manifest đã commit trước lần sửa này có review_status=requires-rerun: số lượng và checksum
phản ánh thuật toán cũ. Phải chạy lại bằng command được lưu trên dataset gốc, cập nhật version,
nguồn truy cập và review trước khi dùng kết quả. Không tự sửa số thống kê để giả làm đã chạy lại.
Lệnh reproduce_command được quote theo shell POSIX; trên PowerShell truyền từng tham số và
đặt dấu nháy quanh đường dẫn hoặc source-reference chứa khoảng trắng. raw_files.rows đếm bản ghi,
không tính header và vẫn tính dòng cuối không có newline.
