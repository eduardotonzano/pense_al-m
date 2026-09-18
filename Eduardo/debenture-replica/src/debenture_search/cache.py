import json, sqlite3, time

class SQLiteTTLCache:
    def __init__(self, path="debenture_cache.sqlite3"):
        self.db = sqlite3.connect(path)
        self.db.execute("create table if not exists cache (key text primary key, value text not null, expires real not null)")
    def get(self, key):
        row = self.db.execute("select value, expires from cache where key=?", (key,)).fetchone()
        if not row: return None
        if row[1] < time.time():
            self.db.execute("delete from cache where key=?", (key,)); self.db.commit(); return None
        return json.loads(row[0])
    def set(self, key, value, ttl=3600):
        self.db.execute("insert or replace into cache values (?, ?, ?)", (key, json.dumps(value), time.time()+ttl)); self.db.commit()
