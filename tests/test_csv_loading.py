"""
tests/test_csv_loading.py
 
Unit tests for the CSV loader (app/db.py). Covers the "empty file or
missing columns" item from the Phase 6 checklist: load_csv_to_db() should
raise a clean CSVLoadError in these cases, never crash with an unhandled
exception. Uses pytest's tmp_path fixture to write throwaway CSV/DB files
per test, so nothing touches the real data/ folder.
"""
 
import pandas as pd
import pytest
 
from app.db import SCHEMA, CSVLoadError, load_csv_to_db
 
 
def _valid_row():
    """One row with every column SCHEMA expects, keyed by source CSV name."""
    values_by_final_name = {
        "item_id": "P1",
        "title": "Test Product",
        "price": 100.0,
        "previous_price": 120.0,
        "discount_pct": "10% OFF",
        "free_shipping": True,
        "official_store": False,
        "in_stock": True,
        "seller_name": "Test Seller",
        "units_sold": 5,
        "rating": 4.5,
        "reviews_count": 10,
        "installments_text": "3x $33.33",
        "shipping_text": "Free shipping",
        "product_link": "http://example.com/p1",
        "image_url": "http://example.com/p1.jpg",
    }
    return {info["source"]: values_by_final_name[final_name] for final_name, info in SCHEMA.items()}
 
 
def test_loads_valid_csv(tmp_path):
    csv_path = tmp_path / "valid.csv"
    pd.DataFrame([_valid_row()]).to_csv(csv_path, index=False)
 
    rows_loaded = load_csv_to_db(csv_path=str(csv_path), db_path=str(tmp_path / "test.db"))
 
    assert rows_loaded == 1
 
 
def test_raises_on_missing_file(tmp_path):
    missing_path = tmp_path / "does_not_exist.csv"
 
    with pytest.raises(CSVLoadError):
        load_csv_to_db(csv_path=str(missing_path), db_path=str(tmp_path / "test.db"))
 
 
def test_raises_on_empty_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")  # 0 bytes, no header at all
 
    with pytest.raises(CSVLoadError):
        load_csv_to_db(csv_path=str(csv_path), db_path=str(tmp_path / "test.db"))
 
 
def test_raises_on_header_only_csv(tmp_path):
    csv_path = tmp_path / "header_only.csv"
    header = ",".join(info["source"] for info in SCHEMA.values())
    csv_path.write_text(header + "\n")  # valid header, zero data rows
 
    with pytest.raises(CSVLoadError):
        load_csv_to_db(csv_path=str(csv_path), db_path=str(tmp_path / "test.db"))
 
 
def test_raises_on_missing_column(tmp_path):
    csv_path = tmp_path / "missing_column.csv"
    row = _valid_row()
    del row["articuloTitulo"]  # drop one column the schema expects
    pd.DataFrame([row]).to_csv(csv_path, index=False)
 
    with pytest.raises(CSVLoadError):
        load_csv_to_db(csv_path=str(csv_path), db_path=str(tmp_path / "test.db"))