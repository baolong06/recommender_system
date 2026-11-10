# bao-long - Hướng dẫn làm việc của Bảo Long

**Đề tài 3: Đánh giá theo nhóm warm/cold và Cat-Popularity oracle/non-oracle.**

Bạn làm trên nhánh `bao-long`, gửi PR vào `dev`. Sản phẩm chính là công cụ group-wise dùng lại được
và bảng kết quả giải thích hiện tượng khi dùng category cho sản phẩm mới.
Phần gia cố CI đang có trên nhánh này phục vụ kiểm chứng; nó không thay nhiệm vụ nghiên cứu ĐT3.

## 1. Đầu vào bạn phải nhận và xác minh

| Thành phần | Nguồn | Kiểm tra trước khi chạy |
| --- | --- | --- |
| Dữ liệu sạch + catalog/category | Bá Chiến | Schema, data version/checksum, nguồn và ý nghĩa category |
| HR/MRR/NDCG | Bá Chiến | Giao diện, K, cách tổng hợp và test tính tay |
| Train/validation/test + cold IDs | Trung Chiến | Split ID/checksum, seed và báo cáo rò rỉ |
| Random/Popularity | Trung Chiến | Config, candidate policy, tie-break và kết quả tham chiếu |

Không chia lại split để thuận lợi cho mô hình category; mọi bảng so sánh phải cùng luật đánh giá.
Nếu chưa nhận đủ dữ liệu thật, bạn vẫn làm group-wise và code category trên mẫu nhỏ,
nhưng ghi rõ đó là kiểm thử, chưa phải kết quả nghiên cứu.

**Hiện trạng nhánh:** đã có metric, validator, Random/Popularity tham chiếu, group-wise và
runner fixture; gia cố CI đang ở [PR #1 vào dev](https://github.com/baolong06/recommender_system/pull/1).
Chưa có Cat-Popularity hoàn chỉnh hoặc runner thực nghiệm Yoochoose/Diginetica đầy đủ.

## 2. Việc 1 - Hoàn thiện group-wise trước

Mã nền nằm ở `src/recommender/evaluation.py`:

```python
evaluate_groups(examples, predictions, cold_items, k) -> dict
```

Yêu cầu bạn phải giữ hoặc mở rộng có test:

1. Mỗi ví dụ có một `target`; xác định nhóm bằng việc target có nằm trong cold IDs hay không.
   Không phân nhóm theo item cuối history hoặc việc history có cold item.
2. Mỗi ví dụ phải có đúng một ranking, không âm thầm cắt bớt bằng `zip` khi số lượng lệch.
3. Tính overall, warm, cold bằng metric chung; output có số mẫu `n` của từng nhóm.
4. Với toàn bộ ví dụ thuộc warm/cold, `n_warm + n_cold = n_overall`.
   Overall là trung bình theo mẫu, không phải trung bình đều của hai nhóm nếu kích thước lệch.
5. Nhóm không có mẫu: metric `null`/N/A; nhóm có mẫu nhưng không trúng: metric 0.
6. Ghi rõ quy tắc với mẫu không đánh giá được; báo coverage/lý do, không âm thầm loại để tăng điểm.

**Test riêng của bạn:** history chứa cold nhưng target warm; target cold nhưng history warm;
hai nhóm lệch số mẫu; nhóm rỗng; thiếu ranking; target ngoài top-K; K khác nhau.

**Bàn giao sớm:** cho Random/Popularity chạy qua group-wise để đối chiếu trước khi thêm category.
Đây cũng là công cụ ĐT4 dự phòng sẽ dùng lại, nên tránh gắn cứng với một baseline.

## 3. Việc 2 - Thiết kế rõ Cat-Popularity oracle và non-oracle

Trước khi viết kết quả, bạn phải ghi một bảng protocol cho từng chế độ:

| Cần ghi | Câu hỏi phải trả lời |
| --- | --- |
| Nguồn category | Có từ metadata nào, được biết từ thời điểm nào? |
| Tín hiệu chọn category | Lấy từ history hay thông tin của target? |
| Scoring | Đếm/chuẩn hóa thế nào, thống kê fit trên dữ liệu nào? |
| Candidate | Giống baseline sàn không, có item cold trong catalog không? |
| Tie-break/fallback | Điểm 0, category thiếu hoặc history không có category thì làm gì? |
| Phạm vi hỗ trợ | Trường hợp nào không hỗ trợ và ghi N/A ra sao? |

**Oracle:** nếu định nghĩa chế độ cho phép biết category của target, đánh dấu rõ thông tin đặc quyền
và chỉ dùng cho phân tích oracle. Chốt cách dùng này với nhóm; không trình bày như thông tin có thật lúc gợi ý.

**Non-oracle:** chỉ dùng history và metadata được protocol cho phép; không dùng target hoặc category
của target để lựa chọn category/ranking. Tách bước dự đoán khỏi bước chấm điểm để test được ranh giới này.

Không mặc định category sẽ cứu được item cold. Nếu scoring dùng độ phổ biến item từ train,
cold item có count 0; kết quả có thể phụ thuộc candidate/tie-break.
Ghi rõ thuật toán trước khi diễn giải, không bù vector category trung bình ngoài phạm vi P0.

**Test riêng của bạn:** đổi target nhưng giữ history thì non-oracle không đổi dự đoán;
thay validation/test không đổi thống kê fit; category thiếu; ranking không lặp;
điểm bằng nhau; nguồn category không hợp lệ. Test oracle/non-oracle phải tách tên rõ.

## 4. Việc 3 - Chạy so sánh và xuất bảng nghiên cứu

Sau khi nhận đủ dữ liệu/split đã duyệt:

1. Kiểm tra checksum, data version, split ID, protocol và phiên bản metric trước mỗi đợt chạy.
2. Chạy Random, Popularity, Cat-Popularity oracle, Cat-Popularity non-oracle trên cùng split,
   K và candidate policy. Nếu một mô hình không hỗ trợ một trường hợp, ghi N/A kèm lý do.
3. Chạy tối thiểu ba seed theo kế hoạch nhóm; phân biệt seed mô hình với seed split.
   Nếu dùng nhiều split seed, mọi baseline phải dùng cùng split ở seed tương ứng.
4. Lưu kết quả từng seed; tổng hợp mean ± sample std (`ddof=1`). Mô hình xác định có std=0 là hợp lệ.
5. Xuất overall/warm/cold, số mẫu và coverage cùng bảng so sánh; không chỉ xuất một điểm overall.
6. Viết mô tả hiện tượng: category thay đổi kết quả ở nhóm nào, điều kiện/giới hạn nào.
   P0 không yêu cầu khuyến nghị “nên dùng phương pháp X”.

**Mỗi dòng kết quả nên có:** dataset, data version, split ID/seed, model, chế độ oracle,
model seed, K, group, n, HR, MRR, NDCG và trạng thái/coverage nếu có.
Kèm config, commit, môi trường, checksum và lệnh tái chạy; không dùng JSON fixture làm bảng bài báo.

## 5. Setup trên nhánh bao-long

Cần Git, Python 3.12. Bộ test workflow dùng Node.js 24 hoặc mới hơn; nghiên cứu P0 không cần GPU.

```powershell
git clone https://github.com/baolong06/recommender_system.git
cd recommender_system
git switch bao-long
git fetch origin
git merge origin/dev
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
```

Nếu đã clone, bỏ bước clone/cd; trước merge hãy commit/cất công việc đang làm.
Nhánh này đang có input/lock hash nên dùng hai lệnh cài tách riêng như trên.
Nếu sau này thêm thư viện, cập nhật pyproject/input/lock theo `docs/security.md`, không cài thiếu truy nguyên.
Linux/macOS dùng `python3.12` và `.venv/bin/python` thay đường dẫn Windows.

Nếu README đang xung đột khi nhập dev vào bao-long, giữ hướng dẫn cá nhân:

```powershell
git restore --ours -- README.md
git add README.md
```

Chỉ làm khi README đang xung đột; xử lý các file code khác riêng rồi hoàn tất merge bằng `git commit` nếu cần.

## 6. Những file bạn cần dùng và phát triển

| Vị trí | Vai trò trong nhiệm vụ |
| --- | --- |
| `src/recommender/evaluation.py` | Group-wise và tổng hợp metric bạn phụ trách |
| `src/recommender/baselines.py` | Random/Popularity tham chiếu để kiểm tra ghép nối |
| `src/recommender/category.py` | Tên module đề xuất cho Cat-Popularity bạn còn phải tạo |
| `tests/test_groupwise.py` | Test group-wise đã có, cần mở rộng trường hợp biên |
| `tests/test_category.py` | Test oracle/non-oracle bạn còn phải bổ sung |
| `configs/protocol.toml` | Nguồn quy ước được nhóm duyệt; hiện còn quyết định mở |
| `docs/research-readiness.json` | Hồ sơ nghiên cứu trước đề nghị dev -> main; chưa đánh dấu complete |

Không có lệnh runner category/dataset thật sẵn để chạy ngay. Khi bổ sung runner,
ghi lệnh gọi thực tế, input/output và config trong cùng PR, tránh đưa lệnh giả vào hướng dẫn.

## 7. Lệnh kiểm tra của Bảo Long

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_groupwise.py tests/test_baselines.py tests/test_pipeline.py
.\.venv\Scripts\python.exe -m recommender.smoke --seeds 42 43 44 --output artifacts/bao-long-fixture.json
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
node --test .github/tests/trusted-policy.test.cjs
```

Các lệnh trên kiểm tra nền và fixture, chưa đánh giá Cat-Popularity thật.
Sau khi tạo `tests/test_category.py`, bổ sung test đó vào lệnh kiểm tra tập trung của bạn.

Nếu sửa dependencies hoặc cần audit:

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-audit.txt
.\.venv\Scripts\python.exe -m pip_audit --disable-pip --no-deps --require-hashes --strict -r requirements-audit.txt
```

CI có năm check: branch-policy, quality, unit-tests, pipeline-smoke, dependency-audit.
Workflow luật tin cậy và lịch Dependabot còn cần định nghĩa trên main để kích hoạt đầy đủ;
đọc `docs/security.md` trước khi sửa workflow. Không tự bypass review hoặc gọi đây là chứng nhận AppSec.

## 8. Bộ bàn giao và điều kiện kết thúc ĐT3

- [ ] Group-wise tái sử dụng được, đúng target, n và cách tổng hợp.
- [ ] Category baseline có mô tả thuật toán và ranh giới thông tin, test non-oracle chống đọc đáp án.
- [ ] Cả bốn baseline dùng cùng split/metric/candidate policy và có hồ sơ cấu hình.
- [ ] Bảng kết quả có từng seed, mean ± std, overall/warm/cold, n và coverage/N/A có lý do.
- [ ] Báo cáo mô tả kết quả thật, cả số thấp/bất ngờ, kèm giới hạn và lệnh tái tạo.
- [ ] Người khác review trước khi ghép vào dev; chưa coi công việc xong chỉ vì CI xanh.

Đề xuất chia PR: group-wise -> interface category và test chống leakage -> oracle/non-oracle -> runner và bảng kết quả.

## 9. Cách gửi công việc và xử lý vướng mắc

Nhận nền mới bằng `git fetch origin`, `git merge origin/dev` trên bao-long sau khi lưu công việc.
Ví dụ PR group-wise:

```powershell
git add src/recommender/evaluation.py tests/test_groupwise.py
git commit -m "feat(evaluation): validate target-based group metrics"
git push origin bao-long
```

Mở PR **base: dev**, **compare: bao-long**, hoặc tiếp tục push nếu PR cùng nhiệm vụ đang mở.
Ghi input/output, split ID, lệnh test, cách chống dùng đáp án và kết quả kiểm chứng.
README này dành riêng cho Bảo Long; reviewer phải xử lý riêng README khi ghép code để giữ
tài liệu nhánh đích phù hợp, không thay hướng dẫn dev/main bằng hướng dẫn cá nhân.

- Kết quả warm/cold sai: kiểm tra nhóm theo target và mẫu số, không đoán từ history.
- Non-oracle giống oracle bất thường: kiểm tra đường truyền target/category và bước fit.
- Cold tốt bất thường: kiểm tra leakage, candidate và tie-break trước khi kết luận.
- Thiếu split/metric: dùng fixture cho phần độc lập, không tự chia/viết bản riêng để chốt bảng nghiên cứu.
- PR thiếu review: cần một người khác có quyền ghi duyệt, không tắt bảo vệ để merge.

Chỉ khi cả ba đề tài xong và hồ sơ chung được review mới đề nghị `dev -> main`.
Nguồn phân công: tài liệu phối hợp P0 của nhóm; các số minh họa trong tài liệu không phải kết quả thật.
