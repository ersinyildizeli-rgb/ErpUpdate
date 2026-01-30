import sqlite3
import os

paths = [
    "f:/cursor/endercelik/data/erp_database.db",
    os.path.join(os.getenv('APPDATA'), 'ErpYonetim', 'data', 'erp_database.db')
]

for p in paths:
    if p and os.path.exists(p):
        print(f"FILE: {p}")
        conn = sqlite3.connect(p)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(Belgeler)")
        belge_cols = [row[1] for row in cursor.fetchall()]
        print(f"  Belgeler columns: {belge_cols}")
        
        cursor.execute("PRAGMA table_info(StokHareketleri)")
        stok_cols = [row[1] for row in cursor.fetchall()]
        print(f"  StokHareketleri columns: {stok_cols}")
        
        conn.close()
    else:
        print(f"MISSING: {p}")
