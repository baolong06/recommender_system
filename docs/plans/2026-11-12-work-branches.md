# Luồng nhánh làm việc và tích hợp

| Nhánh làm việc | PR vào nhánh cá nhân | PR tích hợp |
| --- | --- | --- |
| `bachien-dev` | `ba-chien` | `ba-chien` → `dev` |
| `trungchien-dev` | `trung-chien` | `trung-chien` → `dev` |
| `baolong-dev` | `bao-long` | `bao-long` → `dev` |

Chỉ `dev` được gửi PR vào `main`, sau khi hoàn tất nghiên cứu và có bằng chứng được review.
Git không lưu quan hệ cha/con của branch. Policy kiểm tra đúng cặp nguồn/đích, chặn đi tắt,
chéo thành viên và fork. Ngoại lệ Dependabot staging vào `bao-long` vẫn được giữ.

CI chạy khi push lên cả tám nhánh và khi mở/cập nhật/đổi base PR vào ba nhánh cá nhân,
`dev`, `main`. Trusted policy vẫn chỉ chạy nguồn tin cậy từ nhánh đích, không chạy code PR.
Bản trusted workflow mới có hiệu lực sau khi được review và tích hợp vào các nhánh đích;
việc sửa file trên một nhánh không tự cập nhật branch protection/ruleset của GitHub.

Đồng bộ nền chung bằng merge nhánh đích vào nhánh làm việc, xử lý xung đột và chạy kiểm tra.
Không force-push để đồng bộ. PR #2 chuyển sang `bachien-dev` → `ba-chien`.

## Kiểm tra dữ liệu

Cài `requirements-dev.txt` với `--require-hashes --only-binary=:all:`, rồi cài editable
`--no-build-isolation --no-deps -e .`. Pandas và PyArrow bắt buộc, không skip test nếu thiếu.
Chạy `python -m pytest`, Ruff và `node --test .github/tests/trusted-policy.test.cjs`.
Manifest cũ cần tái tạo trên dataset gốc; fixture CI không xác nhận kết quả nghiên cứu.
