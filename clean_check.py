import sqlite3, os
def p_cols(p, t):
    if not os.path.exists(p): return
    c = sqlite3.connect(p)
    res = c.execute(f"PRAGMA table_info({t})").fetchall()
    print(f"DB:{p} TABLE:{t}")
    for r in res: print(f"  {r[1]}")
    c.close()

db1 = "f:/cursor/endercelik/data/erp_database.db"
db2 = os.path.expandvars("%APPDATA%/ErpYonetim/data/erp_database.db")

for d in [db1, db2]:
    for t in ["Belgeler", "IslemLoglari", "StokHareketleri", "Finans"]:
        p_cols(d, t)
