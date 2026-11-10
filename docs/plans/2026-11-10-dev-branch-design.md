# Luồng tích hợp nghiên cứu qua dev

Yêu cầu mới: đổi nhánh cá nhân thành bao-long, ba-chien, trung-chien và tạo dev.
Nhánh cá nhân tích hợp qua PR vào dev. Main giữ bản ổn định; chỉ nhận dev khi nghiên cứu xong.

CI chạy trên PR vào dev/main và push dev/main. Job branch-policy kiểm tra nguồn PR trong cùng
repository. PR dev -> main còn yêu cầu checklist nghiên cứu, bốn file bằng chứng và protocol đã chốt.
CI kiểm tra sự hiện diện và khai báo, không tự xác nhận chất lượng nghiên cứu; vẫn cần một review.
Cả dev và main yêu cầu bốn check, review và đồng bộ nhánh đích, cấm force-push/xóa.

Chuyển cấu hình qua dev trước; giữ nguyên main cho tới lần promotion được review.
Các nhánh cá nhân giữ commit hiện có khi đổi tên; thành viên nhập dev trước khi bắt đầu công việc.
