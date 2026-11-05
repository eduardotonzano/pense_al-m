import sqlite3

from credit_assets.database.category_migrations import reclassify_financial_statements


def _db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE documents (document_pk INTEGER PRIMARY KEY, "
        "source_document_id TEXT, category TEXT, document_name TEXT)"
    )
    c.executemany(
        "INSERT INTO documents VALUES (?,?,?,?)",
        [
            (1, "a", "Informe Mensal", "Demonstrações Financeiras"),
            (2, "b", "Informe Mensal", "Informe Mensal de CRA"),
            (3, "c", "Outro", "Demonstracao Financeira"),
        ],
    )
    return c


def test_dry_run_does_not_change_anything():
    c = _db()
    result = reclassify_financial_statements(c)
    assert result["candidates"] == 1 and not result["applied"]
    assert c.execute("SELECT category FROM documents WHERE document_pk=1").fetchone()[0] == "Informe Mensal"


def test_apply_only_demotes_financial_statements():
    c = _db()
    result = reclassify_financial_statements(c, apply=True)
    assert result["applied"]
    cats = dict(c.execute("SELECT document_pk, category FROM documents").fetchall())
    assert cats == {1: "Outro", 2: "Informe Mensal", 3: "Outro"}
    assert reclassify_financial_statements(c, apply=True)["candidates"] == 0
