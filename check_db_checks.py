
import sqlite3
import os
from pathlib import Path

# Try to find the DB
possible_paths = [
    Path('f:/cursor/endercelik/data/erp_database.db'),
    Path(os.getenv('APPDATA')) / 'ErpYonetim' / 'data' / 'erp_database.db'
]

db_path = None
for p in possible_paths:
    if p.exists():
        db_path = p
        break

if not db_path:
    print("Database not found!")
else:
    print(f"Checking database at: {db_path}")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Search for any checks
        cursor.execute("SELECT FinansID, Kategori, Aciklama, IslemTuru FROM Finans WHERE Kategori LIKE '%çek%' OR Kategori LIKE '%Çek%' OR Kategori LIKE '%CEK%' OR Kategori LIKE '%cek%' OR Aciklama LIKE '%çek%' OR Aciklama LIKE '%Çek%'")
        rows = cursor.fetchall()
        print(f"Found {len(rows)} check records in Finans table:")
        for row in rows:
            print(row)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
