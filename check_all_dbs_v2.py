import sqlite3
import os

paths = [
    "f:/cursor/endercelik/data/erp_database.db",
    "C:/Users/ersin/AppData/Roaming/ErpYonetim/data/erp_database.db",
    "f:/cursor/endercelik/instance/erp_dev.db"
]

for p in paths:
    if os.path.exists(p):
        print(f"--- Checking {p} ---")
        try:
            conn = sqlite3.connect(p)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(Belgeler)")
            cols = [row[1] for row in cursor.fetchall()]
            print(f"Columns in Belgeler: {cols}")
            
            cursor.execute("PRAGMA table_info(StokHareketleri)")
            cols_stok = [row[1] for row in cursor.fetchall()]
            print(f"Columns in StokHareketleri: {cols_stok}")
            
            conn.close()
        except Exception as e:
            print(f"Error checking {p}: {e}")
    else:
        print(f"File {p} does not exist.")
