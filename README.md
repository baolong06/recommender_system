# trung-chien - Hướng dẫn làm việc của Trung Chiến

**Đề tài 2: Chia dữ liệu cold-start và xây dựng baseline Random/Popularity.**

Bạn làm trên nhánh `trung-chien`, gửi PR vào `dev`. Nhiệm vụ của bạn là tạo một bộ split
và một luật đánh giá dùng chung, rồi đo hai baseline mốc sàn trên đúng luật đó.
Bảo Long dùng lại split và kết quả của bạn để so sánh mô hình category.

## 1. Bạn cần nhận gì trước khi bắt đầu?

| Đầu vào | Người cung cấp | Bạn phải xác minh |
| --- | --- | --- |
| Dữ liệu sạch | Bá Chiến | Schema, phiên bản, checksum và số lượng |
| Metric HR/MRR/NDCG | Bá Chiến | Giao diện gọi hàm, cutoff K và test tính tay |
| Protocol nghiên cứu | Cả nhóm duyệt | Item universe, cách chia, candidate, tie-break và seed |

Bạn có thể phát triển thuật toán split và baseline trên fixture trong lúc chờ dữ liệu thật.
Không tự viết lại metric để tránh chờ; dùng module chung khi nó được bàn giao.

**Hiện trạng nhánh:** đã có khung Python, validator, metric, Random/Popularity tham chiếu,
fixture, CI và dependency lock để setup/chạy kiểm tra ngay. Nhánh có thêm
`configs/split.example.toml`, manifest split, bảng cột kết quả và checklist trong `docs/splits/`.
Chưa có bộ sinh split Yoochoose/Diginetica hoàn chỉnh; các file mẫu không phải kết quả nghiên cứu.

## 2. Công việc split - làm theo thứ tự này

### A. Chốt protocol trước khi sinh file

Ghi vào PR/tài liệu và thống nhất với cả nhóm:

1. 20% cold item được chọn từ tập item nào, tại thời điểm nào, làm tròn thế nào.
2. Chia train/validation/test theo session hay thời gian; mốc và tỷ lệ cụ thể.
3. Làm sạch ở bước nào; thống kê nào chỉ được fit trên train để tránh biết tương lai.
4. Nếu xóa cold event khỏi train, xử lý phiên bị ngắn/đứt chuỗi ra sao.
5. Tập candidate và khả năng xuất hiện cold item; xử lý item đã xem và điểm bằng nhau.
6. Giữ một split cố định hay lặp split seed; seed mô hình là một thông tin riêng.

Giữ cold item **20%** theo P0, không tự thử 10%/30% để chọn kết quả đẹp.
Quy tắc fixture `ceil`, top-3 và toàn catalog chỉ dùng kiểm tra; chưa phải protocol nghiên cứu đã duyệt.

### B. Viết bộ sinh split có thể tái tạo

- Chuẩn hóa thứ tự item trước khi chọn ngẫu nhiên; lưu danh sách cold IDs và seed.
- Không để cold item xuất hiện trong dữ liệu dùng để fit baseline.
- Tạo các ví dụ có history và next-item target theo protocol; không chuyển tương tác tương lai vào history.
- Lưu train/validation/test và cold IDs thành một bộ có cùng data version/split ID.
- Nếu tạo nhiều prefix cho một session, dùng `example_id` riêng nhưng vẫn kiểm tra session
  không tràn qua các split theo quy tắc đã chốt; không ép dùng validator một-mẫu/session của fixture.
- Dữ liệu lớn nằm ngoài Git; trong repo giữ script, config, schema và manifest nhỏ.

**Đầu ra bắt buộc:** script tái tạo, config protocol, split files, cold IDs và manifest checksum.

### C. Kiểm tra rò rỉ trước khi chấm điểm

| Kiểm tra | Cách kết luận |
| --- | --- |
| Cold item trong train | Giao giữa cold IDs và item train phải rỗng |
| Session qua các split | Đúng quy tắc session/temporal đã duyệt; không âm thầm dùng cùng phiên ở train và test |
| Thứ tự thời gian | History không biết tương lai của target; fit/tune đúng nguồn |
| Metadata/candidate | Nguồn và thời điểm khả dụng đúng protocol; không lấy label test làm tín hiệu |
| Tính tái lập | Cùng input/config/seed tạo cùng split/checksum hoặc có giải thích định dạng lưu |
| Khả năng đánh giá | Báo số mẫu warm/cold và trường hợp target không nằm trong candidate |

Cold item xuất hiện trong history của validation/test có được phép không phải do bạn tự đoán;
ghi rõ quy ước cùng nhóm. Điều kiện bắt buộc đã nêu là vắng khỏi dữ liệu fit.

## 3. Công việc baseline - Random và Popularity

Sau khi split qua kiểm tra, triển khai runner dùng đúng metric của Bá Chiến:

| Baseline | Yêu cầu triển khai | Phải kiểm thử |
| --- | --- | --- |
| Random | Dùng candidate chung; seed có thể tái lập; không tạo item trùng trong ranking | Cùng seed có cùng đầu ra, đúng tập item và độ dài ranking |
| Popularity | Đếm chỉ từ train, tie-break rõ; không học từ validation/test | Sửa test không làm đổi thống kê fit; cold item có count 0 theo train |

`src/recommender/baselines.py` hiện có `random_ranking(candidates, seed)` và
`popularity_ranking(train, candidates)`. Đây là hàm nhỏ cho fixture, chưa phải runner dataset lớn.
Nếu dùng Random theo từng ví dụ, định nghĩa rõ cách tạo RNG và thứ tự ví dụ; không khởi tạo lại
cùng một RNG cho mỗi query mà không giải thích. Không bắt Random phải tốt hơn/kém hơn một số cố định.

Nếu cold item được đưa vào candidate với score 0 của Popularity, thứ tự tie có thể làm chúng
được xếp hạng; không khẳng định cold HR luôn bằng 0 trong mọi protocol.
Ghi lại candidate/tie-break khi báo kết quả để Bảo Long so sánh công bằng.

**Bảng kết quả bàn giao:** dataset, data version, split ID/seed, model seed, model,
K, metric và số mẫu. Chạy tối thiểu ba seed theo kế hoạch đã chốt; lưu từng lượt,
trung bình và sample std (`ddof=1`). Baseline xác định có std = 0 vẫn là kết quả hợp lệ.

## 4. Setup trên nhánh trung-chien

Cần Git, Python 3.12; Node.js 24 hoặc mới hơn để kiểm tra workflow. Không cần GPU:

```powershell
git clone https://github.com/baolong06/recommender_system.git
cd recommender_system
git switch trung-chien
git fetch origin
```

Nếu đã clone thì bỏ hai dòng đầu. Sau `git status` và khi đã lưu công việc, chạy
`git pull --ff-only origin trung-chien` trên đúng nhánh để nhận khung mới.
Không cần merge dev để setup lần đầu. Khi cần nhận phần chung mới, lưu công việc rồi chạy:

```powershell
git fetch origin
git merge origin/dev
```

Nếu README đang xung đột khi nhận dev, giữ hướng dẫn riêng của bạn:

```powershell
git restore --ours -- README.md
git add README.md
```

Chỉ áp dụng cho README xung đột; xem và xử lý riêng các file code khác.
Hoàn tất bằng `git commit` nếu Git còn ở trạng thái merge.

Cài môi trường từ thư mục gốc:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

Khai báo thư viện mới trong cấu hình dự án và cập nhật lock theo `docs/security.md`.
Không yêu cầu người khác cài thủ công thư viện thiếu.
Linux/macOS dùng Python 3.12 và `.venv/bin/python` thay đường dẫn Windows.

## 5. File nên phát triển và lệnh kiểm tra của bạn

| Vị trí | Công việc |
| --- | --- |
| `configs/protocol.toml` | Ghi quyết định được nhóm duyệt, không tự đổi status để làm CI xanh |
| `src/recommender/contracts.py` | Kiểm tra fixture hiện có; mở rộng đúng schema thật |
| `src/recommender/splits/` | Thư mục đề xuất cho bộ sinh split thật, hiện chưa có |
| `src/recommender/baselines.py` | Baseline tham chiếu; mở rộng/tách module khi cần |
| `tests/test_splits.py` | Test thuật toán split bạn cần bổ sung, chưa có trong nền |
| `tests/test_contracts.py`, `tests/test_baselines.py` | Test nền để chạy trước/sau thay đổi |
| `configs/split.example.toml` | Mẫu tham số/đường dẫn và các quyết định cần chốt, chưa có runner dữ liệu thật |
| `docs/splits/` | Đã có manifest JSON mẫu, header bảng baseline và HANDOFF.md để làm bộ bàn giao |

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_contracts.py tests/test_baselines.py
.\.venv\Scripts\python.exe -m recommender.smoke --seeds 42 43 44 --output artifacts/split-baseline-fixture.json
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
node --test .github/tests/trusted-policy.test.cjs
```

Smoke dùng split giả lập đã có; nó không chứng minh thuật toán split mới của bạn đúng.
Chưa có lệnh chạy dataset thật; bạn phải bổ sung runner và hướng dẫn cùng code.
Test mới nên gồm item universe nhỏ, làm tròn, phiên ngắn sau lọc cold, seed tái lập,
session tràn split và thống kê baseline vô tình đọc test.

## 6. Bộ bàn giao cho Bảo Long

- [ ] Một bộ train/validation/test + cold IDs có data version, split ID và checksum.
- [ ] Config, nguồn dữ liệu và lệnh tạo lại; cách lấy đúng file không phụ thuộc máy bạn.
- [ ] Báo cáo kiểm tra rò rỉ và số mẫu warm/cold theo target.
- [ ] Candidate policy, K, tie-break và cách xử lý target không có trong candidate.
- [ ] Random/Popularity dùng chung metric, có kết quả từng seed và bản tổng hợp.
- [ ] Bảo Long xác nhận nạp đúng split, không chia lại và không thay luật riêng cho category.

Đề xuất chia PR: protocol/schema split -> split + test rò rỉ -> baseline -> runner/bảng kết quả.
Ưu tiên split/manifest trước khi chờ hoàn chỉnh mọi bảng để Bảo Long có nền làm tiếp.

## 7. Commit, PR và lỗi cần tránh

Trên trung-chien, nhận cập nhật bằng `git fetch origin`, `git merge origin/dev` sau khi đã lưu công việc.
Ví dụ PR cho baseline:

```powershell
git add src/recommender/baselines.py tests/test_baselines.py
git commit -m "feat(baselines): evaluate train-only popularity"
git push origin trung-chien
```

Mở PR **base: dev**, **compare: trung-chien**. Ghi thay đổi protocol, split ID,
bằng chứng chống rò rỉ và cách người nhận tái chạy; cần một người khác review.
README này là hướng dẫn riêng của bạn; khi review code vào dev, xử lý riêng README
để tài liệu của nhánh đích không bị thay bằng hướng dẫn cá nhân.

- Thiếu code/test: bản local cũ, cập nhật origin/trung-chien theo mục 4.
- Nhánh này đã có dependency-audit; nền dev còn chờ
  [PR gia cố #1](https://github.com/baolong06/recommender_system/pull/1).
  Không tắt required check hoặc review để ghép code.
- Kết quả khác nhau: kiểm tra dữ liệu, seed, thứ tự item/candidate và tie-break trước khi kết luận mô hình.
- Split bị phát hiện rò rỉ: sửa quy trình, ghi version mới và báo Bảo Long chạy lại.

Không push code thẳng main, không tự đánh dấu nghiên cứu xong. Số liệu trong PDF là minh họa;
số liệu bàn giao phải do code chạy thật. Nguồn phân công: tài liệu phối hợp P0 của nhóm.
