from pathlib import Path

import pandas as pd
import pytest

from recommender.data.neutral import normalize_dataset


def test_neutral_preserves_repeats_precision_context_and_row_identity(tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    (source / "yoochoose-clicks.dat").write_text(
        "01,2014-04-07T10:51:09.900Z,009,S\n"
        "01,2014-04-07T10:51:09.100Z,009,0\n"
        "01,2014-04-07T10:51:09.100Z,009,0\n"
        ",2014-04-07T10:51:09.100Z,009,1\n"
        "01,broken,009,1\n01,1960-01-01T00:00:00Z,009,1\n"
    )
    out = tmp_path / "neutral.parquet"
    audit = normalize_dataset("yoochoose", source, out, batch_size=2)
    data = pd.read_parquet(out)
    assert audit["raw_rows"] == 6
    assert audit["valid_rows"] == 3
    assert audit["dropped_rows"] == 3
    assert data.session_id.tolist() == ["01"] * 3
    assert data.item_id.tolist() == ["009"] * 3
    assert data.raw_context.tolist() == ["S", "0", "0"]
    assert data.category_id.tolist() == ["UNK"] * 3
    assert data.raw_row_index.tolist() == [0, 1, 2]
    assert data.timestamp_ms.tolist() == [1396867869900, 1396867869100, 1396867869100]
    assert len(audit["raw_files"][0]["sha256"]) == 64
    with pytest.raises(FileExistsError):
        normalize_dataset("yoochoose", source, out)


def diginetica_fixture(source: Path, categories="itemId;categoryId\n01;2\n01;2\n"):
    source.mkdir()
    (source / "product-categories.csv").write_text(categories)
    (source / "train-item-views.csv").write_text(
        "sessionId;userId;itemId;timeframe;eventdate\n"
        "1;NA;01;100;2016-05-09\n1;NA;02;900;2016-05-09\n"
        "1;NA;03;bad;2016-05-09\n1;NA;04;-1;2016-05-09\n"
        "1;NA;05;1.5;2016-05-09\n1;NA;06;9223372036854775808;2016-05-09\n"
    )


def test_diginetica_offset_validation_and_static_metadata(tmp_path):
    source = tmp_path / "raw"
    diginetica_fixture(source)
    out = tmp_path / "out.parquet"
    audit = normalize_dataset("diginetica", source, out, batch_size=2)
    data = pd.read_parquet(out)
    assert audit["valid_rows"] == 2
    assert audit["dropped_reasons"]["invalid_timeframe"] == 4
    assert audit["identical_catalog_duplicates_collapsed"] == 1
    assert data.category_id.tolist() == ["2", "UNK"]
    assert data.timestamp_ms.iloc[1] - data.timestamp_ms.iloc[0] == 800


def test_conflicting_catalog_fails_before_output(tmp_path):
    source = tmp_path / "raw"
    diginetica_fixture(source, "itemId;categoryId\n01;2\n01;3\n")
    out = tmp_path / "out.parquet"
    with pytest.raises(ValueError, match="conflicting"):
        normalize_dataset("diginetica", source, out)
    assert not out.exists()


@pytest.mark.parametrize("row", ["1,2014-04-07T10:51:09.100Z,9,1,EXTRA\n"])
def test_malformed_csv_never_silently_shifts_columns(tmp_path, row):
    (tmp_path / "yoochoose-clicks.dat").write_text(row)
    with pytest.raises(ValueError, match="Malformed"):
        normalize_dataset("yoochoose", tmp_path, tmp_path / "out.parquet")
    assert not (tmp_path / "out.parquet").exists()


def test_empty_category_is_preserved_as_raw_context_not_event_rejection(tmp_path):
    (tmp_path / "yoochoose-clicks.dat").write_text("1,2014-04-07T10:51:09.100Z,9,\n")
    out = tmp_path / "out.parquet"
    assert normalize_dataset("yoochoose", tmp_path, out)["valid_rows"] == 1
    assert pd.read_parquet(out).raw_context.tolist() == [""]


def test_overflowing_offset_rejected_without_float_rounding(tmp_path):
    source = tmp_path / "raw"
    diginetica_fixture(source)
    (source / "train-item-views.csv").write_text(
        "sessionId;itemId;timeframe;eventdate\n"
        "1;01;9223372036854775807;2016-05-09\n"
        "1;01;bad;2016-05-09\n"
        "1;01;0000100;2016-05-09\n"
    )
    out = tmp_path / "out.parquet"
    audit = normalize_dataset("diginetica", source, out)
    assert audit["valid_rows"] == 1
    assert audit["dropped_reasons"]["invalid_timeframe"] == 2
    assert pd.read_parquet(out).timestamp_ms.iloc[0] % 1000 == 100


@pytest.mark.parametrize("content", ["wrong;columns\nA;B\n", "itemId;categoryId\n01;\n"])
def test_catalog_requires_complete_mapping_schema(tmp_path, content):
    source = tmp_path / "raw"
    diginetica_fixture(source, content)
    with pytest.raises(ValueError):
        normalize_dataset("diginetica", source, tmp_path / "out.parquet")
