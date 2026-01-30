import sqlite3
import os
from pathlib import Path

def migrate_db(db_path):
    if not os.path.exists(db_path):
        print(f"Skipping {db_path} (not found)")
        return
    
    print(f"Migrating {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    def add_column(table, column, type_def):
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            if column not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}")
                print(f"  Added {column} to {table}")
        except Exception as e:
            print(f"  Error adding {column} to {table}: {e}")

    # StokHareketleri
    add_column("StokHareketleri", "SeriNo", "VARCHAR(100)")
    add_column("StokHareketleri", "CariID", "INTEGER")
    add_column("StokHareketleri", "FaturaID", "INTEGER")
    
    # Belgeler
    add_column("Belgeler", "RelationType", "VARCHAR(50)")
    add_column("Belgeler", "RelationID", "INTEGER")
    add_column("Belgeler", "Kategori", "VARCHAR(50)")
    
    # IslemLoglari
    add_column("IslemLoglari", "IslemTuru", "VARCHAR(50) DEFAULT 'İşlem'")
    add_column("IslemLoglari", "Detay", "VARCHAR(500)")
    add_column("IslemLoglari", "IpAdresi", "VARCHAR(50)")
    
    # Kalemler
    for table in ['FaturaKalemleri', 'TeklifKalemleri', 'SiparisKalemleri']:
        add_column(table, "SeriNo", "VARCHAR(100)")
    
    # Finans
    add_column("Finans", "KategoriID", "INTEGER")
    
    conn.commit()
    conn.close()
    print(f"Finished migrating {db_path}")

# Local DB
migrate_db("data/erp_database.db")

# AppData DB
appdata = os.getenv('APPDATA')
if appdata:
    appdata_db = os.path.join(appdata, 'ErpYonetim', 'data', 'erp_database.db')
    migrate_db(appdata_db)
