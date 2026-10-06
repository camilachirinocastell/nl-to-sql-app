"""
tests/test_sql_validation.py

Unit tests for the SQL validator (app/text_to_sql.py). This is the
independent security layer that never trusts the model's output — see
section 5.1 of the build doc for the full threat model. These tests run
against the validator directly, with no model and no database involved.
"""

import pytest

from app.db import TABLE_NAME
from app.text_to_sql import SQLValidationError, validate_sql

VALID_SQL = f"SELECT title, price FROM {TABLE_NAME} LIMIT 10"


def test_valid_select_passes():
    result = validate_sql(VALID_SQL)
    assert result.upper().startswith("SELECT")


@pytest.mark.parametrize(
    "forbidden_sql",
    [
        f"DROP TABLE {TABLE_NAME}",
        f"DELETE FROM {TABLE_NAME}",
        f"UPDATE {TABLE_NAME} SET price = 0",
        f"INSERT INTO {TABLE_NAME} (title) VALUES ('x')",
        f"ATTACH DATABASE 'evil.db' AS evil",
        "PRAGMA table_info(products)",
    ],
)
def test_rejects_forbidden_keywords(forbidden_sql):
    with pytest.raises(SQLValidationError):
        validate_sql(forbidden_sql)


def test_rejects_multiple_statements():
    malicious_sql = f"SELECT * FROM {TABLE_NAME}; DROP TABLE {TABLE_NAME};"
    with pytest.raises(SQLValidationError):
        validate_sql(malicious_sql)


def test_rejects_unknown_table():
    with pytest.raises(SQLValidationError):
        validate_sql("SELECT * FROM some_other_table")


def test_adds_limit_when_missing():
    sql_without_limit = f"SELECT title FROM {TABLE_NAME}"
    result = validate_sql(sql_without_limit)
    assert "LIMIT" in result.upper()