# Luồng nhánh hiện tại

Ba nhánh phụ đã được xóa sau khi bảo toàn công việc trên nhánh cá nhân.

| Nhánh làm việc cá nhân | Nhánh nhận PR |
| --- | --- |
| `ba-chien` | `dev` |
| `trung-chien` | `dev` |
| `bao-long` | `dev` |

Chỉ `dev` được gửi PR vào `main` sau khi hoàn tất nghiên cứu và có bằng chứng được review.
Policy chặn nguồn ngoài ba nhánh cá nhân vào dev, nhánh cá nhân đi thẳng main và fork.
Ngoại lệ Dependabot staging vào `bao-long` vẫn được giữ.

CI chạy khi push trên ba nhánh cá nhân, dev và main; PR vào dev/main và Dependabot staging
trên bao-long. Không cần tạo nhánh phụ để phát triển. Đồng bộ bằng merge origin/dev,
xử lý xung đột rồi chạy kiểm tra; không force-push để đồng bộ.

Thành phẩm PR #2 đã được ghép vào ba-chien. Pipeline dữ liệu giữ nguyên các bản sửa;
manifest requires-rerun vẫn cần dữ liệu gốc để tái tạo, không phải kết quả đã được xác nhận.
