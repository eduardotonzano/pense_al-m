from credit_assets.database.connection import connect, initialize_database

def test_schema_initialization(tmp_path):
    conn = connect(tmp_path / "test.db")
    initialize_database(conn)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"executions", "assets", "documents", "collection_attempts", "alerts"}.issubset(names)
