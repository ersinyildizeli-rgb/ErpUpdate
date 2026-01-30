import sqlite3
import os

def check_other_db():
    db_path = "f:/cursor/endercelik/instance/erp_dev.db"
    if not os.path.exists(db_path):
        print("Not found")
        return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT SUM(Tutar) FROM Finans WHERE IslemTuru='Gelir'")
    res = cur.fetchone()
    print(f"er_dev.db Income Sum: {res[0]}")
    conn.close()

if __name__ == "__main__":
    check_other_db()
