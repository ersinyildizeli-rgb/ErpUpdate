import sqlite3
import os

def check_table(p, table):
    if os.path.exists(p):
        print(f"--- {table} in {p} ---")
        conn = sqlite3.connect(p)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        for row in cursor.fetchall():
            print(f"Col: {row[1]}")
        conn.close()

paths = [
    "f:/cursor/endercelik/data/erp_database.db",
    os.path.join(os.getenv('APPDATA'), 'ErpYonetim', 'data', 'erp_database.db')
]

for p in paths:
    check_table(p, "Belgeler")
    check_table(p, "IslemLoglari")
    check_table(p, "StokHareketleri")
    check_table(p, "Finans")
