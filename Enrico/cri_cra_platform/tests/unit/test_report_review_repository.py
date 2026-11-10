import sqlite3

from credit_assets.repositories.report_review_repository import recompute_current


def _db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE extracted_reports (report_id INTEGER PRIMARY KEY, asset_id INT, "
        "reference_date TEXT, source_version TEXT, human_review_status TEXT, is_current INT DEFAULT 0)"
    )
    c.executemany("INSERT INTO extracted_reports VALUES (?,?,?,?,?,0)", [
        (1, 1, "2024-01-31", "1", "rejected"),
        (2, 1, "2024-01-31", "2", "approved"),
        (3, 1, "2024-02-29", "1", "approved"),
        (4, 1, "2024-03-31", "2", "pending"),
        (5, 1, "2024-03-31", "1", "approved"),
        (6, 2, "2024-01-31", "1", "approved"),
    ])
    return c


def test_current_is_highest_approved_version_per_asset_and_month():
    c = _db()
    assert recompute_current(c) == 4
    current = [r[0] for r in c.execute("SELECT report_id FROM extracted_reports WHERE is_current = 1 ORDER BY 1")]
    # Mar/2024: a v2 pendente não substitui a v1 aprovada.
    assert current == [2, 3, 5, 6]
