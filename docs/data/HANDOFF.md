# Bộ bàn giao ĐT1

1. Chốt mapping schema và chính sách dữ liệu lỗi trong schema.md.
2. Hoàn thiện bộ đọc/lọc trước khi dùng configs/data.example.toml làm config chạy thật.
3. Tạo manifest thật từ mẫu; đổi kind, điền dataset/version, source và commit đã chạy.
4. Mỗi file nguồn/đầu ra phải có vị trí lấy dữ liệu, SHA256 và số dòng; không đưa dataset lớn vào Git.
5. Ghi từng bước lọc, số event/session/item trước/sau và thứ tự áp dụng.
6. Ghi lệnh thực sự chạy được từ root, config và môi trường đã dùng.
7. Trung Chiến xác nhận đọc được dữ liệu; cả hai người nhận xác nhận dùng được metric chung.

Không dùng manifest mẫu trống làm bằng chứng hoàn tất nghiên cứu.
Metric đã có trong src/recommender/metrics.py và test tính tay trong tests/test_metrics.py.
Những phần xử lý dataset thật vẫn cần Bá Chiến phát triển kèm test riêng.
