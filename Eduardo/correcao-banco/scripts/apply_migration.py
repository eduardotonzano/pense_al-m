from pathlib import Path
import sqlite3
ROOT=Path(__file__).resolve().parent.parent
DB=ROOT/'data'/'debenture.db'
SQL=ROOT/'migrations'/'001_initial_schema.sql'
DB.parent.mkdir(parents=True,exist_ok=True)
con=sqlite3.connect(DB)
try:
 con.execute('PRAGMA foreign_keys=ON')
 con.execute('PRAGMA synchronous=FULL')
 journal=con.execute('PRAGMA journal_mode=WAL').fetchone()[0]
 con.executescript(SQL.read_text(encoding='utf-8'))
 con.commit()
 integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
 foreign_keys=con.execute('PRAGMA foreign_key_check').fetchall()
 tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
 assert integrity=='ok',integrity
 assert not foreign_keys,foreign_keys
 print('Migration aplicada com sucesso.')
 print('Journal mode:',journal)
 print('Integrity check:',integrity)
 print('Foreign key errors:',foreign_keys)
 print('Tabelas:',tables)
finally:
 con.close()
