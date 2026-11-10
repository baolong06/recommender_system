# Bộ bàn giao ĐT2

1. Nhận manifest dữ liệu thật từ Bá Chiến; xác minh phiên bản/checksum trước khi chạy.
2. Chốt các mục pending-team-agreement trong configs/split.example.toml với cả nhóm.
3. Phát triển runner split thật; mẫu config chưa có runner để chạy trực tiếp.
4. Tạo train/validation/test/cold IDs, ghi số lượng, SHA256, seed và lệnh tái tạo vào manifest thật.
5. Kiểm tra cold item không có trong dữ liệu fit, đúng quy tắc session/time và history/target.
6. Chạy Random/Popularity với metric dùng chung; ghi candidate, tie-break và seed mô hình riêng.
7. Giao đúng cùng split cho Bảo Long; nếu đổi split, tạo version mới và báo người nhận chạy lại.

baseline_results.example.csv chỉ có header để định nghĩa cột, chưa có số liệu nghiên cứu.
Số liệu thật cần từng seed và bản mean ± sample std; không dùng fixture để điền bảng P0.
Manifest mẫu có null/trường trống phải được hoàn thiện và review trước khi làm bằng chứng.
