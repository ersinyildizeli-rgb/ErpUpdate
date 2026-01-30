import sqlite3
import os

p = os.path.join(os.getenv('APPDATA'), 'ErpYonetim', 'data', 'erp_database.db')
if os.path.exists(p):
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("SELECT KullaniciAdi, Rol FROM Kullanici")
    rows = cursor.fetchall()
    print("Users:")
    for r in rows:
        print(r)
    conn.close()
