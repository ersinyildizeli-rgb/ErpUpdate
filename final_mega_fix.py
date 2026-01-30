import sqlite3, os
def migrate(p):
    if not os.path.exists(p): return
    print(f"Migrating {p}")
    c = sqlite3.connect(p)
    cur = c.cursor()
    def add(tbl, col, typ):
        try:
            cur.execute(f"PRAGMA table_info({tbl})")
            if col not in [r[1] for r in cur.fetchall()]:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
                print(f"  Added {col} to {tbl}")
        except: pass
    
    add("Belgeler", "Kategori", "VARCHAR(50)")
    add("Belgeler", "DosyaBoyutu", "INTEGER")
    add("Belgeler", "RelationType", "VARCHAR(50)")
    add("Belgeler", "RelationID", "INTEGER")
    add("StokHareketleri", "SeriNo", "VARCHAR(100)")
    add("StokHareketleri", "CariID", "INTEGER")
    add("StokHareketleri", "FaturaID", "INTEGER")
    add("IslemLoglari", "IslemTuru", "VARCHAR(50)")
    add("IslemLoglari", "Detay", "VARCHAR(500)")
    add("IslemLoglari", "IpAdresi", "VARCHAR(50)")
    add("Finans", "KategoriID", "INTEGER")
    for t in ["FaturaKalemleri", "TeklifKalemleri", "SiparisKalemleri"]:
        add(t, "SeriNo", "VARCHAR(100)")
    c.commit(); c.close()

db1 = "f:/cursor/endercelik/data/erp_database.db"
db2 = os.path.expandvars("%APPDATA%/ErpYonetim/data/erp_database.db")
migrate(db1); migrate(db2)
