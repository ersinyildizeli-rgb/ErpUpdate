import sqlite3
import os
from pathlib import Path

def migrate_db(db_path):
    print(f"Checking {db_path}...")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Check if Carpan exists
            cursor.execute("PRAGMA table_info(Puantaj)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'Carpan' not in columns:
                cursor.execute("ALTER TABLE Puantaj ADD COLUMN Carpan FLOAT DEFAULT 1.5;")
                print(f"  Successfully added Carpan to {db_path}")
            else:
                print(f"  Carpan already exists in {db_path}")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"  Error migrating {db_path}: {e}")
    else:
        print(f"  {db_path} does not exist.")

project_root = Path(r'f:\cursor\endercelik')
db_files = list(project_root.glob('**/*.db'))

for db_file in db_files:
    migrate_db(str(db_file))

# Also check common locations
appdata_db = Path(os.getenv('APPDATA')) / 'ErpYonetim' / 'data' / 'erp_database.db'
migrate_db(str(appdata_db))
migrate_db(str(project_root / 'data' / 'erp_database.db'))
migrate_db(str(project_root / 'instance' / 'erp_dev.db'))
