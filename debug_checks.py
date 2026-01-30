import sqlite3
import os

# Define the database path
db_path = os.path.join(os.getenv('APPDATA'), 'ErpYonetim', 'data', 'erp_database.db')
print(f"Connecting to: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    # Count Finans
    cursor.execute("SELECT COUNT(*) FROM Finans")
    count = cursor.fetchone()[0]
    print(f"Total Finans records: {count}")
    
    # Search for check ID 37 specifically
    cursor.execute("SELECT FinansID, Kategori, Aciklama, IslemTuru, Tutar FROM Finans WHERE FinansID = 37")
    c = cursor.fetchone()
    if c:
        print(f"\nTarget Check Found:")
        print(f"ID: {c[0]}")
        print(f"Kategori: {c[1]}")
        print(f"Aciklama: {c[2]}")
        print(f"IslemTuru: {c[3]}")
        print(f"Tutar: {c[4]}")
        
        # Check reasons for exclusion
        reasons = []
        if c[3] != 'Gelir': reasons.append(f"IslemTuru is NOT 'Gelir' (it is {c[3]})")
        
        lower_kat = (c[1] or "").lower()
        lower_desc = (c[2] or "").lower()
        
        if not any(x in (lower_kat + lower_desc) for x in ['çek', 'cek']):
            reasons.append("Does NOT contain 'çek' or 'cek'")
            
        filters = ['tahsil edildi', 'ödendi', 'odendi', 'silindi', 'karşılıksız', 'karsiliksiz', 'kendi çeki', 'kendi ceki', 'ciro edildi']
        for f in filters:
            if f in (lower_kat + lower_desc): # Check both Kat and Desc
                reasons.append(f"Matches filter: '{f}'")
        
        print(f"REASONS FOR FILTRATION: {reasons if reasons else 'NONE'}")
    else:
        print("\nTarget Check ID 37 NOT FOUND!")
        
    # Test case sensitivity for 'Çek'
    cursor.execute("SELECT FinansID FROM Finans WHERE FinansID = 37 AND Kategori LIKE '%çek%'")
    res = cursor.fetchone()
    print(f"\nMatch with '%çek%': {'YES' if res else 'NO'}")
    
    cursor.execute("SELECT FinansID FROM Finans WHERE FinansID = 37 AND Kategori LIKE '%Çek%'")
    res = cursor.fetchone()
    print(f"Match with '%Çek%': {'YES' if res else 'NO'}")
    
    cursor.execute("SELECT FinansID FROM Finans WHERE FinansID = 37 AND (Kategori LIKE '%çek%' OR Kategori LIKE '%Çek%' OR Kategori LIKE '%ÇEK%' OR Kategori LIKE '%cek%' OR Kategori LIKE '%CEK%')")
    res = cursor.fetchone()
    print(f"Match with ANY case in Kategori: {'YES' if res else 'NO'}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
