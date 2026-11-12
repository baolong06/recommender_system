# ba-chien - Hướng dẫn làm việc của Bá Chiến

**Đề tài 1: Chuẩn bị dữ liệu và bộ thước đo cho nghiên cứu P0.**

Bạn phát triển trên `bachien-dev`, gửi PR vào `ba-chien`, rồi `ba-chien` gửi PR vào `dev`. Hai sản phẩm quan trọng nhất của bạn là
**dữ liệu sạch có thể tái tạo** và **bộ metric HR/MRR/NDCG được kiểm chứng**.
Trung Chiến cần chúng để tạo split/baseline; Bảo Long cần chúng để chấm điểm mô hình category.

## 1. Phạm vi công việc của bạn

| Bạn chịu trách nhiệm | Sản phẩm cần có |
| --- | --- |
| Đọc Yoochoose và Diginetica | Bộ đọc riêng cho định dạng gốc của mỗi dataset, đưa về schema chung |
| Kiểm tra và làm sạch dữ liệu | Code lọc, cấu hình, thống kê trước/sau và log lý do loại |
| Thống kê dữ liệu | Bảng số lượng, độ dài phiên và biểu đồ tần suất/long-tail |
| Metric dùng chung | HR@K, MRR@K, NDCG@K cho dự đoán next-item, có test tính tay |
| Bàn giao nền dữ liệu | Manifest, checksum, vị trí dữ liệu và lệnh tái chạy |

Bạn không phải xây dựng Cat-Popularity hay tự chia lại split để chạy kết quả của riêng mình.
Nếu cần thay đổi schema/metric, thống nhất với hai người dùng lại trước khi ghép vào dev.

**Hiện trạng nhánh:** đã có khung Python, metric, baseline tham chiếu, validator, fixture,
CI và dependency lock để setup/chạy kiểm tra ngay. Nhánh có thêm `configs/data.example.toml`,
schema, manifest và checklist bàn giao trong `docs/data/`, cùng mẫu event tổng hợp.
Bộ đọc/lọc dataset thật và các báo cáo dữ liệu là phần bạn còn phải phát triển;
không coi fixture hoặc manifest mẫu là nghiên cứu đã hoàn tất.

## 2. Thứ tự triển khai và yêu cầu cụ thể

### Bước A - Chốt schema và bộ đọc

1. Xem cấu trúc file gốc của từng dataset, ghi tên cột, kiểu dữ liệu, đơn vị thời gian,
   cách biểu diễn item/category và trường nào có thể thiếu.
2. Chuẩn hóa các trường tối thiểu: `session_id`, `item_id`, `timestamp`, `category_id`.
   Giữ ID dạng chuỗi để không mất số 0 đầu; giữ ý nghĩa category gốc.
3. Ghi rõ cách ánh xạ schema gốc sang schema chung và nguồn lấy metadata.
   Không tự đặt tên chữ cho category ID như các ví dụ minh họa trong tài liệu P0.
4. Thống nhất cách xử lý timestamp bằng nhau, giá trị thiếu, dữ liệu lặp và item nhiều category.
   Không tự xóa mọi click lặp vì chúng có thể là hành vi hợp lệ.
5. Tạo dữ liệu rất nhỏ để kiểm thử bộ đọc; không tải toàn bộ dataset trong unit test.

**Đầu ra bước A:** code bộ đọc, tài liệu schema và mẫu đã chuẩn hóa mà Trung Chiến đọc được.

### Bước B - Làm sạch có truy nguyên

- Xử lý phiên ngắn dưới 2 item và item xuất hiện dưới 5 lần theo phạm vi tài liệu P0.
- Ghi rõ cách đếm: số event hay số item khác nhau; thứ tự các phép lọc; có lọc lặp hay không;
  nếu có thì điều kiện dừng là gì. Các quy ước này phải được nhóm duyệt.
- Phối hợp với Trung Chiến để chốt thứ tự làm sạch và chia dữ liệu.
  Không tính thống kê có dùng tương lai rồi tuyên bố toàn bộ quy trình không rò rỉ.
- Lưu số event/session/item trước và sau mỗi bước; ghi tỷ lệ thiếu category và xử lý tương ứng.
- Cùng input, cấu hình và quy tắc sắp thứ tự phải tạo lại cùng dữ liệu sạch.

**Đầu ra bước B:** bộ dữ liệu sạch, config xử lý và bảng kiểm tra trước/sau.
Dataset lớn lưu ở nơi nhóm thống nhất, không commit vào Git.

### Bước C - Hoàn thiện metric trước khi chạy bảng kết quả

Sau khi nhận nền dev, mã tham chiếu nằm ở `src/recommender/metrics.py`:

```python
ranking_metrics(predictions: list[str], target: str, k: int) -> dict[str, float]
```

- `predictions` đã được xếp hạng, không trùng item; `target` là một next-item đúng;
  K là số nguyên dương. Nếu thay hợp đồng này, cập nhật test và báo cả nhóm.
- HR@K = 1 nếu target nằm trong top-K, ngược lại 0.
- MRR@K = 1/rank khi trúng; NDCG@K = 1/log2(rank+1) cho trường hợp một target đúng.
- Ví dụ target ở hạng 3, K >= 3: HR = 1, MRR = 1/3, NDCG = 0.5.
- Test target ở đầu/cuối top-K, ngoài top-K, không xuất hiện, ranking rỗng,
  K không hợp lệ và ranking có item trùng. Phân biệt điểm từng mẫu và trung bình nhiều mẫu.
- Không dùng số minh họa trong PDF làm ngưỡng để CI phải đạt.

**Đầu ra bước C:** module metric được test và giao diện mà hai người còn lại gọi trực tiếp;
không để họ sao chép thành hai bản metric khác nhau.

### Bước D - Thống kê và manifest

Với mỗi dataset, bàn giao tối thiểu:

- Số event/session/item/category; số giá trị thiếu và số bị loại theo từng lý do.
- Thống kê độ dài phiên: min, median, mean, max và phân phối.
- Phân phối tần suất item/long-tail; script tạo biểu đồ từ dữ liệu đã ghi phiên bản.
- Manifest ghi nguồn, phiên bản dữ liệu, config xử lý, số lượng, checksum và commit code.
- Lệnh tái tạo chạy từ thư mục gốc; đường dẫn input/output là tham số, không hard-code ổ đĩa máy mình.

## 3. Setup trên đúng nhánh bachien-dev

Cần Git và Python 3.12; Node.js 24 hoặc mới hơn để chạy test workflow. Không cần GPU. Lần đầu:

```powershell
git clone https://github.com/baolong06/recommender_system.git
cd recommender_system
git switch bachien-dev
git fetch origin
```

Nếu máy đã có repo, bỏ bước clone; sau `git status` và khi đã lưu công việc, chạy
`git pull --ff-only origin bachien-dev` trên đúng nhánh để nhận bộ khung mới.
Khung code đã có sẵn, không cần merge dev để setup lần đầu. Khi muốn nhận phần chung mới:

```powershell
git fetch origin
git merge origin/dev
```

Nếu **README.md** xung đột với bản chung từ dev, giữ hướng dẫn riêng của Bá Chiến bằng:

```powershell
git restore --ours -- README.md
git add README.md
```

Chỉ dùng hai lệnh trên khi README đang xung đột trong lần nhập dev vào ba-chien.
Xử lý riêng các file khác, rồi `git commit` nếu Git đang chờ hoàn tất merge.
Không dùng cách này để ghi đè hàng loạt code từ dev.

Cài môi trường từ thư mục gốc:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

`pandas` và `pyarrow` đã được khai báo và khóa phiên bản. Nếu thêm dependency khác,
khai báo trong `pyproject.toml` và cập nhật input/lock theo `docs/security.md`;
không chỉ cài riêng trên máy. Linux/macOS dùng `python3.12` và `.venv/bin/python`.

## 4. Bạn nên sửa file nào và kiểm tra gì?

| Vị trí | Cách dùng trong nhiệm vụ |
| --- | --- |
| `src/recommender/metrics.py` | Bộ metric dùng chung; ưu tiên hoàn thiện trước |
| `src/recommender/contracts.py` | Tham khảo validator fixture; mở rộng schema phải giữ kiểm tra chống rò rỉ |
| `src/recommender/data/` | Thư mục đề xuất để bạn bổ sung bộ đọc/lọc thật, hiện chưa có trong nền |
| `tests/test_metrics.py` | Test metric tính tay đã có sau khi nhận dev |
| `tests/test_data.py` | File đề xuất để bạn bổ sung test bộ đọc/lọc; chưa phải test đã có |
| `configs/data.example.toml` | Mẫu thông số/đường dẫn; còn quyết định cần nhóm duyệt, chưa có runner dữ liệu thật |
| `docs/data/` | Đã có schema, manifest JSON mẫu và HANDOFF.md để điền khi thực hiện |
| `tests/fixtures/raw_events.example.csv` | Mẫu tổng hợp nhỏ cho bộ đọc/lọc bạn sẽ phát triển |

Các thư mục/file đề xuất cần được tạo cùng code, không có sẵn lệnh xử lý dataset thật để chạy ngay.
Kiểm tra nền trước, rồi bổ sung test của phần mình:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_metrics.py tests/test_contracts.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m recommender.smoke --seeds 42 43 44 --output artifacts/ba-chien-smoke.json
node --test .github/tests/trusted-policy.test.cjs
```

Test bộ đọc/lọc mới phải có dữ liệu biên: phiên bị loại, item hiếm, timestamp sai,
category thiếu và lọc lặp làm thay đổi kết quả. Không viết test chỉ kiểm tra file tồn tại.

## 5. Bàn giao cho Trung Chiến và Bảo Long

| Bàn giao | Yêu cầu nghiệm thu |
| --- | --- |
| Dữ liệu sạch | Đọc được bằng schema đã duyệt, có phiên bản và checksum |
| Metric | Test tính tay đạt, có ví dụ gọi hàm và ý nghĩa output |
| Bảng thống kê/biểu đồ | Do code chạy ra, có lệnh tạo lại |
| Manifest/config | Chỉ đúng dữ liệu, nguồn và quy trình; không cần hỏi riêng đường dẫn máy bạn |

- [ ] Người nhận đọc được mẫu và toàn bộ dữ liệu đúng phiên bản.
- [ ] Số lượng trước/sau khớp log; không bỏ qua dữ liệu lỗi mà không báo.
- [ ] Code metric chỉ có một bản dùng chung; thay đổi được ghi rõ trong PR.
- [ ] CI đạt và một người khác review trước khi merge vào dev.

Đề xuất chia PR: schema/bộ đọc nhỏ -> metric -> làm sạch -> thống kê và manifest.
Ưu tiên PR metric và schema để hai bạn còn lại không bị chờ toàn bộ dữ liệu.

## 6. Commit và PR của Bá Chiến

```powershell
git status
git add src/recommender/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): validate next-item ranking metrics"
git push origin bachien-dev
```

Stage đúng file của thay đổi; ví dụ trên dành cho PR metric, không phải lệnh stage mọi nhiệm vụ.
Mở PR **base: ba-chien**, **compare: bachien-dev**; điền input/output, lệnh test và người dùng lại bị ảnh hưởng.
Mỗi ngày nhập `origin/dev` trên nhánh này để nhận code chung. Push tiếp lên `bachien-dev` khi PR cần sửa. Sau khi review và merge vào `ba-chien`, mở PR `ba-chien → dev`.

README này chỉ dành cho Bá Chiến. Khi review PR code vào dev, phải xem riêng thay đổi README,
giữ tài liệu nhánh đích phù hợp; không dùng README cá nhân làm hướng dẫn của dev/main.

## 7. Lỗi thường gặp và các giới hạn cần nhớ

- **Không có pyproject/test:** bản local cũ; cập nhật origin/ba-chien theo mục 3 trước khi cài.
- **Metric sai dù chương trình chạy:** kiểm tra rank bắt đầu từ 1, cutoff K và công thức log2.
- **Thống kê thay đổi mỗi lần chạy:** kiểm tra dữ liệu nguồn, thứ tự sort và cấu hình xử lý.
- **CI chờ review:** nhánh này đã có dependency-audit; nền dev vẫn còn chờ
  [PR gia cố #1](https://github.com/baolong06/recommender_system/pull/1).
  Không tắt yêu cầu CI/review để ghép code.
- **Dữ liệu quá lớn:** để ngoài Git, chỉ commit manifest/schema/fixture nhỏ và code.

Không đổi tỷ lệ cold 20%, không dùng test để chọn quy tắc có lợi, không biến ví dụ thành kết quả.
Không tự đánh dấu nghiên cứu hoàn tất hoặc đưa code thẳng lên main.
Nguồn nhiệm vụ: tài liệu P0 của nhóm; đây là hướng dẫn triển khai, không phải xác nhận các việc đã xong.


## Luồng nhánh và pipeline đã sửa

Xem [quy trình nhánh](docs/plans/2026-11-12-work-branches.md). PR công việc không đi thẳng
vào `dev` hoặc `main`. Test dữ liệu bắt buộc có pandas/pyarrow, gồm xuất Parquet/manifest.
Timestamp giây vẫn được giữ để tương thích; `timestamp_ms` dùng để sort và loại click trùng.
Xem `docs/data/schema.md` trước khi dùng dữ liệu. Các manifest cũ cần chạy lại trên dữ liệu gốc
sau thay đổi độ chính xác timestamp; không dùng số lượng/checksum cũ làm kết quả của code mới.
