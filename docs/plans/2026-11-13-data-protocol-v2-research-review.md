# Phương án dữ liệu P0 v2 — kết luận nghiên cứu và phản biện

Ngày: 13/11/2026 (Việt Nam). Trạng thái: các tác nhân đã thống nhất phương án kỹ thuật;
chưa phải biên bản phê duyệt của Bá Chiến, Trung Chiến, Bảo Long hoặc giảng viên.
Đây là quyết định thiết kế cho phiên bản tiếp theo, chưa phải cấu hình đã được triển khai.

## 1. Quyết định chính

Dùng luồng **dữ liệu chuẩn hóa trung tính → chia thời gian → lọc chỉ trên train → can thiệp cold 20% → đánh giá**.
Giữ các bản dữ liệu đã xuất để đối chiếu; không ghi đè, không gọi chúng là sai hoặc vô dụng.
Bản vừa chạy thành công là kết quả kỹ thuật của pipeline hiện tại, có global support filtering
và majority-category toàn corpus; nó chưa đáp ứng đầy đủ protocol v2 này.

Ba hướng nghiên cứu: (1) làm sạch và repeated clicks; (2) temporal split và leakage;
(3) category/catalog và oracle. Các tác nhân đã gửi phản biện chéo. Bất đồng chính là tận dụng
cohort đã lọc toàn bộ hay tạo neutral archive. Chọn neutral + train-only làm phương án chính
để không để tần suất tương lai quyết định item nào đủ điều kiện huấn luyện. Dữ liệu cũ vẫn là
snapshot exploratory có mô tả rõ cách chọn quần thể.

## 2. Bằng chứng và giới hạn suy luận

- **SR-GNN, AAAI 2019** [S1,S2]: phiên tối thiểu hai sự kiện, item tối thiểu năm lượt sự kiện.
  Mã tác giả dùng độ dài danh sách click và đếm từng occurrence, không đếm distinct item.
  Mã gốc lọc toàn corpus trước split, không lặp đến fixed point và có bước bỏ unseen test;
  do đó không sao chép nguyên pipeline đó cho bài toán cold-start. P0 v2 không phải tái tạo
  y nguyên benchmark SR-GNN.
- **Ji et al., TOIS** [S3] và **Time to Split, RecSys 2025** [S4]: thời gian huấn luyện/đánh giá
  chồng lặp có thể tạo thông tin tương lai; cách chọn target và validation phải được định nghĩa
  cùng temporal split. Áp dụng nguyên tắc này vào support/category là suy luận thiết kế của P0,
  không phải hai paper đã kiểm thử đúng code trong repository này.
- **RepeatNet, AAAI 2019** [S5]: tiêu thụ lại cùng item là hành vi cần xem xét. Điều này hỗ trợ
  giữ click lặp và cho phép gợi ý lại item đã xem; không chứng minh hai dòng trùng mili giây
  nhất thiết là hai click thật.
- **README nhà cung cấp Yoochoose được bảo tồn ở mirror** [S6]: cột thứ tư là ngữ cảnh click,
  có nhiều nghĩa. Mirror không phải repository chính thức của nhà cung cấp.

## 3. Quy tắc làm sạch được chọn

| Hạng mục | Quyết định P0 v2 |
| --- | --- |
| Nguồn | Cố định Kaggle version 1 của hai dataset; lưu SHA-256, version, code commit và môi trường |
| Neutral archive | Giữ mọi event có session/item hợp lệ và thời gian hợp lệ; chưa lọc support hoặc suy ra category từ toàn log |
| Thời gian | UTC milliseconds; giữ timestamp giây để tương thích; thêm raw_row_index để phá hòa ổn định |
| Dòng lỗi | Bỏ ID rỗng, ngày/offset không hợp lệ, timestamp trước epoch; thống kê từng lý do |
| Click lặp | Không bỏ consecutive repeat và không buộc hai item trong phiên phải khác nhau |
| Tuple trùng | Giữ và flag cùng (session,item,timestamp_ms) khi không có event_id để xác nhận lỗi; không tự xóa |
| Phiên | Ngưỡng ít nhất 2 sự kiện, không phải 2 item phân biệt |
| Item support | Ngưỡng ít nhất 5 lượt sự kiện, học từ train; không phải ít nhất 5 phiên |
| Fixed point | Lọc support và phiên trên train đến ổn định; quá giới hạn thì báo lỗi, không xuất như đã thành công |
| Category thiếu | UNK; không xóa event chỉ vì không có category |
| Version | Mọi thay đổi quy tắc tạo output/manifest mới; không sửa số lượng của snapshot cũ |

Không gọi cấu hình session≥2/item≥5 là “5-core” hai phía: nó không áp dụng ngưỡng 5 cho cả
hai loại đỉnh. Tên chính xác là session-min2/item-support5.
Giữ+flag exact tuple là lựa chọn bảo toàn thông tin của P0; nếu sau này có bằng chứng lỗi logging,
quy tắc dedup cần được quyết định lại và tạo phiên bản mới.

## 4. Chia dữ liệu và cold holdout — thứ tự hữu hạn

Cửa sổ sau là lựa chọn P0, không phải chuẩn duy nhất được paper bắt buộc. Chốt trước khi xem metric.
Đặt d là đầu ngày UTC chứa thời điểm lớn nhất của log trung tính.

| Dataset | Validation | Test | Train |
| --- | --- | --- | --- |
| Yoochoose | [d−1 ngày,d) | [d,d+1 ngày) | Trước validation |
| Diginetica | [d−13 ngày,d−6 ngày) | [d−6 ngày,d+1 ngày) | Trước validation |

Chỉ nhận phiên có toàn bộ event nằm trong một cửa sổ; bỏ và đếm riêng phiên băng qua cutoff.
Kiểm tra session không giao nhau và max(train time)<min(validation time)<min(test time).
Tạo next-item examples bằng prefix trước target; không đưa suffix tương lai vào input.
Không random-split từng click hoặc chia các prefix cùng phiên sang các tập khác nhau.

Thứ tự can thiệp:

1. Trên train trước can thiệp, lọc session-min2/item-support5 đến ổn định. Khi loại item khỏi
   chuỗi, cắt thành các đoạn hợp lệ thay vì nối hai phía qua event đã loại. Các đoạn phải có ID
   riêng nhưng giữ parent_session_id/raw_row_index. Ghi rõ lựa chọn segment này trong code mới.
2. Tập item sau bước đó là U0. Với mỗi seed 42,43,44, chọn không hoàn lại ceil(0,20×|U0|) item.
   Để tái lập độc lập thư viện RNG, sort U0 theo ID và sắp theo SHA-256 của chuỗi UTF-8
   dataset_name + ':' + seed_decimal + ':' + item_id; hòa hash thì ID. Lấy số lượng đầu tiên làm C.
   Đây là lựa chọn triển khai của P0; không xem target validation/test để chọn C.
3. Xóa mọi tương tác C khỏi train. Cắt ở vị trí bị xóa thành đoạn warm liên tiếp; bỏ đoạn <2.
4. Không re-core support sau can thiệp. Ngưỡng support5 thuộc bước trước holdout; support warm
   sau can thiệp có thể nhỏ hơn 5 và phải được báo cáo. Giới hạn này tránh một chuỗi can thiệp
   thay đổi quần thể và tỷ lệ C khó kiểm soát.
5. W là các item còn xuất hiện trong final train. I0 là item thuộc U0 nhưng không thuộc C và
   không còn xuất hiện sau segmentation; không gọi I0 là warm.
6. Candidate primary A=W∪C. Giữ nguyên C qua các model. “20%” có mẫu số U0 trước holdout,
   không hứa C chiếm đúng 20% candidate cuối sau attrition.
7. Target I0 hoặc ngoài A không nằm trong primary metric; luôn báo số lượng, tỷ lệ coverage
   và lý do loại. Không giấu natural-unseen trong nhóm controlled-cold. Prefix giữ chuỗi gốc;
   item ngoài mapping phải dùng UNK/biểu diễn OOV được công bố, không âm thầm xóa rồi nối lại.
8. Giữ target thuộc C trong đánh giá. Nếu một seed không có cold target: n_cold=0, metric N/A;
   không tìm seed khác qua test. Giữ item đã xem trong candidates để hỗ trợ repeat consumption.

C là cold do can thiệp trên lịch sử huấn luyện; không tuyên bố đây là thời điểm sản phẩm mới
thực sự ra mắt thị trường. Mọi model dùng chung split, candidates, C và thứ tự phá hòa cho mỗi seed.
Không gộp train+validation để refit trong báo cáo chính này; validation dành cho chọn cấu hình,
model và thống kê giữ nguyên trước test.

## 5. Category — cần thay đổi cách hiểu hiện tại

Audit đọc toàn bộ raw, không sửa dữ liệu. Số liệu chi tiết và hashes ở category_audit_20261113.json.

| Ngữ cảnh click Yoochoose | Số event |
| --- | ---: |
| 0 — thiếu | 16.337.653 |
| S — khuyến mãi | 10.769.610 |
| Mã 1..12 — category thực | 5.820.377 |
| Brand/khác | 76.304 |
| Tổng | 33.003.944 |

Chỉ khoảng 17,6% event mang context là category thực. Có 52.739 item; 42.471 item có ít nhất
một category thực, 2.978 có nhiều category thực và 48 hòa modal category. Đây là thống kê chẩn
đoán toàn dữ liệu, tuyệt đối không dùng làm lookup fit cho primary experiment.

**Yoochoose:** lưu raw_context riêng. Chỉ dùng mã 1..12 trong final train để suy ra category item;
hòa chọn số nhỏ hơn theo số nguyên, không theo thứ tự chuỗi; không có bằng chứng thì UNK.
0/S/brand không được dùng như taxonomy category. Không suy ra mapping của item C từ interaction
đã giấu hoặc validation/test. Khi chưa có catalog độc lập cho cold item, Cat-Popularity cold
primary trên Yoochoose ghi N/A, không ghi 0 và không giả lập category. Random/Popularity và
đánh giá warm vẫn có thể chạy.

**Diginetica:** product-categories.csv có 184.047 dòng tương ứng 184.047 item, 1.217 category;
không thiếu/trùng/xung đột item mapping trong version đã audit. Dùng làm core dataset cho
category cold-start với giả định metadata catalog được biết trước dự đoán. Catalog thiếu thời
gian công bố nên không tuyên bố đã xác minh availability lịch sử. Loader mới phải báo lỗi khi
có item mapping xung đột thay vì im lặng giữ dòng đầu.

**Oracle/non-oracle:** oracle chỉ được nhận category target từ catalog được phép, không target ID,
và phải báo là điều kiện có thông tin nhãn/upper bound. Non-oracle chỉ dùng prefix đã quan sát,
metadata được phép và thống kê học trên final train. Cả hai dùng cùng candidate set A.
Công thức chấm Cat-Popularity cần được đặc tả riêng trước khi benchmark; văn bản này không
ngụ ý công thức mô hình đã triển khai hay đã chạy thành công.

## 6. Ảnh hưởng đến thành phẩm hiện tại và việc cần làm tiếp

Bản chạy trên code commit 9229e6a đã qua kiểm tra schema/checksum/counts: Diginetica 989.204
và Yoochoose 31.707.554 events. Các số này vẫn đúng cho pipeline đã thực thi. Tuy nhiên kiểm tra
kỹ thuật không xác nhận tính phù hợp của mọi lựa chọn nghiên cứu. Giữ artifact đó để đối chiếu,
không relabel thành dữ liệu theo protocol v2.

Cần tạo neutral archive từ raw, sửa mapper category, triển khai train-only split/filter/cold và
bổ sung kiểm tra rò rỉ. Không thể khôi phục raw_context và các event đã loại bằng cách chỉ đổi
tên cột trong Parquet cũ. Chưa chạy lại v2 trong nhiệm vụ nghiên cứu này.

Tiêu chí nghiệm thu v2: raw SHA khớp; không thiếu precision; raw_row_index tái lập được; số dòng
lỗi/trùng flag rõ; session/time disjoint; support chỉ học train; C∩train-items=∅; I0/coverage được
báo; category mapper không đọc heldout; mọi model dùng cùng manifests. Report overall/warm/
controlled-cold, số mẫu và N/A khi không có mẫu. HR/MRR/NDCG@20 là cutoff chính đề xuất cho P0,
không chọn K sau khi xem test. Không thử tỷ lệ cold khác 20%.

Chỉ sau khi nhóm xác nhận và code v2 được thực thi/kiểm tra mới cập nhật trạng thái protocol
hoạt động. Tài liệu này không tự đổi configs/protocol.toml thành approved hay research complete.

## 7. Nguồn

- [S1 — SR-GNN, paper AAAI 2019](https://arxiv.org/html/1811.00855v4)
- [S2 — SR-GNN, preprocessing của tác giả](https://github.com/CRIPAC-DIG/SR-GNN/blob/master/datasets/preprocess.py)
- [S3 — Ji et al., A Critical Study on Data Leakage in Recommender System Offline Evaluation](https://arxiv.org/abs/2010.11060)
- [S4 — Gusak et al., Time to Split, RecSys 2025](https://arxiv.org/abs/2507.16289)
- [S5 — RepeatNet, AAAI 2019](https://arxiv.org/abs/1812.02646)
- [S6 — README nhà cung cấp Yoochoose, bản mirror bảo tồn](https://github.com/jeremander/Yoochoose/blob/master/yoochoose/data/dataset-README.txt)
- Tài liệu phân công P0 của nhóm: PhoiHop_3DeTai_BaChien_TrungChien_BaoLong_P0.pdf;
  giữ tỷ lệ controlled cold 20%, seeds 42/43/44 và phân công dữ liệu/metric/split/category.
