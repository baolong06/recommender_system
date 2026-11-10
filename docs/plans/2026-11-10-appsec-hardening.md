# Thiết kế gia cố AppSec đã duyệt

Chủ repository đã duyệt các mục gia cố của báo cáo ngày 10/11/2026. Thực hiện trên
bao-long, tạo PR vào dev; giữ main ổn định và không bỏ qua approval của người khác.

Tách trusted branch policy sang pull_request_target từ nguồn workflow được duyệt,
chỉ dùng metadata và bounded regular blobs của PR, không execute head code.
Giữ branch-policy hiện có cho quá trình bootstrap. Chỉ bật required trusted check sau
khi workflow có trên main và chạy thật. Bổ sung event edited, CODEOWNERS, locked hashed
dependencies/build tools, audit/SBOM và Dependabot với đường staging bao-long.

Không tự dựng rubric 11 lĩnh vực khi nguồn không có. Mọi giới hạn kích hoạt qua
default branch, phạm vi SBOM và vai trò review được ghi tại docs/security.md.
