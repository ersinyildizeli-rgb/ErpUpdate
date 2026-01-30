
import sqlite3
import os
from pathlib import Path

# Try to find the DB
possible_paths = [
    Path('f:/cursor/endercelik/data/erp_database.db'),
    Path('f:/cursor/endercelik/instance/erp_dev.db'),
    Path(os.getenv('APPDATA')) / 'ErpYonetim' / 'data' / 'erp_database.db'
]

for p in possible_paths:
    if p.exists():
        print(f"Checking database at: {p}")
        try:
            conn = sqlite3.connect(str(p))
            cursor = conn.cursor()
            cursor.execute("SELECT FinansID, Kategori, Aciklama, IslemTuru, Tutar FROM Finans WHERE Kategori LIKE '%çek%' OR Kategori LIKE '%Çek%' OR Aciklama LIKE '%çek%' OR Aciklama LIKE '%Çek%'")
            rows = cursor.fetchall()
            print(f"Found {len(rows)} check records:")
            for row in rows:
                print(row)
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
        print("-" * 20)
