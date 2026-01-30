import sqlite3
import os

p = "f:/cursor/endercelik/data/erp_database.db"
if os.path.exists(p):
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("SELECT BelgeID, DosyaAdi, DosyaYolu, Kategori FROM Belgeler")
    rows = cursor.fetchall()
    print("Documents in database:")
    for r in rows:
        print(r)
    conn.close()
