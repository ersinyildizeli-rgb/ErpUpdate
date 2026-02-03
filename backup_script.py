import shutil
import os
import datetime
import time
from config import DATABASE_PATH, BACKUP_DIR

def backup_database():
    """
    Veritabanını güvenli bir şekilde yedekler (WAL dosyalarıyla birlikte)
    """
    if not os.path.exists(DATABASE_PATH):
        print("Veritabanı dosyası bulunamadı!")
        return False

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_folder = BACKUP_DIR / timestamp
    os.makedirs(backup_folder, exist_ok=True)

    try:
        # Ana db dosyası
        shutil.copy2(DATABASE_PATH, backup_folder / 'erp_database.db')
        
        # WAL ve SHM dosyaları varsa onları da kopyala (Sıcak yedek tutarlılığı için)
        wal_path = str(DATABASE_PATH) + '-wal'
        shutilidx_path = str(DATABASE_PATH) + '-shm'
        
        if os.path.exists(wal_path):
            shutil.copy2(wal_path, backup_folder / 'erp_database.db-wal')
        
        if os.path.exists(shutilidx_path):
            shutil.copy2(shutilidx_path, backup_folder / 'erp_database.db-shm')
            
        print(f"Yedekleme başarılı: {backup_folder}")
        
        # Eski yedekleri temizle (Son 30 yedeği tut)
        clean_old_backups()
        return True
    
    except Exception as e:
        print(f"Yedekleme hatası: {str(e)}")
        return False

def clean_old_backups(keep_count=30):
    try:
        backups = sorted([os.path.join(BACKUP_DIR, d) for d in os.listdir(BACKUP_DIR)], key=os.path.getmtime)
        if len(backups) > keep_count:
            for old_backup in backups[:-keep_count]:
                shutil.rmtree(old_backup)
                print(f"Eski yedek silindi: {old_backup}")
    except Exception as e:
        print(f"Temizlik hatası: {str(e)}")

if __name__ == "__main__":
    print("Yedekleme işlemi başlatılıyor...")
    backup_database()
