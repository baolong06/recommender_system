# Bảo Long — kết quả Cat-Popularity và đánh giá nhóm P0 v2

Ngày 13/11/2026 (Việt Nam). Mã thực nghiệm: `42de87384588accd53c7ff8f70781b9820f99045`.
Input là nguyên bộ split Trung Chiến tải lại từ GitHub Release, không chia lại hay đổi cohort cold.
Kết quả có 504 dòng: 144 dòng Random/Popularity full-primary, 72 dòng Cat theo hai chế độ,
và 288 dòng Random/Popularity trên các matched cohorts. Oracle có thông tin category target
đặc quyền; non-oracle chỉ dùng prefix. K=20/công thức được ghi trước khi chạy test.

## Công thức và ranh giới thông tin

Cat-Popularity xếp theo `(-I[category_i = selected], -train_event_count_i, item_id)`.
Non-oracle chọn category biết được xuất hiện nhiều nhất trong prefix, hòa chọn occurrence
gần nhất; không có category biết được thì fallback global Popularity. Oracle nhận category
target từ mapping được phép; không có category thì không hỗ trợ. Candidate W∪C giữ nguyên,
không thêm pseudo-count/vector cho item cold. Công thức được version trong configs/category_v2.toml.

Yoochoose mapping được tái dựng chỉ từ raw_context 1..12 trong final train, chưa biết category cold.
Diginetica mapping được đối chiếu với catalog raw đúng SHA-256; dùng giả định catalog tĩnh có sẵn
lúc inference. Lịch sử thời điểm công bố metadata chưa được xác minh. Prefix có thể chứa cold item
đã quan sát; non-oracle được dùng metadata của những item prefix đó nếu catalog cho phép.

## Kết quả test overall

Giá trị là tỷ lệ 0..1, mean ± sample std (ddof=1) qua ba split mean. Với Random, lấy mean
ba model seed trong từng split trước. **Các dòng partial dùng mẫu số khác full-primary; không
so trực tiếp chúng với baseline full-primary.** Xem bảng matched-cohort phía dưới.

| Dataset | Model | Cohort | HR@20 | MRR@20 | NDCG@20 | n chấm / n eligible theo seed |
| --- | --- | --- | ---: | ---: | ---: | --- |
| diginetica | Popularity | full-primary (full) | 0.00844388 ± 0.00092022 | 0.00207090 ± 0.00012290 | 0.00345390 ± 0.00028649 | 42: 54,399/54,399; 43: 54,397/54,397; 44: 54,399/54,399 |
| diginetica | Random | full-primary (full) | 0.00054536 ± 0.00005515 | 0.00009510 ± 0.00001827 | 0.00018994 ± 0.00002539 | 42: 54,399/54,399; 43: 54,397/54,397; 44: 54,399/54,399 |
| yoochoose | Popularity | full-primary (full) | 0.00644122 ± 0.00199224 | 0.00098569 ± 0.00014495 | 0.00211249 ± 0.00047528 | 42: 1,449/1,449; 43: 1,449/1,449; 44: 1,449/1,449 |
| yoochoose | Random | full-primary (full) | 0.00061345 ± 0.00035140 | 0.00015178 ± 0.00006888 | 0.00024974 ± 0.00001996 | 42: 1,449/1,449; 43: 1,449/1,449; 44: 1,449/1,449 |
| diginetica | CatPopularity-non-oracle | non-oracle-supported (full) | 0.27250227 ± 0.00561569 | 0.07062512 ± 0.00112762 | 0.11418193 ± 0.00210818 | 42: 54,399/54,399; 43: 54,397/54,397; 44: 54,399/54,399 |
| yoochoose | CatPopularity-non-oracle | non-oracle-supported (partial) | 0.04477686 ± 0.00453390 | 0.01157438 ± 0.00105210 | 0.01871866 ± 0.00106507 | 42: 1,138/1,449; 43: 1,142/1,449; 44: 1,221/1,449 |
| diginetica | CatPopularity-oracle | oracle-supported (full) | 0.36064836 ± 0.00580767 | 0.10166704 ± 0.00143525 | 0.15780219 ± 0.00240041 | 42: 54,399/54,399; 43: 54,397/54,397; 44: 54,399/54,399 |
| yoochoose | CatPopularity-oracle | oracle-supported (partial) | 0.06779712 ± 0.01067512 | 0.01522548 ± 0.00046236 | 0.02648474 ± 0.00201867 | 42: 1,032/1,449; 43: 1,049/1,449; 44: 1,129/1,449 |

## Cat-Popularity tách nhóm warm/cold

| Dataset | Model | Nhóm target | HR@20 | MRR@20 | NDCG@20 | n chấm / n eligible theo seed |
| --- | --- | --- | ---: | ---: | ---: | --- |
| diginetica | CatPopularity-non-oracle | cold | 0.02672506 ± 0.00226871 | 0.00367591 ± 0.00052910 | 0.00843960 ± 0.00088617 | 42: 11,215/11,215; 43: 10,357/10,357; 44: 10,951/10,951 |
| diginetica | CatPopularity-non-oracle | warm | 0.33365726 ± 0.00429960 | 0.08728849 ± 0.00090407 | 0.14049663 ± 0.00162833 | 42: 43,184/43,184; 43: 44,040/44,040; 44: 43,448/43,448 |
| yoochoose | CatPopularity-non-oracle | cold | N/A | N/A | N/A | 42: 0/311; 43: 0/307; 44: 0/228 |
| yoochoose | CatPopularity-non-oracle | warm | 0.04477686 ± 0.00453390 | 0.01157438 ± 0.00105210 | 0.01871866 ± 0.00106507 | 42: 1,138/1,138; 43: 1,142/1,142; 44: 1,221/1,221 |
| diginetica | CatPopularity-oracle | cold | 0.05284973 ± 0.00541659 | 0.00898467 ± 0.00119277 | 0.01818357 ± 0.00196809 | 42: 11,215/11,215; 43: 10,357/10,357; 44: 10,951/10,951 |
| diginetica | CatPopularity-oracle | warm | 0.43724699 ± 0.00303461 | 0.12473801 ± 0.00063614 | 0.19255176 ± 0.00117751 | 42: 43,184/43,184; 43: 44,040/44,040; 44: 43,448/43,448 |
| yoochoose | CatPopularity-oracle | cold | N/A | N/A | N/A | 42: 0/311; 43: 0/307; 44: 0/228 |
| yoochoose | CatPopularity-oracle | warm | 0.06779712 ± 0.01067512 | 0.01522548 ± 0.00046236 | 0.02648474 ± 0.00201867 | 42: 1,032/1,138; 43: 1,049/1,142; 44: 1,129/1,221 |

## Chênh lệch với Popularity trên cùng mẫu

Đây là Cat trừ Popularity được tính theo từng split trên **cùng các query được Cat hỗ trợ**.
Sau đó lấy mean/sample std qua ba split. Đơn vị vẫn là tỷ lệ, không phải phần trăm.
Bảng đầy đủ còn có so sánh Random và validation trong paired_differences.json.

| Dataset | Cat mode | Nhóm | ΔHR@20 | ΔMRR@20 | ΔNDCG@20 |
| --- | --- | --- | ---: | ---: | ---: |
| diginetica | CatPopularity-non-oracle | overall | 0.26405839 ± 0.00528527 | 0.06855422 ± 0.00106865 | 0.11072803 ± 0.00199902 |
| diginetica | CatPopularity-non-oracle | warm | 0.32310996 ± 0.00368897 | 0.08470172 ± 0.00076709 | 0.13618221 ± 0.00138500 |
| diginetica | CatPopularity-non-oracle | cold | 0.02672506 ± 0.00226871 | 0.00367591 ± 0.00052910 | 0.00843960 ± 0.00088617 |
| diginetica | CatPopularity-oracle | overall | 0.35220448 ± 0.00558977 | 0.09959613 ± 0.00141437 | 0.15434829 ± 0.00235127 |
| diginetica | CatPopularity-oracle | warm | 0.42669970 ± 0.00273370 | 0.12215124 ± 0.00053699 | 0.18823734 ± 0.00103124 |
| diginetica | CatPopularity-oracle | cold | 0.05284973 ± 0.00541659 | 0.00898467 ± 0.00119277 | 0.01818357 ± 0.00196809 |
| yoochoose | CatPopularity-non-oracle | overall | 0.03670609 ± 0.00640825 | 0.01034625 ± 0.00107759 | 0.01607767 ± 0.00174538 |
| yoochoose | CatPopularity-non-oracle | warm | 0.03670609 ± 0.00640825 | 0.01034625 ± 0.00107759 | 0.01607767 ± 0.00174538 |
| yoochoose | CatPopularity-non-oracle | cold | N/A | N/A | N/A |
| yoochoose | CatPopularity-oracle | overall | 0.05959029 ± 0.01221254 | 0.01391652 ± 0.00056414 | 0.02374135 ± 0.00260488 |
| yoochoose | CatPopularity-oracle | warm | 0.05959029 ± 0.01221254 | 0.01391652 ± 0.00056414 | 0.02374135 ± 0.00260488 |
| yoochoose | CatPopularity-oracle | cold | N/A | N/A | N/A |

## Coverage và fallback

Coverage chia hai tầng: target nằm trong W∪C (split coverage), sau đó khả năng metadata của
mô hình trên tập target đó (support_fraction). Hai tỷ lệ không thay thế accuracy.
Diginetica khoảng 76,3% target quan sát nằm trong primary candidates; cả hai Cat hỗ trợ
100% primary targets. Yoochoose có 1.452 target test quan sát, 1.449 primary targets mỗi seed.
Cat non-oracle chỉ báo phần warm; oracle còn loại warm target không có category biết được.

| Dataset | Seed | Nhóm | Non-oracle n/eligible | Oracle n/eligible | Non-oracle fallback |
| --- | ---: | --- | ---: | ---: | ---: |
| diginetica | 42 | overall | 54,399/54,399 | 54,399/54,399 | 1,672 |
| diginetica | 42 | warm | 43,184/43,184 | 43,184/43,184 | 1,333 |
| diginetica | 42 | cold | 11,215/11,215 | 11,215/11,215 | 339 |
| diginetica | 43 | overall | 54,397/54,397 | 54,397/54,397 | 1,672 |
| diginetica | 43 | warm | 44,040/44,040 | 44,040/44,040 | 1,325 |
| diginetica | 43 | cold | 10,357/10,357 | 10,357/10,357 | 347 |
| diginetica | 44 | overall | 54,399/54,399 | 54,399/54,399 | 1,673 |
| diginetica | 44 | warm | 43,448/43,448 | 43,448/43,448 | 1,334 |
| diginetica | 44 | cold | 10,951/10,951 | 10,951/10,951 | 339 |
| yoochoose | 42 | overall | 1,138/1,449 | 1,032/1,449 | 146 |
| yoochoose | 42 | warm | 1,138/1,138 | 1,032/1,138 | 146 |
| yoochoose | 42 | cold | 0/311 | 0/311 | 0 |
| yoochoose | 43 | overall | 1,142/1,449 | 1,049/1,449 | 113 |
| yoochoose | 43 | warm | 1,142/1,142 | 1,049/1,142 | 113 |
| yoochoose | 43 | cold | 0/307 | 0/307 | 0 |
| yoochoose | 44 | overall | 1,221/1,449 | 1,129/1,449 | 105 |
| yoochoose | 44 | warm | 1,221/1,221 | 1,129/1,221 | 105 |
| yoochoose | 44 | cold | 0/228 | 0/228 | 0 |

## Quan sát và giới hạn

- Trong cấu hình Diginetica này, Cat-Popularity có điểm cao hơn Popularity trên matched cohorts. Oracle biết category target nên có lợi thế thông tin; không mô tả nó là non-oracle deployable hay bảo đảm upper bound cho mọi metric.
- Cold item vẫn có count train bằng 0. Category chỉ giúp đưa chúng vào vùng ưu tiên; các warm item trong category vẫn đứng trước. Cold hits xảy ra khi có chỗ trong top20 của category, đồng hạng cold còn phụ thuộc ID chuỗi. Không kết luận category luôn giải quyết cold-start.
- Yoochoose Cat cold là N/A ở cả hai chế độ. Oracle warm có coverage chưa đầy đủ; không biến thiếu category thành score 0 hoặc lấy category từ heldout để lấp.
- Yoochoose test chỉ có 479 phiên. Không đổi cutoff/seed từ kết quả; không khẳng định khả năng khái quát hoặc tương đương benchmark bên ngoài.
- Diginetica dùng catalog không có lịch sử availability; cold là can thiệp từ train, không chứng minh thời điểm sản phẩm ra mắt.
- Exact duplicate tuples được giữ theo protocol dữ liệu. Không fit category bằng toàn corpus, không refit train+validation và không thay candidates theo model.
- Std qua ba split mean mô tả biến thiên; không phải confidence interval hay kiểm định ý nghĩa thống kê. Các phiên có nhiều prefix phụ thuộc nhau; không giả định mọi target độc lập.
- Đây là kết quả kỹ thuật theo công thức đã ghi, không phải khuyến nghị nên dùng mô hình nào. Nhóm vẫn cần review công thức/protocol, dữ liệu và nội dung báo cáo.

## Kiểm chứng và tái lập

- 122 test Python, 13 test workflow, Ruff và smoke đạt local. CI GitHub kiểm tra ở commit bàn giao sau khi push.
- Recomputed Random/Popularity full-primary: 144/144 dòng khớp chính xác snapshot Trung Chiến, cùng split ID và input manifest hash.
- Independent checker: 144 dòng Cat và matched Popularity khớp trong sai số 1e-12. Bộ kiểm dùng SQL count train, duyệt lại holdout gốc, analytical rank và metric sums riêng; không gọi predictor/metric chung.
- Mapping của cả sáu dataset/seed được tái dựng từ nguồn được phép và bằng mapping bàn giao; metadata_checks.json lưu bằng chứng.
- Test end-to-end chạy lặp tạo runs/summary/paired giống byte; thay target nhưng giữ prefix không đổi dự đoán non-oracle.

```powershell
python scripts/download_splits_v2.py
python scripts/download_raw.py --dataset diginetica --cache-dir artifacts/kagglehub
python scripts/run_category_v2.py --output-dir artifacts/reproduced-category-v2
python scripts/verify_category_results.py --input-root data/protocol_v2 --runs artifacts/reproduced-category-v2/runs.json --output artifacts/reproduced-category-check.json
```

Manifest ghi commit/source/config/input/lock hashes và môi trường. Các dòng runs có cohort,
n_eligible, n, support_fraction, status, unsupported reasons và fallback count. Báo cáo này
không thay thế review của người khác; research-readiness chưa được đánh dấu complete.
