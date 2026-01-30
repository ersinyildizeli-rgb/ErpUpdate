import os
import sys
from pathlib import Path

# Simulate app.py's environment
import config

print(f"Current working directory: {os.getcwd()}")
print(f"DATABASE_PATH from config: {config.DATABASE_PATH}")
print(f"DATABASE_URI from config: {config.DATABASE_URI}")

if os.path.exists(config.DATABASE_PATH):
    print(f"Database file exists at {config.DATABASE_PATH}")
    import sqlite3
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    
    # Check StokHareketleri columns
    try:
        cursor.execute("PRAGMA table_info(StokHareketleri)")
        cols = cursor.fetchall()
        print("Columns in StokHareketleri:")
        for col in cols:
            print(f"  {col[1]}")
    except Exception as e:
        print(f"Error checking StokHareketleri: {e}")
        
    conn.close()
else:
    print(f"Database file NOT FOUND at {config.DATABASE_PATH}")
