import sqlite3
import os

def migrate():
    db_path = 'data/erp_database.db'
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def add_column_if_not_exists(table, column, type):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type}")
            print(f"Added {column} to {table}")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e).lower():
                print(f"{column} already exists in {table}")
            else:
                print(f"Error adding {column} to {table}: {e}")

    # StokHareketleri columns
    add_column_if_not_exists("StokHareketleri", "SeriNo", "VARCHAR(100)")
    
    # Belgeler (Document) table columns
    add_column_if_not_exists("Belgeler", "RelationType", "VARCHAR(50)")
    add_column_if_not_exists("Belgeler", "RelationID", "INTEGER")
    
    # IslemLoglari (ActionLog) table columns
    add_column_if_not_exists("IslemLoglari", "IslemTuru", "VARCHAR(50)")
    add_column_if_not_exists("IslemLoglari", "Detay", "VARCHAR(500)")
    add_column_if_not_exists("IslemLoglari", "IpAdresi", "VARCHAR(50)")

    # Finans table columns
    add_column_if_not_exists("Finans", "KategoriID", "INTEGER")

    # Ensure missing tables are created correctly
    tables_to_create = {
        "Teklifler": """
            CREATE TABLE Teklifler (
                TeklifID INTEGER PRIMARY KEY AUTOINCREMENT,
                TeklifNo VARCHAR(50) NOT NULL,
                TeklifTuru VARCHAR(20) NOT NULL,
                CariID INTEGER NOT NULL,
                Tarih DATETIME DEFAULT CURRENT_TIMESTAMP,
                GecerlilikTarihi DATETIME,
                Durum VARCHAR(30) DEFAULT 'Beklemede',
                AraToplam FLOAT DEFAULT 0.0,
                KDVToplam FLOAT DEFAULT 0.0,
                GenelToplam FLOAT DEFAULT 0.0,
                Aciklama VARCHAR(500),
                FOREIGN KEY (CariID) REFERENCES CariHesaplar (CariID)
            )
        """,
        "TeklifKalemleri": """
            CREATE TABLE TeklifKalemleri (
                KalemID INTEGER PRIMARY KEY AUTOINCREMENT,
                TeklifID INTEGER NOT NULL,
                UrunID INTEGER NOT NULL,
                Miktar FLOAT NOT NULL,
                BirimFiyat FLOAT NOT NULL,
                KDVOran INTEGER DEFAULT 20,
                SatirToplami FLOAT NOT NULL,
                SeriNo VARCHAR(100),
                FOREIGN KEY (TeklifID) REFERENCES Teklifler (TeklifID),
                FOREIGN KEY (UrunID) REFERENCES Urunler (UrunID)
            )
        """,
        "Siparisler": """
            CREATE TABLE Siparisler (
                SiparisID INTEGER PRIMARY KEY AUTOINCREMENT,
                SiparisNo VARCHAR(50) NOT NULL,
                SiparisTuru VARCHAR(20) NOT NULL,
                CariID INTEGER NOT NULL,
                Tarih DATETIME DEFAULT CURRENT_TIMESTAMP,
                TeslimTarihi DATETIME,
                Durum VARCHAR(30) DEFAULT 'Beklemede',
                AraToplam FLOAT DEFAULT 0.0,
                KDVToplam FLOAT DEFAULT 0.0,
                GenelToplam FLOAT DEFAULT 0.0,
                Aciklama VARCHAR(500),
                FOREIGN KEY (CariID) REFERENCES CariHesaplar (CariID)
            )
        """,
        "SiparisKalemleri": """
            CREATE TABLE SiparisKalemleri (
                KalemID INTEGER PRIMARY KEY AUTOINCREMENT,
                SiparisID INTEGER NOT NULL,
                UrunID INTEGER NOT NULL,
                Miktar FLOAT NOT NULL,
                BirimFiyat FLOAT NOT NULL,
                KDVOran INTEGER DEFAULT 20,
                SatirToplami FLOAT NOT NULL,
                SeriNo VARCHAR(100),
                FOREIGN KEY (SiparisID) REFERENCES Siparisler (SiparisID),
                FOREIGN KEY (UrunID) REFERENCES Urunler (UrunID)
            )
        """,
        "Receteler": """
            CREATE TABLE Receteler (
                ReceteID INTEGER PRIMARY KEY AUTOINCREMENT,
                MamulID INTEGER NOT NULL,
                ReceteAdi VARCHAR(200) NOT NULL,
                VarsayilanMiktar FLOAT DEFAULT 1.0,
                Aciklama VARCHAR(500),
                FOREIGN KEY (MamulID) REFERENCES Urunler (UrunID)
            )
        """,
        "ReceteKalemleri": """
            CREATE TABLE ReceteKalemleri (
                KalemID INTEGER PRIMARY KEY AUTOINCREMENT,
                ReceteID INTEGER NOT NULL,
                HammaddeID INTEGER NOT NULL,
                Miktar FLOAT NOT NULL,
                FOREIGN KEY (ReceteID) REFERENCES Receteler (ReceteID),
                FOREIGN KEY (HammaddeID) REFERENCES Urunler (UrunID)
            )
        """,
        "UretimEmirleri": """
            CREATE TABLE UretimEmirleri (
                EmirID INTEGER PRIMARY KEY AUTOINCREMENT,
                ReceteID INTEGER NOT NULL,
                Miktar FLOAT NOT NULL,
                Tarih DATETIME DEFAULT CURRENT_TIMESTAMP,
                Durum VARCHAR(30) DEFAULT 'Planlandı',
                Aciklama VARCHAR(500),
                FOREIGN KEY (ReceteID) REFERENCES Receteler (ReceteID)
            )
        """
    }

    for table, ddl in tables_to_create.items():
        try:
            cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
            print(f"Table {table} already exists")
        except sqlite3.OperationalError:
            print(f"Creating table {table}...")
            cursor.execute(ddl)
            print(f"Created table {table}")

    conn.commit()
    conn.close()
    print("Full migration completed successfully.")

if __name__ == "__main__":
    migrate()
