import os
import sys
from pathlib import Path

# Uygulama ana dizini (Kodun çalıştığı yer)
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
    
    # Veri dizini (Yazılabilir alan: %APPDATA%/ErpYonetim)
    DATA_DIR = Path(os.getenv('APPDATA')) / 'ErpYonetim'
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    APP_DIR = Path(__file__).parent
    DATA_DIR = APP_DIR

# Veritabanı dosya yolu
DATABASE_PATH = DATA_DIR / 'data' / 'erp_database.db'

# Veritabanı klasörü yoksa oluştur
os.makedirs(DATA_DIR / 'data', exist_ok=True)

# SQLite veritabanı bağlantısı
DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

# Default design directory
if getattr(sys, 'frozen', False):
    DESIGN_DIR = os.environ.get('DESIGN_DIR', str(DATA_DIR / 'tasarimlar'))
else:
    DESIGN_DIR = os.environ.get('DESIGN_DIR', str(APP_DIR / 'tasarimlar'))
os.makedirs(DESIGN_DIR, exist_ok=True)

# Overtime rate default (can be overridden by Company.settings)
DEFAULT_OVERTIME_RATE = float(os.environ.get('DEFAULT_OVERTIME_RATE', 50))

# Flask secret key - Üretimde değiştirilmeli!
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Locale and encoding
DEFAULT_LOCALE = os.environ.get('DEFAULT_LOCALE', 'tr')

# Yedek klasörü
BACKUP_DIR = DATA_DIR / 'backups'
os.makedirs(BACKUP_DIR, exist_ok=True)

# Yüklenen dosyalar klasörü
UPLOADS_DIR = DATA_DIR / 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

# E-posta Ayarları (Mail Bildirimleri ve Özetler için)
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')  # E-posta adresiniz
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')  # Uygulama şifreniz
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)
