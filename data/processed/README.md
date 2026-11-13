# Dữ liệu đã xử lý — bản đóng gói legacy v1

[Tải trên GitHub Releases](https://github.com/baolong06/recommender_system/releases/tag/processed-legacy-v1-2026-11-12).
Tag: `processed-legacy-v1-2026-11-12`, đóng gói từ các Parquet đã có ngày 11/11/2026.
Nhánh `ba-chien` lưu manifest, checksum, hướng dẫn và script; Release lưu các file dữ liệu.

| Bộ dữ liệu | Event | Session | Item |
| --- | ---: | ---: | ---: |
| `yoochoose_clean` | 31,594,390 | 7,954,835 | 37,263 |
| `diginetica_clean` | 988,884 | 204,043 | 42,163 |
| `yoochoose_clean_nrows1000000` | 960,813 | 233,958 | 11,705 |

Mẫu `nrows1000000` được tạo bằng cách đọc một triệu dòng raw đầu tiên rồi làm sạch;
960,813 là số event còn lại. Đây là bộ để thử nhanh, có dữ liệu trùng với bản đầy đủ.
Đọc riêng từng bộ; không ghép mẫu vào bản đầy đủ hoặc dùng hai bộ làm train/test độc lập.

## Phiên bản và schema thực tế

Release này giữ nguyên dữ liệu đã có, với `review_status=legacy-seconds-requires-rerun`.
Chỉ thay cách nén/chia file; chưa chạy lại bước cleaning từ raw bằng pipeline mới.

| Cột | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `session_id` | string | ID phiên gốc |
| `item_id` | string | ID item gốc |
| `timestamp` | int64 | Unix seconds UTC |
| `category` | string | Mã category từ pipeline cũ |

Các file này không có `timestamp_ms` và dùng tên `category`, trong khi schema hiện tại của
pipeline là `category_id` và có thêm `timestamp_ms`. Pipeline cũ đã loại trùng theo giây;
đổi tên cột hoặc nhân timestamp với 1000 không khôi phục các click đã mất độ chính xác.
Khi cần dữ liệu theo [schema mới](../../docs/data/schema.md), phải chạy lại cleaning từ raw.
Release này không xác nhận dữ liệu đã được duyệt cho nghiên cứu, không chứa split train/val/test,
và không chứng minh quy trình không rò rỉ. Metadata nguồn có `git_commit=unknown`; không suy diễn
commit đóng gói thành commit tạo dữ liệu.

## Tải về `data/processed`

Sau khi clone và chuyển sang nhánh `ba-chien`, dùng Python 3.12 trở lên:

```powershell
python scripts/download_processed.py
```

Script tải cả ba bộ từ Release, kiểm tra dung lượng và SHA-256 trước khi đổi tên file tạm.
File đã có đúng checksum được bỏ qua; file sai checksum sẽ báo lỗi để bạn xử lý.
Có thể tải một bộ hoặc đổi nơi lưu:

```powershell
python scripts/download_processed.py --dataset yoochoose_clean
python scripts/download_processed.py --dataset diginetica_clean --output-dir data/processed
```

Cấu trúc sau khi tải:

```text
data/processed/
  README.md
  manifest.json
  source-manifest.json
  SHA256SUMS
  yoochoose_clean/part-000.parquet
  diginetica_clean/part-000.parquet
  yoochoose_clean_nrows1000000/part-000.parquet
```

Đọc từng bộ bằng pandas (cài môi trường theo README ở root):

```python
import pandas as pd

events = pd.read_parquet("data/processed/yoochoose_clean", engine="pyarrow")
print(len(events))  # 31594390
```

Nếu cần thứ tự dòng chính xác của nguồn, đọc theo danh sách parts trong manifest:

```python
import json
from pathlib import Path
import pyarrow.parquet as pq

root = Path("data/processed")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
dataset = manifest["datasets"]["yoochoose_clean"]
for part in dataset["parts"]:
    for batch in pq.ParquetFile(root / part["local_path"]).iter_batches(batch_size=65536):
        # Xử lý batch ở đây; không cần giữ toàn bộ dataset trong RAM.
        print(batch.num_rows)
```

Không cần ghép thành một file lớn. Cả bộ được nén Parquet/Zstandard level 6;
ngưỡng chia phần là 256 MiB, có thể vượt nhẹ để giữ trọn một batch/phiên.
Bản hiện tại nén vừa một phần cho mỗi bộ. `session_id` được kiểm tra thứ tự từ điển,
mọi event của cùng một session nằm trong cùng một phần.

## Manifest và kiểm chứng

- `manifest.json`: URL tải từng phần, số byte, SHA-256 mới, số event/session/item,
  schema thực tế, ranh giới phiên và provenance của nguồn.
- `source-manifest.json`: manifest gốc giữ nguyên, gồm checksum Parquet trước khi nén lại,
  checksum raw và config `min_session_len=2`, `min_item_support=5`, `max_iter=10`.
- `SHA256SUMS`: checksum của các asset, manifest nguồn và manifest phát hành.
  Tên Parquet ở đây là tên asset trên Release; script đổi về `part-000.parquet` trong từng thư mục.

Khi đóng gói, script kiểm tra checksum nguồn, đếm lại event/session/item, kiểm tra session
liên tục theo thứ tự, rồi đọc lại **toàn bộ** Parquet đầu ra để so sánh từng giá trị,
thứ tự dòng và schema/metadata với nguồn. Checksum file mới khác checksum file cũ vì codec
và bố cục Parquet thay đổi; nội dung dữ liệu được đối chiếu tương đương hoàn toàn.

Để đóng gói lại từ các file Parquet nguồn cùng manifest gốc, dùng một thư mục đầu ra mới:

```powershell
python scripts/package_processed.py --input-dir path/to/original/data/processed --output-dir artifacts/processed-release --tag processed-legacy-v1-2026-11-12 --target-mib 256
```

Script này nhận định dạng manifest nguồn legacy, không nhận manifest phát hành làm input.
Nén lại với phiên bản PyArrow khác có thể tạo checksum khác; bản phát hành này dùng PyArrow 26.0.1.
Không ghi đè asset của cùng tag khi nội dung thay đổi; phát hành tag mới và cập nhật manifest.
