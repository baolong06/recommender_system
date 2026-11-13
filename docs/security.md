# Gia cố CI/AppSec - 10/11/2026

## Phạm vi và trạng thái

Phần này xử lý các khoảng trống trong báo cáo trước sửa mà chủ repo đã duyệt:
nguồn luật nhánh, sự kiện đổi base, theo dõi lỗ hổng và khóa môi trường.
Không có bộ rubric 11 lĩnh vực, trình báo cáo hoặc thư viện CVE gốc trong dự án;
không tự chấm điểm, tạo chứng nhận hoặc coi tài liệu P0 là AppSec runbook.

**Hiệu lực sau khi PR vào dev được review và merge:** CI khóa dependency/hashes,
audit và SBOM, chạy lại khi đổi base, CODEOWNERS của dev. Cấu hình repository
đã bật Dependabot alerts/security updates; việc đánh giá alert phụ thuộc dependency graph.

**Chưa kích hoạt tự động ở nhánh mặc định:** workflow `Trusted branch policy` và lịch
Dependabot trong `.github/dependabot.yml`. GitHub cần định nghĩa đó trên nhánh mặc định
`main`. Giữ đúng quy trình dev -> main sau nghiên cứu; không tạm tắt bảo vệ để tự merge.

## Luật nhánh từ nguồn tin cậy

`CI / branch-policy` vẫn chạy trên code PR như kiểm tra hồi quy, vì check này đang
được cấu hình bắt buộc. Nó không phải nguồn quyết định độc lập khỏi PR.

Workflow mới `Trusted branch policy` chạy bằng `pull_request_target`, có các giới hạn:

- Nguồn workflow/checker lấy từ `github.workflow_sha`, không lấy Python từ head PR.
- Chỉ `contents: read` và `pull-requests: read`, không dùng secret hoặc quyền ghi.
- Không checkout head PR, cài dependency, dùng cache hay tải artifact từ PR.
- Đọc metadata PR mới nhất qua REST API; đọc bằng chứng tại head SHA đó dưới dạng dữ liệu.
- Chỉ nhận regular blob, giới hạn 512 KiB/file và 2 MiB tổng; từ chối symlink,
  đường dẫn tuyệt đối, backslash/colon/control characters và `..`.
- Tách metadata đáng tin cậy khỏi thư mục chứa file dữ liệu PR. Python dùng `-I`
  để không import từ thư mục PR hoặc biến môi trường Python.
- Chạy lại khi `opened`, `synchronize`, `reopened`, `edited`, `ready_for_review`.

Khi workflow đã có trên main và chạy thật trên PR sau đó, quản trị viên xác minh
nguồn lần chạy là `pull_request_target` rồi thêm check `trusted-branch-policy`
(GitHub Actions app) vào bảo vệ dev/main. Không đặt check chưa tồn tại thành bắt buộc
trong giai đoạn bootstrap vì sẽ làm mọi PR chờ vô hạn.

Job names/app_id không tự gắn check với duy nhất một file workflow. CODEOWNERS
và review thay đổi `.github/**` vẫn cần thiết; không tuyên bố không thể bypass dưới
mọi mô hình quyền. Chủ repo có quyền sửa thiết lập GitHub vẫn là ranh giới tin cậy.

## Dependencies

- `requirements-dev.in`: dependency trực tiếp và build tools, bản txt là toàn bộ lock có hash.
- `requirements-audit.in`: thêm pip-audit; bản txt khóa cả công cụ kiểm tra và dependency của nó.
- CI cài với `--require-hashes --only-binary=:all:`; không build package registry từ source.
- Package local cài riêng với `--no-build-isolation --no-deps -e .`; setuptools/wheel
  đã cài từ lock và trùng phiên bản khai báo build-system. CI không tải build tools trôi nổi.
- `dependency-audit` dùng pip-audit với advisory PyPI, không chạy pip/dependency resolver
  trên manifest PR trong quá trình audit. Dịch vụ lỗi, dependency không thu thập được
  hoặc có advisory khiến check thất bại; không tự bỏ qua advisory để làm xanh.
- Xuất JSON audit và CycloneDX SBOM của tập lock audit, lưu artifact 14 ngày.
  SBOM này không bao phủ hệ điều hành runner hoặc nội dung toàn bộ GitHub Action.

Tạo lại lock bằng uv 0.11.21, Python 3.12:

```bash
uv pip compile requirements-dev.in --generate-hashes --universal --python-version 3.12 --no-header -o requirements-dev.txt
uv pip compile requirements-audit.in --generate-hashes --universal --python-version 3.12 --no-header -o requirements-audit.txt
```

Thay đổi build tools cần cập nhật cả `pyproject.toml` và input/lock.
Test `test_dependency_lock.py` kiểm tra khớp dependency trực tiếp/build tools và hash.

## Dependabot và đường đi cập nhật

Cấu hình tuần cho pip/GitHub Actions đặt `target-branch: bao-long`. Bot đề xuất vào nhánh
cá nhân; người phụ trách kiểm tra và tạo lại lock khi cần, sau đó bao-long -> dev -> main.
Chỉ actor `dependabot[bot]` với nhánh `dependabot/` trong cùng repo được dùng đường
staging vào bao-long; không có ngoại lệ bot đi thẳng vào dev hoặc main.

Dependabot security updates dùng dependency graph của default branch; chúng có thể đề
xuất PR bảo mật vào main theo hành vi GitHub. Không bypass branch policy: chuyển bản sửa
qua nhánh cá nhân -> dev, review rồi xử lý promotion phù hợp. Cấu hình version-update
trong repo chỉ được GitHub nạp khi đã có trên default branch.

## Review và xử lý phát hiện

CODEOWNERS dùng hai tài khoản có quyền ghi đã xác minh: baolong06 và luongtrungchien-249.
Tác giả không tự duyệt PR của mình. Nhóm kiểm tra kỹ workflow, luật nhánh, protocol,
readiness và lockfile khi review. Không đưa kết quả fixture vào bằng chứng nghiên cứu thật.

Nếu audit phát hiện advisory: xác minh ảnh hưởng, cập nhật `.in`/lock và chạy lại,
ghi rõ lý do trong PR. Chưa có đối chiếu đầy đủ thư viện CVE/CISA KEV nội bộ.
Secret scanning/push protection của GitHub đang bật; quyền đọc alert chi tiết có thể
bị giới hạn. Không coi kết quả API thiếu quyền là không có secret.

## Kiểm chứng

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
node --test .github/tests/trusted-policy.test.cjs
python -m pip_audit --disable-pip --no-deps --require-hashes --strict -r requirements-audit.txt
```

Node.js 24 trên GitHub-hosted runner dùng cho test workflow; khi kiểm tra toàn bộ
trên máy, cài Node.js 24 hoặc mới hơn. Test mock API/ghi file để kiểm tra các đường
đi dữ liệu nguy hiểm; việc kích hoạt `pull_request_target` còn cần lần chạy GitHub thật
sau khi workflow được đưa lên main qua review.
