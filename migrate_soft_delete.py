import sqlite3
import os
from datetime import datetime
import shutil

def get_db_path():
    # Config'deki mantığı taklit et
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'data', 'erp_database.db')
    return db_path

def apply_migration():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"Veritabanı dosyası bulunamadı: {db_path}")
        return

    print(f"Veritabanı yolu: {db_path}")
    
    # Yedek al
    backup_path = db_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"Yedek alındı: {backup_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Aktif kolonu eklenecek tablolar
    tables_to_update = [
        'Finans', 'BankaHesabi', 'Borclar', 'Alacaklar', 
        'CariHesaplar', 'Urunler', 'Faturalar', 'Teklifler', 
        'Siparisler', 'Receteler', 'UretimEmirleri', 'GiderKategorileri'
    ]

    for table in tables_to_update:
        try:
            # Kolon var mı kontrol et
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if 'Aktif' not in columns:
                print(f"{table} tablosuna Aktif kolonu ekleniyor...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN Aktif BOOLEAN NOT NULL DEFAULT 1")
                conn.commit()
                print(f"{table} güncellendi.")
            else:
                print(f"{table} tablosunda Aktif kolonu zaten var.")
                
        except Exception as e:
            print(f"Hata ({table}): {str(e)}")

    # View veya özel indexler varsa burada oluşturulabilir
    conn.close()
    print("Migrasyon tamamlandı.")

if __name__ == "__main__":
    apply_migration()
