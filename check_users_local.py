import sqlite3
import os

# Kodun çalıştığı dizindeki data klasöründe veritabanı
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'erp_database.db')
print(f"Checking database at: {db_path}")

if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT KullaniciAdi, Email FROM Kullanici") # Updated table name
        rows = cursor.fetchall()
        print("Users found:")
        for r in rows:
            print(r)
        
        # Also print table names just to be sure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("\nAll Tables:", [t[0] for t in tables])
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Database file not found.")
