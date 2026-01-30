import sqlite3
import os

p = "f:/cursor/endercelik/data/erp_database.db"
if os.path.exists(p):
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Belgeler)")
    for row in cursor.fetchall():
        print(f"Col: {row[1]}")
    conn.close()
p2 = os.path.join(os.getenv('APPDATA'), 'ErpYonetim', 'data', 'erp_database.db')
if os.path.exists(p2):
    print(f"--- {p2} ---")
    conn = sqlite3.connect(p2)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Belgeler)")
    for row in cursor.fetchall():
        print(f"Col: {row[1]}")
    conn.close()
