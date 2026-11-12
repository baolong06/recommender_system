## Thay đổi và người phụ trách

Mô tả phần thay đổi, lý do và đầu ra được bàn giao.

## Kiểm tra

- [ ] Đúng luồng: nhánh cá nhân -> `dev`, hoặc `dev` -> `main` khi nghiên cứu xong.
- [ ] Đã đồng bộ với nhánh đích và xử lý xung đột.
- [ ] Ruff và pytest chạy đạt trên máy.
- [ ] Có kiểm thử cho phép tính/hợp đồng dữ liệu mới hoặc thay đổi.
- [ ] Nếu đổi metric/split/group-wise: đã nêu ảnh hưởng và báo người dùng lại phần đó.
- [ ] Không đưa dataset lớn, token hoặc kết quả minh họa thành kết quả thật.
- [ ] Đã ghi rõ quyết định protocol mới, seed, nguồn dữ liệu khi có liên quan.

## Bằng chứng

Ghi lệnh kiểm tra đã chạy; nếu có kết quả nghiên cứu, dẫn bản lưu và manifest tương ứng.

Nếu PR từ `dev` vào `main`: hoàn tất `docs/research-readiness.json`, dẫn manifest dữ liệu/split,
kết quả ba seed và báo cáo; chốt protocol. Người review kiểm tra các bằng chứng trước khi duyệt.
