import os
import json
import io
import csv
import shutil
import sqlite3
import gzip
import urllib.request
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory
from sqlalchemy import func, or_, and_, text, event, DDL
import services
import config
import sys
from models import db, Personel, Finance, Puantaj, Company, User, BankAccount, Debt, Receivable, Document, ActionLog, CariAccount, Urun, StokHareketi, Fatura, FaturaKalemi, Teklif, TeklifKalemi, Siparis, SiparisKalemi, CekSenet, Recete, ReceteKalemi, UretimEmri, ExpenseCategory
import tempfile
from werkzeug.utils import secure_filename

import ssl

CURRENT_VERSION = '1.0.98'
GITHUB_USER = "ersinyildizeli-rgb"
GITHUB_REPO_NAME = "ErpUpdate"

def get_exchange_rates():
    """USD/TRY kurunu çeker (TCMB veya public API)"""
    try:
        # Hızlı ve ücretsiz bir API (kayıt gerektirmez) - urllib versiyonu
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen("https://api.exchangerate-api.com/v4/latest/TRY", timeout=3, context=ctx) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                rates = data.get('rates', {})
                # TRY bazlı geldiği için USD kurunu 1/rate olarak alıyoruz
                usd_rate = 1 / rates.get('USD', 0.03) # Fallback 1/0.03 ~ 33
                return {'USD': usd_rate, 'EUR': 1/rates.get('EUR', 0.028)}
    except Exception:
        pass
    return {'USD': 35.0, 'EUR': 38.0} # Fallback sabit kurlar

def get_weather(city="Ankara"):
    """Seçilen şehir için hava durumunu çeker (Open-Meteo API)"""
    cities = {
        "Ankara": {"lat": 39.93, "lon": 32.85},
        "İstanbul": {"lat": 41.01, "lon": 28.97},
        "İzmir": {"lat": 38.42, "lon": 27.14},
        "Bursa": {"lat": 40.18, "lon": 29.06},
        "Antalya": {"lat": 36.88, "lon": 30.70},
        "Adana": {"lat": 37.00, "lon": 35.32},
        "Konya": {"lat": 37.87, "lon": 32.48},
        "Gaziantep": {"lat": 37.06, "lon": 37.38},
        "Kayseri": {"lat": 38.72, "lon": 35.48},
        "Samsun": {"lat": 41.28, "lon": 36.33}
    }
    
    city_data = cities.get(city, cities["Ankara"])
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={city_data['lat']}&longitude={city_data['lon']}&current_weather=true"
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(url, timeout=3, context=ctx) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                current = data.get('current_weather', {})
                return {
                    'temp': round(current.get('temperature', 0)),
                    'code': current.get('weathercode', 0),
                    'city': city
                }
    except Exception:
        pass
    return {'temp': 15, 'code': 0, 'city': city} # Fallback

def pick_folder():
    """Native Windows klasör seçme diyaloğunu açar"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw() # Pencereyi gizle
        root.attributes('-topmost', True) # En üstte göster
        folder_selected = filedialog.askdirectory()
        root.destroy()
        return folder_selected
    except Exception:
        return None



def create_backup():
    """Veritabanının yedeğini alır"""
    try:
        # Get custom backup path from DB settings
        try:
            from flask import current_app
            with current_app.app_context():
                company = Company.query.first()
                settings = company.get_settings() if company else {}
                custom_path = settings.get('backup_path')
                
                if custom_path and os.path.exists(custom_path) and os.path.isdir(custom_path):
                    backup_dir = Path(custom_path)
                else:
                    backup_dir = config.BACKUP_DIR
        except Exception:
             # Fallback if no app context or DB error
            backup_dir = config.BACKUP_DIR

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"erp_backup_{timestamp}.db.gz"
        
        # Veritabanını kopyala
        with open(config.DATABASE_PATH, 'rb') as f_in:
            with gzip.open(backup_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Eski yedekleri temizle (son 5 yedeği sakla)
        backups = sorted(backup_dir.glob('erp_backup_*.db.gz'), key=os.path.getmtime, reverse=True)
        for old_backup in backups[5:]:
            try:
                os.remove(old_backup)
            except Exception:
                pass
        
        return backup_file
    except Exception:
        return None

def log_action(islem_turu, modul, detay=None):
    """Sistem günlüklerini kaydeder"""
    try:
        user_id = session.get('user_id')
        ip = request.remote_addr
        log = ActionLog(
            KullaniciID=user_id,
            IslemTuru=islem_turu,
            Modul=modul,
            Detay=detay,
            IpAdresi=ip
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

def parse_float(v, default=0.0):
    """Metin olarak gelen sayıyı float tipine güvenli bir şekilde dönüştürür. 
    Virgül veya nokta ayıraçlarını destekler."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    try:
        # Önce binlik ayıraç olabilecek noktaları temizleyebiliriz ama 
        # genellikle formdan yalın sayı gelir. En kritik olan virgül/nokta değişimi.
        s = str(v).replace(',', '.').strip()
        if not s:
            return default
        return float(s)
    except (ValueError, TypeError):
        return default

def update_cari_balance(cari_id):
    """Cari hesabın bakiyesini finans hareketlerine göre günceller"""
    if not cari_id:
        return
    try:
        cari = CariAccount.query.get(cari_id)
        if not cari:
            return
        
        # Alacaklar (Bizim beklediğimiz para - Satışlar vb.): Bakiye artar (+)
        # Borçlar (Bizim ödememiz gereken para - Alışlar vb.): Bakiye azalır (-)
        # Gider (Para çıkışı - Borç ödedik): Borcumuz azalır -> Bakiye artar (+)
        # Gelir (Para girişi - Alacak tahsil edildi): Alacağımız azalır -> Bakiye düşer (-)
        
        from models import Receivable, Debt
        total_alacak = db.session.query(func.sum(Receivable.AnaTutar)).filter(Receivable.CariID == cari_id, Receivable.Aktif == True).scalar() or 0
        total_borc = db.session.query(func.sum(Debt.AnaTutar)).filter(Debt.CariID == cari_id, Debt.Aktif == True).scalar() or 0
        
        # Karşılıksız çekleri bakiyeden düşür (Onlar gerçek gelir/gider değildir)
        incomes_query = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.CariID == cari_id, 
            Finance.IslemTuru == 'Gelir'
        )
        expenses_query = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.CariID == cari_id, 
            Finance.IslemTuru == 'Gider'
        )
        
        # Karşılıksız/Sanal/İade çekleri bakiyeden düşür
        bad_incomes = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.CariID == cari_id,
            Finance.IslemTuru == 'Gelir',
            (func.lower(Finance.Aciklama).like('%karşılıksız%') | 
             func.lower(Finance.Aciklama).like('%karsiliksiz%') |
             func.lower(Finance.Aciklama).like('%silindi%') |
             func.lower(Finance.Aciklama).like('%iptal%'))
        ).scalar() or 0
        
        raw_incomes = incomes_query.scalar() or 0
        incomes = raw_incomes - bad_incomes
        
        bad_expenses = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.CariID == cari_id,
            Finance.IslemTuru == 'Gider',
            (func.lower(Finance.Aciklama).like('%karşılıksız%') | 
             func.lower(Finance.Aciklama).like('%karsiliksiz%') |
             func.lower(Finance.Aciklama).like('%silindi%') |
             func.lower(Finance.Aciklama).like('%iptal%'))
        ).scalar() or 0
        
        raw_expenses = expenses_query.scalar() or 0
        expenses = raw_expenses - bad_expenses
        
        cari.Bakiye = total_alacak - total_borc + expenses - incomes
        db.session.commit()
    except Exception as e:
        print(f"Cari bakiye güncelleme hatası: {e}")
        db.session.rollback()

def update_bank_balance(bank_id):
    """Banka hesabının bakiyesini finans hareketlerine göre günceller"""
    if not bank_id:
        return
    try:
        from models import BankAccount
        bank = BankAccount.query.get(bank_id)
        if not bank:
            return
            
        # Bankaya ait net bakiye (Gelir - Gider)
        incomes = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.BankaID == bank_id,
            Finance.IslemTuru == 'Gelir'
        ).scalar() or 0
        
        expenses = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.Aktif == True,
            Finance.BankaID == bank_id,
            Finance.IslemTuru == 'Gider'
        ).scalar() or 0
        
        bank.Bakiye = incomes - expenses
        db.session.commit()
    except Exception as e:
        print(f"Banka bakiye güncelleme hatası: {e}")
        db.session.rollback()

def get_local_ip():
    """Cihazın yerel ağdaki IP adresini döndürür"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def toggle_startup(active=True):
    """Uygulamayı Windows başlangıcına ekler veya kaldırır (Registry kullanarak)"""
    try:
        import winreg
        import os
        import sys
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "EnderCelikERP"
        
        if active:
            exe_path = os.path.abspath(sys.executable)
            # Komut satırını oluştur
            if getattr(sys, 'frozen', False):
                # Derlenmiş EXE
                cmd = f'"{exe_path}"'
            else:
                # Script
                try:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    main_file = os.path.join(current_dir, "app.py")
                    if os.path.exists(main_file):
                        cmd = f'"{exe_path}" "{main_file}"'
                    else:
                        cmd = f'"{exe_path}" "{os.path.abspath(sys.argv[0])}"'
                except:
                    cmd = f'"{exe_path}" "{os.path.abspath(sys.argv[0])}"'
            
            # Registry'ye yaz
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            return True
        else:
            # Registry'den sil
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
                winreg.DeleteValue(key, app_name)
                winreg.CloseKey(key)
            except FileNotFoundError:
                pass
            return True
    except Exception as e:
        print(f"Startup toggle error: {e}")
        return False


def create_app():
    DESIGN_DIR = os.environ.get('DESIGN_DIR', config.DESIGN_DIR)
    template_folder = os.path.join(DESIGN_DIR, 'templates') if DESIGN_DIR else None
    static_folder = os.path.join(DESIGN_DIR, 'static') if DESIGN_DIR else None

    # Fallback to internal templates if user design folder not present
    if not (template_folder and os.path.isdir(template_folder)):
        import sys
        if getattr(sys, 'frozen', False):
            # Frozen: check _internal/internal_templates or root/internal_templates
            base_dir = os.path.dirname(sys.executable)
            internal_subdir = os.path.join(base_dir, '_internal')
            
            # Try finding internal_templates in _internal first (PyInstaller 6+)
            candidate = os.path.join(internal_subdir, 'internal_templates')
            if os.path.isdir(candidate):
                template_folder = candidate
            else:
                template_folder = os.path.join(base_dir, 'internal_templates')
        else:
            here = os.path.dirname(__file__)
            template_folder = os.path.join(here, 'internal_templates')

    if not (static_folder and os.path.isdir(static_folder)):
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            internal_subdir = os.path.join(base_dir, '_internal')
            
            candidate = os.path.join(internal_subdir, 'internal_static')
            if os.path.isdir(candidate):
                static_folder = candidate
            else:
                static_folder = os.path.join(base_dir, 'internal_static')
        else:
            here = os.path.dirname(__file__)
            static_folder = os.path.join(here, 'internal_static')

    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', config.DATABASE_URI)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Ensure JSON responses can contain Turkish characters (UTF-8)
    app.config['JSON_AS_ASCII'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', config.SECRET_KEY)

    @app.template_filter('currency')
    def currency_filter(value):
        """Format as 1.234,56"""
        try:
            if value is None:
                return "0,00"
            # Python's default format is 1,234.56 - we swap comma and dot for Turkish locale
            return "{:,.2f}".format(float(value)).replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return "0,00"

    db.init_app(app)

    def ensure_sqlite_schema():
        """SQLite için şema oluşturma ve güncelleme işlemleri"""
        # SQLAlchemy otomatik olarak tabloları oluşturacak
        db.create_all()
        
        # SQLite'da ALTER COLUMN işlemleri için özel işlemler
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(Puantaj)"))
                columns = [row[1] for row in result.fetchall()]
                if 'EksikSaat' not in columns:
                    conn.execute(text("ALTER TABLE Puantaj ADD COLUMN EksikSaat FLOAT NOT NULL DEFAULT 0.0"))
                if 'KesintiTuru' not in columns:
                    conn.execute(text("ALTER TABLE Puantaj ADD COLUMN KesintiTuru VARCHAR(20)"))
                if 'Carpan' not in columns:
                    conn.execute(text("ALTER TABLE Puantaj ADD COLUMN Carpan FLOAT NOT NULL DEFAULT 1.5"))
                
                # Personel tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(Personel)"))
                columns = [row[1] for row in result.fetchall()]
                if 'Aktif' not in columns:
                    conn.execute(text("ALTER TABLE Personel ADD COLUMN Aktif BOOLEAN NOT NULL DEFAULT 1"))
                if 'Unvan' not in columns:
                    conn.execute(text("ALTER TABLE Personel ADD COLUMN Unvan VARCHAR(120)"))
                if 'Email' not in columns:
                    conn.execute(text("ALTER TABLE Personel ADD COLUMN Email VARCHAR(200)"))
                
                # Finans tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(Finans)"))
                columns = [row[1] for row in result.fetchall()]
                if 'BankaID' not in columns:
                    conn.execute(text("ALTER TABLE Finans ADD COLUMN BankaID INTEGER REFERENCES BankaHesabi(BankaID)"))
                if 'CariID' not in columns:
                    conn.execute(text("ALTER TABLE Finans ADD COLUMN CariID INTEGER REFERENCES CariHesaplar(CariID)"))

                # Borclar tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(Borclar)"))
                columns = [row[1] for row in result.fetchall()]
                if 'CariID' not in columns:
                    conn.execute(text("ALTER TABLE Borclar ADD COLUMN CariID INTEGER REFERENCES CariHesaplar(CariID)"))
                
                # Alacaklar tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(Alacaklar)"))
                columns = [row[1] for row in result.fetchall()]
                if 'CariID' not in columns:
                    conn.execute(text("ALTER TABLE Alacaklar ADD COLUMN CariID INTEGER REFERENCES CariHesaplar(CariID)"))

                # StokHareketleri tablosu güncellemeleri (Fatura Entegrasyonu ve Seri No)
                result = conn.execute(text("PRAGMA table_info(StokHareketleri)"))
                columns = [row[1] for row in result.fetchall()]
                if 'FaturaID' not in columns:
                    conn.execute(text("ALTER TABLE StokHareketleri ADD COLUMN FaturaID INTEGER REFERENCES Faturalar(FaturaID)"))
                if 'SeriNo' not in columns:
                    conn.execute(text("ALTER TABLE StokHareketleri ADD COLUMN SeriNo VARCHAR(100)"))
                if 'CariID' not in columns:
                    conn.execute(text("ALTER TABLE StokHareketleri ADD COLUMN CariID INTEGER REFERENCES CariHesaplar(CariID)"))

                # Belgeler tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(Belgeler)"))
                columns = [row[1] for row in result.fetchall()]
                if 'RelationType' not in columns:
                    conn.execute(text("ALTER TABLE Belgeler ADD COLUMN RelationType VARCHAR(50)"))
                if 'RelationID' not in columns:
                    conn.execute(text("ALTER TABLE Belgeler ADD COLUMN RelationID INTEGER"))
                if 'Kategori' not in columns:
                    conn.execute(text("ALTER TABLE Belgeler ADD COLUMN Kategori VARCHAR(50)"))
                if 'DosyaBoyutu' not in columns:
                    conn.execute(text("ALTER TABLE Belgeler ADD COLUMN DosyaBoyutu INTEGER"))
                
                # IslemLoglari tablosu güncellemeleri
                result = conn.execute(text("PRAGMA table_info(IslemLoglari)"))
                columns = [row[1] for row in result.fetchall()]
                if 'IslemTuru' not in columns:
                    conn.execute(text("ALTER TABLE IslemLoglari ADD COLUMN IslemTuru VARCHAR(50) DEFAULT 'İşlem'"))
                if 'Detay' not in columns:
                    conn.execute(text("ALTER TABLE IslemLoglari ADD COLUMN Detay VARCHAR(500)"))
                if 'IpAdresi' not in columns:
                    conn.execute(text("ALTER TABLE IslemLoglari ADD COLUMN IpAdresi VARCHAR(50)"))
                
                # Diğer Kalem tabloları için SeriNo
                for table in ['FaturaKalemleri', 'TeklifKalemleri', 'SiparisKalemleri', 'StokHareketleri']:
                    try:
                        result = conn.execute(text(f"PRAGMA table_info({table})"))
                        columns = [row[1] for row in result.fetchall()]
                        if columns and 'SeriNo' not in columns:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN SeriNo VARCHAR(100)"))
                    except:
                        pass
                
                # StokHareketleri ek kolonlar
                result = conn.execute(text("PRAGMA table_info(StokHareketleri)"))
                columns = [row[1] for row in result.fetchall()]
                if 'FaturaID' not in columns:
                    conn.execute(text("ALTER TABLE StokHareketleri ADD COLUMN FaturaID INTEGER REFERENCES Faturalar(FaturaID)"))
                if 'CariID' not in columns:
                    conn.execute(text("ALTER TABLE StokHareketleri ADD COLUMN CariID INTEGER REFERENCES CariHesaplar(CariID)"))

                # Finans kategorisi
                result = conn.execute(text("PRAGMA table_info(Finans)"))
                columns = [row[1] for row in result.fetchall()]
                if 'KategoriID' not in columns:
                    conn.execute(text("ALTER TABLE Finans ADD COLUMN KategoriID INTEGER"))
                
                # Tüm tablolara Aktif kolonu kontrolü (Soft Delete için)
                tables_for_soft_delete = [
                    'Finans', 'BankaHesabi', 'Borclar', 'Alacaklar', 
                    'CariHesaplar', 'Urunler', 'Faturalar', 'Teklifler', 
                    'Siparisler', 'Receteler', 'UretimEmirleri', 'GiderKategorileri'
                ]
                for table in tables_for_soft_delete:
                    try:
                        result = conn.execute(text(f"PRAGMA table_info({table})"))
                        cols = [row[1] for row in result.fetchall()]
                        if 'Aktif' not in cols:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN Aktif BOOLEAN NOT NULL DEFAULT 1"))
                    except Exception as e:
                        print(f"Schema update (Aktif check) failed for {table}: {e}")
        except Exception as e:
            app.logger.error(f"Schema update error: {e}")

    # Mutex ekle (Installer'ın programı kapatabilmesi için)
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, "ErpBackendMutex")
        if kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            pass # Zaten çalışıyor, sorun değil
    except:
        pass

    # Veritabanı tablolarını oluştur ve başlangıç verilerini ekle
    with app.app_context():
        db_available = False
        try:
            # SQLite için şema oluştur
            ensure_sqlite_schema()
            
            # Varsayılan şirket bilgisi ekle
            # Varsayılan şirket bilgisi ekle (Kullanıcı kendi girmeli, örnek veri eklenmiyor)
            # if Company.query.count() == 0:
            #     default_company = Company(
            #         SirketAdi='Yeni Şirket',
            #         VergiNo='0000000000',
            #         MesaiUcreti=50.0
            #     )
            #     db.session.add(default_company)
            #     db.session.commit()
            
            # Eğer hiç şirket yoksa, ayarlar sayfası hata vermemek için boş bir tane oluşturabiliriz 
            # ancak kullanıcı "hiç iz kalmasın" dediği için bunu pass geçiyoruz.
            # Uygulama şirket verisi olmadığında hata veriyorsa, app.py içinde buna null check eklemeliyiz.
            if Company.query.count() == 0:
                pass
            
            # Varsayılan admin kullanıcısı ekle
            if User.query.count() == 0:
                admin = User(
                    KullaniciAdi='admin',
                    Email='admin@example.com',
                    Rol='admin',
                    Aktif=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                app.logger.info('Varsayılan admin kullanıcısı oluşturuldu.')
            
            # İlk yedeği al
            backup_file = create_backup()
            if backup_file:
                app.logger.info(f'İlk yedek oluşturuldu: {backup_file}')
            
            db_available = True
            # SQL Server şeması güncellendi.
        except Exception:
            pass # Clean startup
        
        app.db_available = db_available

    @app.context_processor
    def inject_company_info():
        try:
            company = Company.query.first()
            name = company.SirketAdi if company else 'Personel Yönetimi'
        except:
            name = 'Personel Yönetimi'
        return dict(company_name=name, datetime=datetime, datetime_lib=datetime)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'):
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    def roles_required(*roles):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not session.get('user_id'):
                    return redirect(url_for('login'))
                if session.get('user_role') not in roles and session.get('user_role') != 'admin':
                    flash('Bu işlem için yetkiniz bulunmamaktadır.', 'danger')
                    return redirect(url_for('dashboard'))
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            try:
                identifier = (request.form.get('username') or '').strip()
                password = request.form.get('password') or ''
                if not identifier or not password:
                    flash('Kullanıcı adı ve şifre zorunludur.', 'error')
                    return render_template('login.html')
                user = User.query.filter(
                    or_(User.KullaniciAdi == identifier, User.Email == identifier)
                ).first()
                if not user or not user.Aktif or not user.check_password(password):
                    flash('Geçersiz kullanıcı bilgileri.', 'error')
                    return render_template('login.html')
                session['user_id'] = user.KullaniciID
                session['user_name'] = user.KullaniciAdi
                session['user_role'] = user.Rol
                log_action("Giriş", "Auth", f"{user.KullaniciAdi} sisteme giriş yaptı.")
                return redirect(url_for('dashboard'))
            except Exception as e:
                app.logger.exception('Login error')
                flash(f'Giriş hatası: {str(e)}', 'error')
                return render_template('login.html')
        if session.get('user_id'):
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        log_action("Çıkış", "Auth", "Kullanıcı sistemden çıkış yaptı.")
        session.clear()
        return redirect(url_for('login'))

    @app.route('/logs')
    @login_required
    def view_logs():
        """Sistem işlem günlüklerini görüntüler"""
        if session.get('user_role') != 'admin':
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            return redirect(url_for('dashboard'))
        
        logs = ActionLog.query.order_by(ActionLog.Tarih.desc()).limit(500).all()
        return render_template('loglar.html', logs=logs)

    @app.route('/uploads/<path:filename>')
    @login_required
    def uploaded_file(filename):
        """Yüklenen dosyaları güvenli bir şekilde servis eder"""
        return send_from_directory(config.UPLOADS_DIR, filename)

    @app.route('/')
    @login_required
    def dashboard():
        try:
            personel_count = Personel.query.filter_by(Aktif=True).count()
            finance_entries = Finance.query.filter_by(Aktif=True).all()

            cash_entries = []
            for f in finance_entries:
                cat_lower = (f.Kategori or '').lower()
                desc_lower = (f.Aciklama or '').lower()
                islem_lower = (f.IslemTuru or '').lower()

                if islem_lower not in ('gelir', 'gider'):
                    continue

                # Eğer bir banka ID'si varsa bu nakit girişi değildir
                if f.BankaID is not None:
                    continue

                if 'kdv' in cat_lower and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower)):
                    continue

                if 'çek' in cat_lower or 'çek' in desc_lower:
                    continue
                
                cash_entries.append(f)

            cash_balance = 0.0
            for f in cash_entries:
                amount = float(f.Tutar or 0)
                islem_lower = (f.IslemTuru or '').lower()
                if islem_lower == 'gelir':
                    cash_balance += amount
                elif islem_lower == 'gider':
                    cash_balance -= amount

            total_finance = cash_balance
            total_salaries = db.session.query(func.coalesce(func.sum(Personel.NetMaas), 0)).scalar() or 0
            
            company = Company.query.first()
            company_name = company.SirketAdi if company else 'ERP Şirketi'
            current_date = datetime.now().strftime('%d.%m.%Y %H:%M')
            # Finansal özet: kategori bazlı toplamlar
            categories = {}
            try:
                rows = db.session.query(Finance.Kategori, func.coalesce(func.sum(Finance.Tutar), 0)).filter(Finance.Aktif==True).group_by(Finance.Kategori).all()
                for k, v in rows:
                    if k:
                        categories[k] = float(v or 0)
            except Exception:
                categories = {}

            tax_total = 0.0
            for k, v in categories.items():
                key_lower = (k or '').lower()
                if any(w in key_lower for w in ('vergi', 'sgk')):
                    tax_total += float(v or 0)
                elif 'kdv' in key_lower:
                    if not (('indirilecek' in key_lower) or ('i̇ndirilecek' in key_lower)):
                        tax_total += float(v or 0)
            tax_paid = 0.0
            tax_remaining = max(0.0, tax_total - tax_paid)

            kdv_hesaplanan = 0.0
            kdv_indirilecek = 0.0
            for e in finance_entries:
                name = e.Kategori or ''
                cat_lower = (name or '').lower()
                if 'kdv' in cat_lower:
                    amount = float(e.Tutar or 0)
                    if 'hesaplanan' in cat_lower:
                        kdv_hesaplanan += amount
                    elif ('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower):
                        kdv_indirilecek += amount
            kdv_net = kdv_hesaplanan - kdv_indirilecek

            # Çek bilgileri: Gelişmiş filtreleme ve normalizasyon
            try:
                def normalize_tr(text):
                    if not text: return ""
                    text = text.lower()
                    text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
                    return text

                checks_incoming = 0.0
                checks_outgoing = 0.0
                checks_bank = 0.0
                
                for f in finance_entries:
                    cat = (f.Kategori or '').lower()
                    desc = (f.Aciklama or '').lower()
                    if any(w in cat or w in desc for w in ['çek', 'cek', 'karşılıksız', 'karsiliksiz']):
                        n_cat = normalize_tr(cat)
                        n_desc = normalize_tr(desc)
                        
                        is_bad = 'karsiliksiz' in n_cat or 'karsiliksiz' in n_desc
                        is_collected = 'tahsil edildi' in n_cat or 'tahsil edildi' in n_desc or 'odendi' in n_cat or 'odendi' in n_desc
                        
                        if is_bad or is_collected:
                            continue
                            
                        amt = float(f.Tutar or 0)
                        is_income = (f.IslemTuru or '').lower() == 'gelir'
                        is_bank = 'bankaya verildi' in n_cat or 'bankaya verildi' in n_desc or 'bankaya verilen' in n_cat or 'bankaya verilen' in n_desc
                        
                        if is_bank:
                            checks_bank += amt
                        elif is_income:
                            # 'verildi' veya 'ciro' içeriği varsa 'Portfolio' (Portföy) dışına (Müşteride) çıkaralım
                            if 'verildi' not in n_cat and 'ciro' not in n_desc and 'ciro' not in n_cat:
                                checks_incoming += amt
                        else:
                            # Gider ise ve 'ciro' değilse 'Payable' (Ödenecek)
                            if 'ciro' not in n_cat and 'ciro' not in n_desc:
                                checks_outgoing += amt
            except Exception as e:
                app.logger.error(f"Dashboard checks error: {e}")
                checks_incoming = 0.0
                checks_outgoing = 0.0
                checks_bank = 0.0

            # Upcoming holidays
            settings = company.get_settings() if company else {}
            public_holidays = settings.get('public_holidays', [])
            upcoming_holidays = []
            today_str = date.today().strftime('%Y-%m-%d')
            for h in public_holidays:
                if h['date'] >= today_str:
                    upcoming_holidays.append(h)
            upcoming_holidays.sort(key=lambda x: x['date'])
            upcoming_holidays = upcoming_holidays[:3] # Show only next 3

            # Chart Data - Monthly Revenue & Expense
            monthly_labels = []
            monthly_income = []
            monthly_expense = []
            
            end_date = date.today().replace(day=1)
            for i in range(5, -1, -1):
                m_date = end_date - timedelta(days=i*30) # Approximate
                # Adjust to month start
                m_date = m_date.replace(day=1)
                month_name = m_date.strftime('%b')
                monthly_labels.append(month_name)
                
                # Query for this month
                next_month = (m_date + timedelta(days=32)).replace(day=1)
                
                # Query for this month - EXCLUDING checks
                inc = db.session.query(func.sum(Finance.Tutar)).filter(
                    Finance.Aktif == True,
                    Finance.Tarih >= m_date,
                    Finance.Tarih < next_month,
                    Finance.IslemTuru == 'Gelir',
                    ~Finance.Aciklama.ilike('%çek%'),
                    ~Finance.Aciklama.ilike('%Çek%'),
                    ~Finance.Aciklama.ilike('%ÇEK%'),
                    ~Finance.Aciklama.ilike('%cek%'),
                    ~Finance.Aciklama.ilike('%CEK%'),
                    ~Finance.Kategori.ilike('%çek%'),
                    ~Finance.Kategori.ilike('%Çek%'),
                    ~Finance.Kategori.ilike('%ÇEK%'),
                    ~Finance.Kategori.ilike('%cek%'),
                    ~Finance.Kategori.ilike('%CEK%')
                ).scalar() or 0
                
                exp = db.session.query(func.sum(Finance.Tutar)).filter(
                    Finance.Aktif == True,
                    Finance.Tarih >= m_date,
                    Finance.Tarih < next_month,
                    Finance.IslemTuru == 'Gider',
                    ~Finance.Aciklama.ilike('%çek%'),
                    ~Finance.Aciklama.ilike('%Çek%'),
                    ~Finance.Aciklama.ilike('%ÇEK%'),
                    ~Finance.Aciklama.ilike('%cek%'),
                    ~Finance.Aciklama.ilike('%CEK%'),
                    ~Finance.Kategori.ilike('%çek%'),
                    ~Finance.Kategori.ilike('%Çek%'),
                    ~Finance.Kategori.ilike('%ÇEK%'),
                    ~Finance.Kategori.ilike('%cek%'),
                    ~Finance.Kategori.ilike('%CEK%')
                ).scalar() or 0
                
                monthly_income.append(float(inc))
                monthly_expense.append(float(exp))

            chart_data = {
                'monthly': {
                    'labels': monthly_labels,
                    'income': monthly_income,
                    'expense': monthly_expense
                }
            }

            # Expense Categories Data
            exp_categories = db.session.query(Finance.Kategori, func.sum(Finance.Tutar)).filter(
                Finance.Aktif == True,
                Finance.IslemTuru == 'Gider'
            ).group_by(Finance.Kategori).all()
            
            chart_data['expense_categories'] = {
                'labels': [row[0] or 'Diğer' for row in exp_categories],
                'values': [float(row[1] or 0) for row in exp_categories]
            }

            # Department Data
            dept_counts = db.session.query(Personel.Departman, func.count(Personel.PersonelID)).filter(Personel.Aktif==True).group_by(Personel.Departman).all()
            chart_data['dept_distribution'] = {
                'labels': [row[0] or 'Tanımsız' for row in dept_counts],
                'values': [int(row[1] or 0) for row in dept_counts]
            }

            total_income = sum(monthly_income)
            total_expense = sum(monthly_expense)

            # Bugünün özeti
            today = date.today()
            # Bugünün özeti - EXCLUDING checks
            today_income = db.session.query(func.sum(Finance.Tutar)).filter(
                Finance.Aktif == True,
                Finance.Tarih == today, 
                Finance.IslemTuru == 'Gelir',
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('çek'),
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('cek'),
                ~Finance.Aciklama.ilike('%çek%'),
                ~Finance.Aciklama.ilike('%ÇEK%'),
                ~Finance.Aciklama.ilike('%cek%'),
                ~Finance.Aciklama.ilike('%CEK%')
            ).scalar() or 0
            
            today_expense = db.session.query(func.sum(Finance.Tutar)).filter(
                Finance.Tarih == today, 
                Finance.IslemTuru == 'Gider',
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('çek'),
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('cek'),
                ~Finance.Aciklama.ilike('%çek%'),
                ~Finance.Aciklama.ilike('%ÇEK%'),
                ~Finance.Aciklama.ilike('%cek%'),
                ~Finance.Aciklama.ilike('%CEK%')
            ).scalar() or 0

            # Son İşlemler (Timeline için) - Çekleri ve silinenleri kesinlikle filtrele
            # SQLite ilike bazen Türkçe karakterlerde büyük/küçük harf duyarlı olabildiği için her varyasyonu ekliyoruz
            # Ayrıca coalesce ve lower kullanarak null ve karakter seti problemlerini aşıyoruz
            recent_transactions = Finance.query.filter(
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('çek'),
                ~func.lower(func.coalesce(Finance.Aciklama, '')).contains('cek'),
                ~func.lower(func.coalesce(Finance.Kategori, '')).contains('çek'),
                ~func.lower(func.coalesce(Finance.Kategori, '')).contains('cek'),
                ~Finance.Aciklama.ilike('%çek%'),
                ~Finance.Aciklama.ilike('%ÇEK%'),
                ~Finance.Aciklama.ilike('%cek%'),
                ~Finance.Aciklama.ilike('%CEK%'),
                ~Finance.Kategori.ilike('%çek%'),
                ~Finance.Kategori.ilike('%ÇEK%'),
                ~Finance.Kategori.ilike('%cek%'),
                ~Finance.Kategori.ilike('%CEK%'),
                ~Finance.Aciklama.ilike('%silindi%'),
                ~Finance.Aciklama.ilike('%karşılıksız%'),
                ~Finance.Aciklama.ilike('%karsiliksiz%')
            ).order_by(Finance.Tarih.desc(), Finance.FinansID.desc()).limit(15).all()

            # Alacak/Borç Toplamları
            from models import Receivable, Debt, CariAccount
            total_receivables = db.session.query(func.sum(Receivable.KalanTutar)).scalar() or 0
            total_payables = db.session.query(func.sum(Debt.KalanTutar)).scalar() or 0

            # Stok Verileri
            inventory_total_value = db.session.query(func.sum(Urun.StokMiktari * Urun.AlisFiyati)).scalar() or 0
            critical_stock_count = Urun.query.filter(Urun.StokMiktari <= Urun.KritikStok).count()
            critical_products = Urun.query.filter(Urun.StokMiktari <= Urun.KritikStok).limit(5).all()

            # Banka Toplam Varlık (TRY cinsinden yaklaşık)
            bank_total = sum(b.Bakiye for b in BankAccount.query.all() if (b.ParaBirimi or 'TRY') == 'TRY')

            # Bugünün personel katılım özeti
            attendance_summary = {
                'geldi': db.session.query(func.count(Puantaj.PuantajID)).filter(Puantaj.Tarih == today, func.lower(Puantaj.Durum) == 'geldi').scalar() or 0,
                'izinli': db.session.query(func.count(Puantaj.PuantajID)).filter(Puantaj.Tarih == today, func.lower(Puantaj.Durum) == 'izinli').scalar() or 0,
                'yok': max(0, personel_count - (db.session.query(func.count(Puantaj.PuantajID)).filter(Puantaj.Tarih == today).scalar() or 0))
            }

            # Yaklaşan Ödemeler/Tahsilatlar (Vadesi gelenler - 7 gün)
            next_7_days = today + timedelta(days=7)
            due_alerts = []
            
            # Borçlar
            upcoming_debts = Debt.query.filter(Debt.VadeTarihi >= today, Debt.VadeTarihi <= next_7_days, Debt.Durum != 'Ödendi').all()
            for d in upcoming_debts:
                due_alerts.append({'type': 'borc', 'title': d.BorcVeren, 'amount': d.KalanTutar, 'date': d.VadeTarihi})
                
            # Alacaklar
            upcoming_receivables = Receivable.query.filter(Receivable.VadeTarihi >= today, Receivable.VadeTarihi <= next_7_days, Receivable.Durum != 'Alındı').all()
            for r in upcoming_receivables:
                due_alerts.append({'type': 'alacak', 'title': r.Alacakli, 'amount': r.KalanTutar, 'date': r.VadeTarihi})
            
            due_alerts.sort(key=lambda x: x['date'] if x['date'] else today)

            # Döviz Kurları
            exchange_rates = get_exchange_rates()

            # Hava Durumu
            selected_city = request.args.get('city', 'Ankara')
            weather = get_weather(selected_city)

            # Net Finansal Durum
            net_balance = total_receivables - total_payables

            return render_template('dashboard.html', 
                                 personel_count=personel_count,
                                 total_finance=total_finance, 
                                 total_salaries=total_salaries,
                                 total_income=total_income,
                                 total_expense=total_expense,
                                 total_receivables=total_receivables,
                                 total_payables=total_payables,
                                 net_balance=net_balance,
                                 bank_total=bank_total,
                                 inventory_total_value=inventory_total_value,
                                 critical_stock_count=critical_stock_count,
                                 critical_products=critical_products,
                                 today_income=today_income,
                                 today_expense=today_expense,
                                 recent_transactions=recent_transactions,
                                 exchange_rates=exchange_rates,
                                 weather=weather,
                                 attendance_summary=attendance_summary,
                                 due_alerts=due_alerts,
                                 company_name=company_name,
                                 current_date=current_date,
                                 categories=categories,
                                 tax_total=tax_total,
                                 tax_paid=tax_paid,
                                 tax_remaining=tax_remaining,
                                 kdv_hesaplanan=kdv_hesaplanan,
                                 kdv_indirilecek=kdv_indirilecek,
                                 kdv_net=kdv_net,
                                 checks_incoming=checks_incoming,
                                 checks_outgoing=checks_outgoing,
                                 checks_bank=checks_bank,
                                 upcoming_holidays=upcoming_holidays,
                                 chart_data=chart_data)
        except Exception as e:
            app.logger.exception('Dashboard error')
            return "Dashboard error: {}".format(e), 500

    @app.route('/api/select_folder')
    @login_required
    def api_select_folder():
        """Backend'den klasör seçme diyaloğunu açar"""
        try:
            folder_selected = pick_folder()
            return jsonify({'path': folder_selected})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/check_update')
    @login_required
    @roles_required('admin')
    def api_check_update():
        """GitHub üzerinden yeni versiyon kontrolü yapar"""
        try:
            # URL'yi parçalı oluşturarak hata payını azaltıyoruz
            url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO_NAME}/releases/latest"
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            
            # Bazı sistemlerdeki SSL sertifika hatasını aşmak için
            ctx = ssl._create_unverified_context()
            
            with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # 'v1.0.1' -> '1.0.1'
                    tag = data.get('tag_name', '').lower()
                    latest_v_str = tag.replace('v', '').strip()
                    current_v_str = CURRENT_VERSION.lower().replace('v', '').strip()
                    
                    app.logger.info(f"Update check: Current={current_v_str}, Latest={latest_v_str}")
                    
                    # Versiyonları numeric olarak karşılaştır (Örn: 1.0.10 > 1.0.9)
                    def v_to_tuple(v):
                        return tuple(map(int, (v.split('.') if '.' in v else [v])))
                    
                    try:
                        has_new_version = v_to_tuple(latest_v_str) > v_to_tuple(current_v_str)
                    except:
                        has_new_version = latest_v_str > current_v_str

                    if has_new_version:
                        assets = data.get('assets', [])
                        download_url = None
                        for asset in assets:
                            if asset['name'].lower().endswith('.exe'):
                                download_url = asset['browser_download_url']
                                break
                        
                        return jsonify({
                            'has_update': True,
                            'latest_version': latest_v_str,
                            'current_version': CURRENT_VERSION,
                            'notes': data.get('body', ''),
                            'url': download_url
                        })
            
            return jsonify({'has_update': False, 'current_version': CURRENT_VERSION})
        except urllib.error.HTTPError as e:
            app.logger.error(f"GitHub API HTTP Error {e.code}: {e.reason}")
            return jsonify({'error': f"Güncelleme dosyası bulunamadı (Repo ismi hatalı olabilir): {e.code}"}), 500
        except Exception as e:
            app.logger.error(f"Update check error: {str(e)}")
            return jsonify({'error': f"Bağlantı hatası: {str(e)}"}), 500

    @app.route('/api/apply_update', methods=['POST'])
    @login_required
    @roles_required('admin')
    def api_apply_update():
        """Yeni versiyonu indirir ve kurulumu başlatır"""
        try:
            download_url = request.json.get('url')
            if not download_url:
                return jsonify({'error': 'İndirme linki bulunamadı.'}), 400
            
            # Temp klasörüne indir
            temp_dir = tempfile.gettempdir()
            setup_path = os.path.join(temp_dir, "ErpUpdateSetup.exe")
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(download_url, headers=headers)
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=ctx) as response:
                with open(setup_path, 'wb') as f:
                    f.write(response.read())
            
            # Kurulumu başlat ve programı kapat
            # os.startfile yerine subprocess kullanıyoruz ki hata yönetimi daha iyi olsun
            # "/VERYSILENT" parametresi Inno Setup için sessiz kurulum demektir (kullanıcıya sormaz)
            import subprocess
            subprocess.Popen([setup_path, "/VERYSILENT"], shell=True)
            
            # Programı kibarca kapat (birkaç saniye sonra)
            def shutdown():
                import time
                time.sleep(2)
                os._exit(0)
            
            import threading
            threading.Thread(target=shutdown).start()
            
            return jsonify({'success': True, 'message': 'Güncelleme indirildi, kurulum başlıyor...'})
        except Exception as e:
            app.logger.error(f"Applying update failed: {e}")
            return jsonify({'error': f"Güncelleme sırasında hata oluştu: {str(e)}"}), 500

    @app.route('/ayarlar/kullanicilar', methods=['GET'])
    @login_required
    @roles_required('admin')
    def ayarlar_kullanicilar():
        try:
            users = User.query.order_by(User.KullaniciAdi.asc()).all()
            return render_template('kullanicilar.html', users=users)
        except Exception as e:
            app.logger.exception('Kullanicilar error')
            return "Error: {}".format(e), 500

    @app.route('/ayarlar', methods=['GET'])
    @login_required
    @roles_required('admin')
    def ayarlar():
        try:
            company = Company.query.first()
            settings = company.get_settings() if company else {}
            users = User.query.order_by(User.KullaniciAdi.asc()).all()
            # Başlangıçta çalıştırma kontrolü (Registry üzerinden)
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "EnderCelikERP")
                    is_startup = True
                except FileNotFoundError:
                    is_startup = False
                winreg.CloseKey(key)
            except:
                is_startup = False

            # Read latest test status
            test_status = None
            try:
                status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests', 'status.json')
                if os.path.exists(status_path):
                    with open(status_path, 'r', encoding='utf-8') as f:
                        test_status = json.load(f)
            except Exception as e:
                app.logger.error(f"Failed to read test status: {e}")

            return render_template('ayarlar.html', 
                                 company=company, 
                                 settings=settings, 
                                 users=users, 
                                 current_version=CURRENT_VERSION,
                                 local_ip=get_local_ip(),
                                 is_startup=is_startup,
                                 test_status=test_status)
        except Exception as e:
            app.logger.exception('Ayarlar error')
            return "Error: {}".format(e), 500

    @app.route('/ayarlar/company', methods=['POST'])
    @login_required
    @roles_required('admin')
    def ayarlar_company_update():
        try:
            company = Company.query.first()
            if not company:
                company = Company(
                    SirketAdi=request.form.get('company_name') or 'Personel Yönetimi',
                    VergiNo=request.form.get('tax_no') or '',
                    MesaiUcreti=50.0
                )
                db.session.add(company)
            else:
                company.SirketAdi = request.form.get('company_name') or company.SirketAdi
                company.VergiNo = request.form.get('tax_no') or company.VergiNo
            
            settings = company.get_settings()
            settings['adres'] = request.form.get('address') or settings.get('adres', '')
            settings['email'] = request.form.get('email') or settings.get('email', '')
            settings['phone'] = request.form.get('phone') or settings.get('phone', '')
            settings['tax_office'] = request.form.get('tax_office') or settings.get('tax_office', '')
            settings['backup_path'] = request.form.get('backup_path') or settings.get('backup_path', '')
            
            # SMTP Settings
            if request.form.get('smtp_server'):
                settings['smtp_server'] = request.form.get('smtp_server')
                settings['smtp_port'] = int(request.form.get('smtp_port') or 587)
                settings['smtp_tls'] = request.form.get('smtp_tls') == 'true'
                settings['smtp_user'] = request.form.get('smtp_user') or ''
                settings['smtp_password'] = request.form.get('smtp_password') or ''
                settings['smtp_from_name'] = request.form.get('smtp_from_name') or ''
            
            company.set_settings(settings)
            db.session.commit()
            flash('Şirket ayarları başarıyla kaydedildi.', 'success')
            return redirect(url_for('ayarlar'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Ayarlar company update error')
            return "Error: {}".format(e), 500

    @app.route('/api/toggle_startup', methods=['POST'])
    @login_required
    @roles_required('admin')
    def api_toggle_startup():
        data = request.json
        active = data.get('active', False)
        success = toggle_startup(active)
        return jsonify({'success': success})

    @app.route('/ayarlar/finans', methods=['POST'])
    @login_required
    @roles_required('admin')
    def ayarlar_finans_update():
        try:
            company = Company.query.first()
            if not company:
                company = Company(
                    SirketAdi='Personel Yönetimi',
                    VergiNo='',
                    MesaiUcreti=50.0
                )
                db.session.add(company)
            
            settings = company.get_settings()
            
            # Currency
            currency = request.form.get('currency') or 'TRY'
            settings['currency'] = currency
            
            # Monthly Working Hours
            try:
                settings['monthly_working_hours'] = float(request.form.get('monthly_working_hours') or 225)
            except ValueError:
                settings['monthly_working_hours'] = 225.0
            
            # Weekly Schedule
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            weekly_schedule = {}
            for day in days:
                break_val = request.form.get(f'schedule_{day}_break')
                weekly_schedule[day] = {
                    'active': request.form.get(f'schedule_{day}_active') == 'on',
                    'start': request.form.get(f'schedule_{day}_start') or '08:30',
                    'end': request.form.get(f'schedule_{day}_end') or '18:00',
                    'break': int(break_val) if (break_val is not None and break_val != '') else (90 if day != 'saturday' else 30),
                    'multiplier': float(request.form.get(f'schedule_{day}_multiplier') or 1.5)
                }
            settings['weekly_schedule'] = weekly_schedule

            # Public Holidays
            holiday_names = request.form.getlist('holiday_name[]')
            holiday_dates = request.form.getlist('holiday_date[]')
            holiday_multipliers = request.form.getlist('holiday_multiplier[]')
            
            public_holidays = []
            for name, dt, mult in zip(holiday_names, holiday_dates, holiday_multipliers):
                name = (name or '').strip()
                dt = (dt or '').strip()
                if name and dt:
                    public_holidays.append({
                        'name': name,
                        'date': dt,
                        'multiplier': float(mult or 2.0)
                    })
            public_holidays.sort(key=lambda x: x['date'])
            settings['public_holidays'] = public_holidays
            
            company.set_settings(settings)
            db.session.commit()
            flash('Finansal ayarlar ve çalışma programı güncellendi.', 'success')
            return redirect(url_for('ayarlar'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Ayarlar finans update error')
            flash('Hata: {}'.format(e), 'danger')
            return redirect(url_for('ayarlar'))

    @app.route('/ayarlar/kullanici_ekle', methods=['POST'])
    @login_required
    @roles_required('admin')
    def ayarlar_kullanici_ekle():
        try:
            username = (request.form.get('username') or '').strip()
            email = (request.form.get('email') or '').strip()
            password = request.form.get('password') or ''
            role = (request.form.get('role') or 'admin').strip() or 'admin'
            active = bool(request.form.get('active'))
            if not username or not password:
                flash('Kullanıcı adı ve şifre zorunludur.', 'error')
                return redirect(url_for('ayarlar'))
            existing = User.query.filter_by(KullaniciAdi=username).first()
            if existing:
                flash('Bu kullanıcı adı zaten kullanılıyor.', 'error')
                return redirect(url_for('ayarlar'))
            user = User(
                KullaniciAdi=username,
                Email=email or None,
                Rol=role,
                Aktif=active
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Kullanıcı başarıyla oluşturuldu.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Ayarlar kullanıcı ekleme hatası')
            flash('Kullanıcı eklenirken bir hata oluştu.', 'error')
        return redirect(url_for('ayarlar_kullanicilar'))

    @app.route('/ayarlar/kullanici_islem', methods=['POST'])
    @login_required
    @roles_required('admin')
    def ayarlar_kullanici_islem():
        try:
            user_id = int(request.form.get('user_id') or 0)
            action = (request.form.get('action') or '').strip()
            if not user_id:
                flash('Geçersiz kullanıcı.', 'error')
                return redirect(url_for('ayarlar'))
            user = User.query.get(user_id)
            if not user:
                flash('Kullanıcı bulunamadı.', 'error')
                return redirect(url_for('ayarlar'))

            current_user_id = session.get('user_id')

            if action == 'toggle_active':
                if user.KullaniciID == current_user_id:
                    flash('Kendi hesabınızı bu ekrandan pasif yapamazsınız.', 'error')
                else:
                    user.Aktif = not user.Aktif
                    db.session.commit()
                    flash('Kullanıcı durumu güncellendi.', 'success')
            elif action == 'delete':
                if user.KullaniciID == current_user_id:
                    flash('Kendi hesabınızı silemezsiniz.', 'error')
                else:
                    db.session.delete(user)
                    db.session.commit()
                    flash('Kullanıcı silindi.', 'success')
            else:
                flash('Geçersiz işlem.', 'error')
            return redirect(url_for('ayarlar_kullanicilar'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Ayarlar kullanıcı işlem hatası')
            flash('Kullanıcı işleminde bir hata oluştu.', 'error')
            return redirect(url_for('ayarlar_kullanicilar'))

    def build_raporlar_context():
        # Aggressive filtering for check-related transactions and deleted items
        check_filters = [
            ~Finance.Aciklama.ilike('%çek%'),
            ~Finance.Aciklama.ilike('%Çek%'),
            ~Finance.Aciklama.ilike('%ÇEK%'),
            ~Finance.Aciklama.ilike('%cek%'),
            ~Finance.Aciklama.ilike('%CEK%'),
            ~Finance.Kategori.ilike('%çek%'),
            ~Finance.Kategori.ilike('%Çek%'),
            ~Finance.Kategori.ilike('%ÇEK%'),
            ~Finance.Kategori.ilike('%cek%'),
            ~Finance.Kategori.ilike('%CEK%'),
            ~Finance.Aciklama.ilike('%silindi%'),
            ~Finance.Aciklama.ilike('%karşılıksız%'),
            ~Finance.Aciklama.ilike('%karsiliksiz%')
        ]

        total_income = db.session.query(func.coalesce(func.sum(Finance.Tutar), 0)).filter(
            func.lower(Finance.IslemTuru) == 'gelir',
            *check_filters
        ).scalar() or 0
        total_expense = db.session.query(func.coalesce(func.sum(Finance.Tutar), 0)).filter(
            func.lower(Finance.IslemTuru) == 'gider',
            *check_filters
        ).scalar() or 0

        today = date.today()
        months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

        monthly_summary = []
        for i in range(5, -1, -1):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)

            rows = db.session.query(
                func.lower(Finance.IslemTuru),
                func.coalesce(func.sum(Finance.Tutar), 0)
            ).filter(
                Finance.Tarih >= start_date,
                Finance.Tarih < end_date,
                *check_filters
            ).group_by(func.lower(Finance.IslemTuru)).all()

            inc = 0.0
            exp = 0.0
            for t, s in rows:
                if (t or '').lower() == 'gelir':
                    inc = float(s or 0)
                elif (t or '').lower() == 'gider':
                    exp = float(s or 0)

            monthly_summary.append({
                'label': f"{months_tr[month-1]} {year}",
                'income': inc,
                'expense': exp,
                'net': inc - exp
            })

        category_rows = db.session.query(
            Finance.Kategori,
            func.lower(Finance.IslemTuru),
            func.coalesce(func.sum(Finance.Tutar), 0)
        ).filter(*check_filters).group_by(Finance.Kategori, func.lower(Finance.IslemTuru)).all()

        category_summary = {}
        for cat, typ, s in category_rows:
            key = cat or 'Diğer'
            if key not in category_summary:
                category_summary[key] = {'name': key, 'income': 0.0, 'expense': 0.0}
            if (typ or '').lower() == 'gelir':
                category_summary[key]['income'] += float(s or 0)
            elif (typ or '').lower() == 'gider':
                category_summary[key]['expense'] += float(s or 0)

        personel_count = Personel.query.count()
        recent_finance = Finance.query.filter(*check_filters).order_by(Finance.Tarih.desc()).limit(5).all()
        return {
            'total_income': total_income,
            'total_expense': total_expense,
            'personel_count': personel_count,
            'recent_finance': recent_finance,
            'current_period': 'Bu Ay',
            'monthly_summary': monthly_summary,
            'category_summary': list(category_summary.values())
        }


    # Personel list + create form
    @app.route('/personel')
    @login_required
    def personel_list():
        try:
            people = Personel.query.filter_by(Aktif=True).order_by(Personel.PersonelID.desc()).all()
            
            # Calculate hourly rate for each person
            company = Company.query.first()
            settings = company.get_settings() if company else {}
            monthly_hours = float(settings.get('monthly_working_hours', 225))
            
            for p in people:
                salary = float(p.NetMaas or 0)
                # Formula: Salary / Monthly Working Hours
                if monthly_hours > 0:
                    p.hourly_rate = salary / monthly_hours
                else:
                    p.hourly_rate = 0.0

            return render_template('personel_list_v2.html', people=people)
        except Exception as e:
            app.logger.exception('Personel list error')
            return "Error: {}".format(e), 500

    @app.route('/personel/create', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'ik')
    def personel_create():
        if request.method == 'POST':
            try:
                data = request.form
                full_name = (data.get('first_name') or '').strip()
                first_name = ''
                last_name = ''
                if full_name:
                    parts = full_name.split()
                    if len(parts) == 1:
                        first_name = parts[0]
                        last_name = parts[0]
                    else:
                        first_name = ' '.join(parts[:-1])
                        last_name = parts[-1]
                hire_date = None
                if data.get('hire_date'):
                    hire_date = datetime.strptime(data.get('hire_date'), '%Y-%m-%d').date()
                tc_no = (data.get('tc') or '').strip()
                if tc_no == '':
                    tc_no = None
                
                if tc_no:
                    # TC benzersizlik kontrolü
                    existing = Personel.query.filter_by(TC=tc_no).first()
                    if existing:
                        flash(f'Hata: {tc_no} TC numaralı bir personel zaten kayıtlı ({existing.Ad} {existing.Soyad}).', 'danger')
                        return render_template('personel_form.html', person=None, documents=[])

                p = Personel(
                    Ad=first_name,
                    Soyad=last_name,
                    TC=tc_no,
                    Telefon=data.get('phone'),
                    Email=data.get('email'),
                    Departman=data.get('department'),
                    Unvan=data.get('unvan'),
                    NetMaas=parse_float(data.get('net_salary')),
                    IsGirisTarihi=hire_date,
                    Aktif=True if data.get('aktif') == 'on' else False
                )
                db.session.add(p)
                db.session.commit()
                log_action("Ekleme", "Personel", f"{p.Ad} {p.Soyad} personeli eklendi.")
                
                # Handle file uploads if any
                if 'files[]' in request.files:
                    files = request.files.getlist('files[]')
                    descriptions = request.form.getlist('descriptions[]')
                    
                    for idx, file in enumerate(files):
                        if file and file.filename:
                            try:
                                filename = secure_filename(file.filename)
                                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                                save_dir = Path(config.UPLOADS_DIR) / 'Personel'
                                save_dir.mkdir(parents=True, exist_ok=True)
                                file_path = save_dir / unique_filename
                                file.save(str(file_path))
                                
                                doc = Document(
                                    DosyaYolu=f"Personel/{unique_filename}",
                                    DosyaAdi=filename,
                                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else None,
                                    Aciklama=descriptions[idx] if idx < len(descriptions) else '',
                                    RelationType='Personel',
                                    RelationID=p.PersonelID
                                )
                                db.session.add(doc)
                            except Exception as e:
                                app.logger.error(f"File upload error during personnel creation: {e}")
                    
                    db.session.commit()
                
                flash('Personel kaydedildi.', 'success')
                return redirect(url_for('personel_list'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Create personel error')
                flash('Hata: {}'.format(e), 'danger')
        return render_template('personel_form.html', person=None, documents=[])

    @app.route('/personel/<int:pid>/edit', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'ik')
    def personel_edit(pid):
        p = Personel.query.get_or_404(pid)
        if request.method == 'POST':
            try:
                data = request.form
                full_name = (data.get('first_name') or '').strip()
                if full_name:
                    parts = full_name.split()
                    if len(parts) == 1:
                        p.Ad = parts[0]
                        p.Soyad = parts[0]
                    else:
                        p.Ad = ' '.join(parts[:-1])
                        p.Soyad = parts[-1]
                tc_no = (data.get('tc') or '').strip()
                if tc_no == '':
                    tc_no = None
                
                if tc_no and tc_no != p.TC:
                    # TC benzersizlik kontrolü
                    existing = Personel.query.filter_by(TC=tc_no).first()
                    if existing:
                        flash(f'Hata: {tc_no} TC numaralı başka bir personel zaten kayıtlı ({existing.Ad} {existing.Soyad}).', 'danger')
                        return render_template('personel_form.html', person=p, documents=[])
                
                p.TC = tc_no
                p.Telefon = data.get('phone')
                p.Email = data.get('email')
                p.Departman = data.get('department')
                p.Unvan = data.get('unvan')
                p.NetMaas = parse_float(data.get('net_salary'))
                p.Aktif = True if data.get('aktif') == 'on' else False
                if data.get('hire_date'):
                    p.IsGirisTarihi = datetime.strptime(data.get('hire_date'), '%Y-%m-%d').date()
                db.session.commit()
                log_action("Güncelleme", "Personel", f"{p.Ad} {p.Soyad} personeli güncellendi.")
                flash('Güncellendi.', 'success')
                return redirect(url_for('personel_list'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Edit personel error')
                flash('Hata: {}'.format(e), 'danger')
        
        # Belgeleri de getir
        docs = Document.query.filter_by(RelationType='Personel', RelationID=pid).all()
        return render_template('personel_form.html', person=p, documents=docs)

    @app.route('/personel/<int:pid>/delete', methods=['POST'])
    @login_required
    def personel_delete(pid):
        try:
            p = Personel.query.get_or_404(pid)
            p.Aktif = False  # Soft delete
            db.session.commit()
            log_action("Arşivleme", "Personel", f"{p.Ad} {p.Soyad} personeli arşivlendi.")
            flash('Personel arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Delete personel error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('personel_list'))

    @app.route('/puantaj', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'ik')
    def puantaj():
        try:
            if request.method == 'POST':
                date_str = request.form.get('date')
            else:
                date_str = request.args.get('date')

            if date_str:
                try:
                    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    selected_date = date.today()
            else:
                selected_date = date.today()

            date_str = selected_date.strftime('%Y-%m-%d')
            prev_date = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
            next_date = (selected_date + timedelta(days=1)).strftime('%Y-%m-%d')

            people = Personel.query.order_by(Personel.PersonelID.asc()).all()

            if request.method == 'POST':
                company = Company.query.first()
                settings = company.get_settings() if company else {}
                mesai_states = settings.get('mesai_states', {}) if settings else {}
                period_key = f"{selected_date.year:04d}-{selected_date.month:02d}"
                mesai_state = mesai_states.get(period_key, 'open')
                if mesai_state == 'locked':
                    flash('Bu ay için mesai kayıtları kilitlenmiş. Değişiklik yapılamaz.', 'warning')
                    return redirect(url_for('puantaj', date=date_str))

                for p in people:
                    status_key = f'durum_{p.PersonelID}'
                    overtime_key = f'mesai_{p.PersonelID}'
                    
                    # Eğer bu personel form verisinde yoksa (filtreleme vb. nedeniyle) atla
                    if status_key not in request.form and overtime_key not in request.form:
                        continue
                    
                    missing_hours_key = f'eksik_saat_{p.PersonelID}'
                    deduction_type_key = f'kesinti_turu_{p.PersonelID}'
                    
                    durum = request.form.get(status_key)
                    mesai_raw = request.form.get(overtime_key) or '0'
                    eksik_saat_raw = request.form.get(missing_hours_key) or '0'
                    kesinti_turu = request.form.get(deduction_type_key) or 'Maaş'
                    carpan_key = f'carpan_{p.PersonelID}'
                    carpan_raw = request.form.get(carpan_key)

                    try:
                        mesai = float(mesai_raw.replace(',', '.'))
                        eksik_saat = float(eksik_saat_raw.replace(',', '.'))
                        if carpan_raw:
                            carpan = float(carpan_raw.replace(',', '.'))
                        else:
                            # Hesapla varsayılan çarpanı
                            days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                            day_name = days_map[selected_date.weekday()]
                            day_config = settings.get('weekly_schedule', {}).get(day_name, {})
                            is_public_holiday = any(holiday['date'] == selected_date.strftime('%Y-%m-%d') for holiday in settings.get('public_holidays', []))
                            
                            if is_public_holiday:
                                default_mult = float(next((h['multiplier'] for h in settings.get('public_holidays', []) if h['date'] == selected_date.strftime('%Y-%m-%d')), 2.0))
                            elif day_name in ['saturday', 'sunday']:
                                default_mult = 2.0
                            else:
                                default_mult = 1.5
                            carpan = float(day_config.get('multiplier', default_mult))
                    except ValueError:
                        mesai = 0.0
                        eksik_saat = 0.0
                        carpan = 1.5

                    record = Puantaj.query.filter_by(PersonelID=p.PersonelID, Tarih=selected_date).first()
                    if not record:
                        record = Puantaj(PersonelID=p.PersonelID, Tarih=selected_date)
                        db.session.add(record)

                    record.Durum = durum or 'Geldi'
                    record.MesaiSaati = mesai
                    record.EksikSaat = eksik_saat
                    record.KesintiTuru = kesinti_turu
                    record.Carpan = carpan

                db.session.commit()
                flash('Puantaj kaydedildi.', 'success')
                return redirect(url_for('puantaj', date=date_str))

            records = Puantaj.query.filter_by(Tarih=selected_date).all()
            by_person = {r.PersonelID: r for r in records}

            company = Company.query.first()
            settings = company.get_settings() if company else {}
            weekly_schedule = settings.get('weekly_schedule', {})

            rows = []
            for p in people:
                r = by_person.get(p.PersonelID)
                durum = r.Durum if r else 'Geldi'
                mesai = float(r.MesaiSaati) if r else 0.0
                eksik_saat = float(r.EksikSaat) if r else 0.0
                kesinti_turu = r.KesintiTuru if r else 'Maaş'
                
                # Çarpan hesaplama
                days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_name = days_map[selected_date.weekday()]
                day_config = weekly_schedule.get(day_name, {})
                is_public_holiday = any(holiday['date'] == selected_date.strftime('%Y-%m-%d') for holiday in settings.get('public_holidays', []))
                
                if is_public_holiday:
                    setting_mult = float(next((h['multiplier'] for h in settings.get('public_holidays', []) if h['date'] == selected_date.strftime('%Y-%m-%d')), 2.0))
                else:
                    d_mult = 2.0 if day_name in ['saturday', 'sunday'] else 1.5
                    setting_mult = float(day_config.get('multiplier', d_mult))

                if r:
                    carpan = services.resolve_multiplier(r.Carpan, setting_mult)
                else:
                    carpan = setting_mult

                rows.append({
                    'personel': p,
                    'durum': durum,
                    'mesai': mesai,
                    'eksik_saat': eksik_saat,
                    'kesinti_turu': kesinti_turu,
                    'carpan': carpan
                })

            mevcut_count = sum(1 for row in rows if (row['durum'] or '').lower() == 'geldi')
            izinli_count = sum(1 for row in rows if (row['durum'] or '').lower() == 'izinli')
            raporlu_count = sum(1 for row in rows if (row['durum'] or '').lower() == 'raporlu')
            total_overtime = sum(row['mesai'] or 0 for row in rows)

            company = Company.query.first()
            company_name = company.SirketAdi if company else 'ERP Şirketi'
            settings = company.get_settings() if company else {}
            
            # Holiday check for the selected date
            public_holidays = settings.get('public_holidays', [])
            current_holiday = next((h for h in public_holidays if h['date'] == selected_date.strftime('%Y-%m-%d')), None)

            # Calculate daily scheduled hours for the selected date
            def get_daily_hours(date_obj, settings):
                days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_name = days_map[date_obj.weekday()]
                schedule = settings.get('weekly_schedule', {}).get(day_name, {})
                if not schedule or not schedule.get('active'): return 0.0
                s = schedule.get('start', '08:30')
                e = schedule.get('end', '18:00')
                b = float(schedule.get('break') if schedule.get('break') is not None else (90 if day_name != 'saturday' else 30))
                try:
                    sh, sm = map(int, s.split(':'))
                    eh, em = map(int, e.split(':'))
                    diff = (eh * 60 + em) - (sh * 60 + sm)
                    return max(0, (diff - b) / 60.0)
                except: return 0.0
            
            daily_scheduled_hours = get_daily_hours(selected_date, settings)

            return render_template(
                'puantaj.html',
                rows=rows,
                selected_date=date_str,
                selected_date_label=selected_date.strftime('%d.%m.%Y'),
                prev_date=prev_date,
                next_date=next_date,
                personel_count=len(rows),
                mevcut_count=mevcut_count,
                izinli_count=izinli_count,
                raporlu_count=raporlu_count,
                total_overtime=total_overtime,
                company_name=company_name,
                settings=settings,
                selected_date_obj=selected_date,
                current_holiday=current_holiday,
                daily_scheduled_hours=daily_scheduled_hours
            )
        except Exception as e:
            app.logger.exception('Puantaj error')
            return "Error: {}".format(e), 500

    # Finance list sayfası kaldırıldı, eski linkler dashboarda yönlendiriliyor
    @app.route('/finans')
    @login_required
    def finans_list():
        return redirect(url_for('dashboard'))

    @app.route('/finans/add', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def finans_add():
        if request.method == 'POST':
            try:
                data = request.form
                dt = datetime.strptime(data.get('date'), '%Y-%m-%d').date() if data.get('date') else date.today()
                f = Finance(
                    Tarih=dt,
                    Tutar=float(data.get('amount') or 0),
                    IslemTuru=data.get('type'),
                    Kategori=data.get('category'),
                    Aciklama=data.get('description'),
                    CariID=data.get('cari_id') if data.get('cari_id') else None
                )
                db.session.add(f)
                db.session.commit()
                log_action("Ekleme", "Finans", f"{f.IslemTuru}: {f.Kategori} - {f.Tutar:,.2f} TL")
                
                # Cari bakiyesini güncelle
                if f.CariID:
                    update_cari_balance(f.CariID)
                
                # Handle file uploads if any
                if 'files[]' in request.files:
                    files = request.files.getlist('files[]')
                    descriptions = request.form.getlist('descriptions[]')
                    
                    for idx, file in enumerate(files):
                        if file and file.filename:
                            try:
                                filename = secure_filename(file.filename)
                                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                                save_dir = Path(config.UPLOADS_DIR) / 'Finans'
                                save_dir.mkdir(parents=True, exist_ok=True)
                                file_path = save_dir / unique_filename
                                file.save(str(file_path))
                                
                                doc = Document(
                                    DosyaYolu=f"Finans/{unique_filename}",
                                    DosyaAdi=filename,
                                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else None,
                                    Aciklama=descriptions[idx] if idx < len(descriptions) else '',
                                    RelationType='Finans',
                                    RelationID=f.FinansID
                                )
                                db.session.add(doc)
                            except Exception as e:
                                app.logger.error(f"File upload error during finance creation: {e}")
                    
                    db.session.commit()
                
                flash('İşlem kaydedildi.', 'success')
                
                # Eğer /kasa üzerinden gelindiyse tekrar kasaya dön
                if request.args.get('type'):
                    return redirect(url_for('kasa'))
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Finans add error')
                flash('Hata: {}'.format(e), 'danger')
        
        # URL ile tip geldiyse önceden seç
        pre_type = request.args.get('type')
        cancel_url = url_for('kasa') if pre_type else url_for('dashboard')
        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        return render_template('finans_form.html', pre_type=pre_type, cancel_url=cancel_url, documents=[], cariler=cariler)

    @app.route('/kasa')
    @login_required
    @roles_required('admin', 'muhasebe')
    def kasa():
        try:
            all_entries = Finance.query.filter_by(Aktif=True).order_by(Finance.Tarih.desc(), Finance.FinansID.desc()).all()
            entries = []
            for f in all_entries:
                cat_lower = (f.Kategori or '').lower()
                desc_lower = (f.Aciklama or '').lower()
                islem_lower = (f.IslemTuru or '').lower()

                # Sadece gerçek nakit hareketleri: Gelir / Gider
                if islem_lower not in ('gelir', 'gider'):
                    continue

                # İndirilecek KDV kayıtları sadece KDV hesabında kullanılmalı, kasa hareketi olmamalı
                if 'kdv' in cat_lower and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower)):
                    continue

                if 'çek' in cat_lower or 'çek' in desc_lower:
                    continue
                
                # Banka ID'si olanlar nakit kasa hareketi değildir
                if f.BankaID is not None:
                    continue
                
                if 'banka' in cat_lower or 'banka' in desc_lower:
                    continue
                entries.append(f)
            personnel = Personel.query.order_by(Personel.Ad.asc(), Personel.Soyad.asc()).all()
            
            # Stats
            cash_balance = 0
            today_income = 0
            today_income_count = 0
            today_expense = 0
            today_expense_count = 0
            month_income = 0
            month_expense = 0
            
            today = date.today()
            first_of_month = today.replace(day=1)
            
            for f in entries:
                amount = f.Tutar or 0
                islem = (f.IslemTuru or '').lower()
                
                if islem == 'gelir':
                    cash_balance += amount
                    if f.Tarih == today:
                        today_income += amount
                        today_income_count += 1
                    if f.Tarih and f.Tarih >= first_of_month:
                        month_income += amount
                elif islem == 'gider':
                    cash_balance -= amount
                    if f.Tarih == today:
                        today_expense += amount
                        today_expense_count += 1
                    if f.Tarih and f.Tarih >= first_of_month:
                        month_expense += amount
            
            month_net = month_income - month_expense
            
            cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
            
            return render_template('kasa.html', 
                                 entries=entries,
                                 personnel=personnel,
                                 cariler=cariler,
                                 cash_balance=cash_balance,
                                 today_income=today_income,
                                 today_income_count=today_income_count,
                                 today_expense=today_expense,
                                 today_expense_count=today_expense_count,
                                 month_net=month_net,
                                 today_date=today.strftime('%Y-%m-%d'))
        except Exception as e:
            app.logger.exception('Kasa error')
            return "Error: {}".format(e), 500

    @app.route('/finans/<int:fid>/edit', methods=['GET', 'POST'])
    @login_required
    def finans_edit(fid):
        f = Finance.query.get_or_404(fid)
        if request.method == 'POST':
            try:
                data = request.form
                dt = datetime.strptime(data.get('date'), '%Y-%m-%d').date() if data.get('date') else date.today()
                old_cari_id = f.CariID
                f.Tarih = dt
                f.Tutar = float(data.get('amount') or 0)
                f.IslemTuru = data.get('type')
                f.Kategori = data.get('category')
                f.Aciklama = data.get('description')
                f.CariID = data.get('cari_id') if data.get('cari_id') else None
                
                db.session.commit()
                log_action("Güncelleme", "Finans", f"{f.IslemTuru}: {f.Kategori} - {f.Tutar:,.2f} TL güncellendi.")
                
                # Cari bakiyelerini güncelle (eskisi ve yenisi farklıysa ikisini de güncelle)
                if old_cari_id:
                    update_cari_balance(old_cari_id)
                if f.CariID and f.CariID != old_cari_id:
                    update_cari_balance(f.CariID)

                flash('İşlem güncellendi.', 'success')
                
                # Kaynak sayfaya geri dön
                next_url = request.args.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect(url_for('dashboard'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Finans edit error')
                flash('Hata: {}'.format(e), 'danger')
        
        
        cancel_url = request.args.get('next') or url_for('dashboard')
        docs = Document.query.filter_by(RelationType='Finans', RelationID=fid).all()
        cariler = CariAccount.query.filter_by(Aktif=True).order_by(CariAccount.Unvan.asc()).all()
        return render_template('finans_form.html', entry=f, cancel_url=cancel_url, documents=docs, cariler=cariler)

    @app.route('/cari')
    @login_required
    @roles_required('admin', 'muhasebe')
    def cari_list():
        """Cari hesapları listeler"""
        cari_tipi = request.args.get('tip') # Müşteri veya Tedarikçi
        query = CariAccount.query.filter_by(Aktif=True)
        if cari_tipi:
            query = query.filter(CariAccount.CariTipi == cari_tipi)
        
        cariler = query.order_by(CariAccount.Unvan.asc()).all()
        
        # Özet verileri hesapla ve bakiyeleri tazele (Hatalı bakiyeleri düzeltmek için)
        all_caris = CariAccount.query.filter_by(Aktif=True).all()
        for c in all_caris:
            update_cari_balance(c.CariID)
        
        # Güncellenmiş bakiyeleri tekrar çek
        all_caris = CariAccount.query.all()
        total_alacak = sum(c.Bakiye for c in all_caris if (c.Bakiye or 0) > 0)
        total_borc = abs(sum(c.Bakiye for c in all_caris if (c.Bakiye or 0) < 0))
        net_bakiye = sum(c.Bakiye for c in all_caris if c.Bakiye)
        
        # Müşteri çeklerini getir (Ciro için)
        customer_checks = Finance.query.filter(
            Finance.IslemTuru == 'Gelir',
            (
                Finance.Kategori.ilike('%çek%') | Finance.Kategori.ilike('%Çek%') | Finance.Kategori.ilike('%ÇEK%') |
                Finance.Kategori.ilike('%cek%') | Finance.Kategori.ilike('%CEK%') |
                Finance.Aciklama.ilike('%çek%') | Finance.Aciklama.ilike('%Çek%') | Finance.Aciklama.ilike('%ÇEK%') |
                Finance.Aciklama.ilike('%cek%') | Finance.Aciklama.ilike('%CEK%')
            ),
            ~Finance.Aciklama.ilike('%tahsil edildi%'),
            ~Finance.Aciklama.ilike('%tahsi̇l edi̇ldi̇%'),
            ~Finance.Aciklama.ilike('%TAHSİL EDİLDİ%'),
            ~Finance.Aciklama.ilike('%ödendi%'),
            ~Finance.Aciklama.ilike('%odendi%'),
            ~Finance.Aciklama.ilike('%ÖDENDİ%'),
            ~Finance.Aciklama.ilike('%silindi%'),
            ~Finance.Aciklama.ilike('%si̇li̇ndi̇%'),
            ~Finance.Aciklama.ilike('%karşılıksız%'),
            ~Finance.Aciklama.ilike('%karsiliksiz%'),
            ~Finance.Aciklama.ilike('%kendi çeki%'),
            ~Finance.Aciklama.ilike('%kendi ceki%'),
            ~Finance.Aciklama.ilike('%ciro edildi%'),
            ~Finance.Aciklama.ilike('%ci̇ro edi̇ldi̇%')
        ).all()
        
        return render_template('cari_listesi.html', 
                               cariler=cariler, 
                               cari_tipi=cari_tipi,
                               total_alacak=total_alacak,
                               total_borc=total_borc,
                               net_bakiye=net_bakiye,
                               banks=BankAccount.query.all(),
                               customer_checks=customer_checks)

    @app.route('/cari/add_ajax', methods=['POST'])
    @login_required
    def cari_add_ajax():
        """Hızlı cari ekleme (AJAX)"""
        try:
            data = request.get_json()
            unvan = (data.get('Unvan') or '').strip()
            if not unvan:
                return jsonify({'success': False, 'message': 'Ünvan boş olamaz.'}), 400
            
            # Cari tipi varsayılan olarak 'Müşteri' al ama gelmişse onu kullan
            cari_tipi = data.get('CariTipi', 'Müşteri')
            
            cari = CariAccount(
                Unvan=unvan,
                VKN_TCN=data.get('VKN_TCN'),
                CariTipi=cari_tipi,
                Telefon=data.get('Telefon'),
                Email=data.get('Email'),
                Adres=data.get('Adres'),
                Bakiye=0.0
            )
            db.session.add(cari)
            db.session.commit()
            
            # Kayıt başarılı, ID ve Unvan döndür
            return jsonify({
                'success': True,
                'cari_id': cari.CariID,
                'unvan': cari.Unvan
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/cari/<int:cid>/history')
    @login_required
    def cari_history(cid):
        """Cari işlem geçmişi"""
        try:
            cari = CariAccount.query.get_or_404(cid)
            
            # Finans hareketleri
            finances = Finance.query.filter_by(CariID=cid).order_by(Finance.Tarih.desc()).all()
            
            # Alacaklar
            receivables = Receivable.query.filter_by(CariID=cid).order_by(Receivable.VadeTarihi.desc()).all()
            
            # Borçlar
            debts = Debt.query.filter_by(CariID=cid).order_by(Debt.VadeTarihi.desc()).all()
            
            # Tüm hareketleri birleştirip tarihe göre sıralayalım
            all_actions = []
            
            from datetime import date
            
            for f in finances:
                all_actions.append({
                    'tarih': f.Tarih,
                    'islem': f.IslemTuru,
                    'kategori': f.Kategori,
                    'aciklama': f.Aciklama,
                    'tutar': f.Tutar,
                    'tip': 'Finans'
                })
                
            for r in receivables:
                all_actions.append({
                    'tarih': r.VadeTarihi,
                    'islem': 'Alacak',
                    'kategori': r.AlacakTuru,
                    'aciklama': r.Baslik,
                    'tutar': r.AnaTutar,
                    'tip': 'Alacak',
                    'durum': r.Durum,
                    'kalan': r.KalanTutar
                })
                
            for d in debts:
                all_actions.append({
                    'tarih': d.VadeTarihi,
                    'islem': 'Borç',
                    'kategori': d.BorcTuru,
                    'aciklama': d.BorcVeren,
                    'tutar': d.AnaTutar,
                    'tip': 'Borç',
                    'durum': d.Durum,
                    'kalan': d.KalanTutar
                })
            
            all_actions.sort(key=lambda x: x['tarih'] or date.min, reverse=True)
            
            return render_template('cari_history.html', cari=cari, actions=all_actions)
        except Exception as e:
            app.logger.exception('Cari history error')
            return "Error: {}".format(e), 500

    @app.route('/cari/<int:cid>/islem', methods=['POST'])
    @login_required
    def cari_islem(cid):
        try:
            cari = CariAccount.query.get_or_404(cid)
            data = request.form
            islem_turu = data.get('islem_turu') # 'Gelir' (Tahsilat) or 'Gider' (Ödeme)
            amount = float(data.get('tutar', '0').replace(',', '.'))
            bank_id = data.get('bank_id')
            payment_method = data.get('payment_method', 'cash')
            aciklama = data.get('aciklama') or f"Cari İşlem: {cari.Unvan}"
            
            if amount <= 0:
                flash('Tutar sıfırdan büyük olmalıdır.', 'danger')
                return redirect(url_for('cari_list'))
            
            check_details = ""
            is_ciro = False
            if payment_method == 'cek':
                check_no = data.get('check_no')
                due_date = data.get('check_due_date')
                check_source = data.get('check_source', 'own')
                customer_check_id = data.get('customer_check_id')
                
                parts = []
                if check_no: parts.append(f"No:{check_no}")
                if due_date: parts.append(f"Vade:{due_date}")
                
                if islem_turu == 'Gider' and check_source == 'customer' and customer_check_id:
                    # Ciro işlemi
                    is_ciro = True
                    orig_check = Finance.query.get(customer_check_id)
                    if orig_check:
                        # Kategoriyi 'verildi' yap ki portföyden düşüp 'Müşteride' (customer) grubuna girsin
                        orig_check.Kategori = "Müşteri Çeki (Verildi)"
                        orig_check.Aciklama = (orig_check.Aciklama or "") + f" - {cari.Unvan} hesabına ciro edildi."
                        parts.append("Müşteri Çeki (Ciro)")
                elif islem_turu == 'Gider':
                    parts.append("Kendi Çekimiz")
                
                if parts:
                    check_details = " (" + ", ".join(parts) + ")"
                
                # Ciro ise 'Çek' kelimesini başa koymayalım ki 'Ödenecek Çekler' listesine (Gider olarak) girmesin
                prefix = "Ciro" if is_ciro else "Çek"
                aciklama = f"{prefix} - {aciklama}{check_details}"
            
            from models import BankAccount
            
            kategori = 'Cari Tahsilat' if islem_turu == 'Gelir' else 'Cari Ödeme'
            if payment_method == 'cek':
                kategori = 'Ciro İşlemi' if is_ciro else 'Çek'
                
            f = Finance(
                Tarih=date.today(),
                Tutar=amount,
                IslemTuru=islem_turu,
                Kategori=kategori,
                Aciklama=aciklama,
                CariID=cid,
                BankaID=int(bank_id) if bank_id and bank_id.strip() and payment_method == 'bank' else None
            )
            db.session.add(f)
            
            if f.BankaID:
                bank = BankAccount.query.get(f.BankaID)
                if bank:
                    if islem_turu == 'Gelir':
                        bank.Bakiye += amount
                    else:
                        bank.Bakiye -= amount
            
            db.session.commit()
            update_cari_balance(cid)
            
            label = "Tahsilat" if islem_turu == 'Gelir' else "Ödeme"
            log_action("İşlem", "Cari", f"{cari.Unvan} hesabına {amount:,.2f} TL {label} yapıldı.")
            flash(f'{label} işlemi başarıyla kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cari islem error')
            flash(f'Hata: {e}', 'danger')
        return redirect(url_for('cari_list'))

    @app.route('/cari/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def cari_ekle():
        """Yeni cari hesap ekler"""
        if request.method == 'POST':
            try:
                data = request.form
                yeni_cari = CariAccount(
                    Unvan=data.get('unvan'),
                    CariTipi=data.get('cari_tipi'),
                    VergiDairesi=data.get('vergi_dairesi'),
                    VergiNo=data.get('vergi_no'),
                    Telefon=data.get('phone'),
                    Email=data.get('email'),
                    Adres=data.get('address')
                )
                db.session.add(yeni_cari)
                db.session.commit()
                log_action("Ekleme", "Cari", f"{yeni_cari.Unvan} carisi eklendi.")
                flash('Cari hesap başarıyla eklendi.', 'success')
                return redirect(url_for('cari_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
        
        return render_template('cari_form.html', cari=None)

    @app.route('/cari/<int:cid>/duzenle', methods=['GET', 'POST'])
    @login_required
    def cari_duzenle(cid):
        """Cari hesabı düzenler"""
        cari = CariAccount.query.get_or_404(cid)
        if request.method == 'POST':
            try:
                data = request.form
                cari.Unvan = data.get('unvan')
                cari.CariTipi = data.get('cari_tipi')
                cari.VergiDairesi = data.get('vergi_dairesi')
                cari.VergiNo = data.get('vergi_no')
                cari.Telefon = data.get('phone')
                cari.Email = data.get('email')
                cari.Adres = data.get('address')
                
                db.session.commit()
                log_action("Güncelleme", "Cari", f"{cari.Unvan} carisi güncellendi.")
                flash('Cari hesap güncellendi.', 'success')
                return redirect(url_for('cari_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
                
        return render_template('cari_form.html', cari=cari)

    @app.route('/cari/<int:cid>/ekstre')
    @login_required
    def cari_ekstre(cid):
        """Cari hesap ekstresini görüntüler"""
        cari = CariAccount.query.get_or_404(cid)
        # Cari ile ilgili tüm finans hareketlerini çek
        hareketler = Finance.query.filter(Finance.CariID == cid).order_by(Finance.Tarih.desc()).all()
        return render_template('cari_ekstre.html', cari=cari, hareketler=hareketler)

    @app.route('/cari/<int:cid>/sil', methods=['POST'])
    @login_required
    def cari_sil(cid):
        """Cari hesabı arşivler"""
        if session.get('user_role') != 'admin':
            flash('Bu işlem için yetkiniz yok.', 'danger')
            return redirect(url_for('cari_list'))
            
        cari = CariAccount.query.get_or_404(cid)
        try:
            unvan = cari.Unvan
            cari.Aktif = False # Soft delete
            db.session.commit()
            log_action("Arşivleme", "Cari", f"{unvan} carisi arşivlendi.")
            flash(f'{unvan} başarıyla arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cari delete error')
            flash(f'Hata: {str(e)}', 'danger')
            
        return redirect(url_for('cari_list'))

    # === STOK VE ENVANTER YÖNETİMİ ===
    @app.route('/urunler')
    @login_required
    @roles_required('admin', 'depo', 'muhasebe')
    def urun_listesi():
        """Ürün listesini görüntüler"""
        search = request.args.get('search', '')
        query = Urun.query.filter_by(Aktif=True)
        if search:
            query = query.filter(Urun.UrunAdi.ilike(f"%{search}%") | Urun.Barkod.ilike(f"%{search}%"))
        
        urunler = query.order_by(Urun.UrunAdi.asc()).all()
        return render_template('stok_listesi.html', urunler=urunler, search=search)

    @app.route('/urun/ekle', methods=['GET', 'POST'])
    @login_required
    def urun_ekle():
        """Yeni ürün ekler"""
        if request.method == 'POST':
            try:
                u = Urun(
                    UrunAdi=request.form.get('urun_adi'),
                    Birim=request.form.get('birim', 'Adet'),
                    KritikStok=parse_float(request.form.get('kritik_stok')),
                    SatisFiyati=parse_float(request.form.get('satis_fiyati')),
                    AlisFiyati=parse_float(request.form.get('alis_fiyati')),
                    KDV=int(request.form.get('kdv', 20)),
                    Barkod=request.form.get('barkod'),
                    StokMiktari=0.0
                )
                db.session.add(u)
                db.session.commit()
                log_action("Ekleme", "Stok", f"{u.UrunAdi} ürünü eklendi.")
                flash('Ürün başarıyla eklendi.', 'success')
                return redirect(url_for('urun_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
        
        return render_template('urun_form.html')

    @app.route('/urun/<int:uid>/duzenle', methods=['GET', 'POST'])
    @login_required
    def urun_duzenle(uid):
        """Ürün bilgilerini günceller"""
        u = Urun.query.get_or_404(uid)
        if request.method == 'POST':
            try:
                u.UrunAdi = request.form.get('urun_adi')
                u.Birim = request.form.get('birim')
                u.KritikStok = parse_float(request.form.get('kritik_stok'))
                u.SatisFiyati = parse_float(request.form.get('satis_fiyati'))
                u.AlisFiyati = parse_float(request.form.get('alis_fiyati'))
                u.KDV = int(request.form.get('kdv'))
                u.Barkod = request.form.get('barkod')
                
                db.session.commit()
                log_action("Güncelleme", "Stok", f"{u.UrunAdi} ürünü güncellendi.")
                flash('Ürün bilgileri güncellendi.', 'success')
                return redirect(url_for('urun_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
        
        return render_template('urun_form.html', urun=u)

    @app.route('/urun/<int:uid>/sil', methods=['POST'])
    @login_required
    def urun_sil(uid):
        """Ürünü arşivler"""
        if session.get('user_role') != 'admin':
            flash('Admin yetkisi gereklidir.', 'danger')
            return redirect(url_for('urun_listesi'))
            
        u = Urun.query.get_or_404(uid)
        try:
            name = u.UrunAdi
            u.Aktif = False # Soft delete
            db.session.commit()
            log_action("Arşivleme", "Stok", f"{name} ürünü arşivlendi.")
            flash(f'{name} arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
        return redirect(url_for('urun_listesi'))

    # === RECYCLE BIN ===
    @app.route('/arsiv')
    @login_required
    @roles_required('admin')
    def recycle_bin():
        """Geri dönüşüm kutusu"""
        deleted_items = {
            'personel': Personel.query.filter_by(Aktif=False).all(),
            'cari': CariAccount.query.filter_by(Aktif=False).all(),
            'urun': Urun.query.filter_by(Aktif=False).all(),
            'finans': Finance.query.filter_by(Aktif=False).order_by(Finance.Tarih.desc()).all()
        }
        return render_template('recycle_bin.html', deleted_items=deleted_items)
    
    @app.route('/restore/<item_type>/<int:item_id>', methods=['POST'])
    @login_required
    @roles_required('admin')
    def restore_item(item_type, item_id):
        try:
            msg = ""
            if item_type == 'personel':
                item = Personel.query.get_or_404(item_id)
                item.Aktif = True
                msg = f"{item.Ad} {item.Soyad} geri yüklendi."
            elif item_type == 'cari':
                item = CariAccount.query.get_or_404(item_id)
                item.Aktif = True
                msg = f"{item.Unvan} geri yüklendi."
            elif item_type == 'urun':
                item = Urun.query.get_or_404(item_id)
                item.Aktif = True
                msg = f"{item.UrunAdi} geri yüklendi."
            elif item_type == 'finans':
                item = Finance.query.get_or_404(item_id)
                item.Aktif = True
                db.session.commit() # Commit first to ensure item is active before recalc ranges
                
                if item.BankaID:
                    update_bank_balance(item.BankaID)

                if item.CariID:
                    update_cari_balance(item.CariID)
                    
                msg = "Finansal işlem geri yüklendi."
            
            db.session.commit()
            log_action("Geri Yükleme", "Arşiv", msg)
            flash(msg, 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Geri yükleme hatası: {e}", 'danger')
        
        return redirect(url_for('recycle_bin'))

    @app.route('/stok/hareket', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'depo', 'muhasebe')
    def stok_hareket():
        """Manuel stok girişi veya çıkışı yapar"""
        if request.method == 'POST':
            try:
                uid = request.form.get('urun_id')
                tur = request.form.get('hareket_turu') # 'Giriş' or 'Çıkış'
                miktar = parse_float(request.form.get('miktar'))
                fiyat = parse_float(request.form.get('birim_fiyat'))
                cari_id = request.form.get('cari_id') or None
                aciklama = request.form.get('aciklama')
                
                u = Urun.query.get(uid)
                if not u:
                    flash('Ürün bulunamadı.', 'danger')
                    return redirect(url_for('urun_listesi'))
                
                hareket = StokHareketi(
                    UrunID=uid,
                    HareketTuru=tur,
                    Miktar=miktar,
                    BirimFiyat=fiyat,
                    CariID=int(cari_id) if cari_id else None,
                    Aciklama=aciklama
                )
                
                # Stok miktarını güncelle
                if tur == 'Giriş':
                    u.StokMiktari += miktar
                else:
                    u.StokMiktari -= miktar
                
                db.session.add(hareket)
                
                # Cari Entegrasyonu: Giriş ise BORÇ (Tedarikçiye), Çıkış ise ALACAK (Müşteriden)
                if cari_id:
                    total_price = miktar * fiyat
                    if tur == 'Giriş':
                        d = Debt(
                            CariID=int(cari_id),
                            AnaTutar=total_price,
                            VadeTarihi=date.today(),
                            Aciklama=f"Stok Girişi: {u.UrunAdi} ({miktar} {u.Birim})"
                        )
                        db.session.add(d)
                    else:
                        r = Receivable(
                            CariID=int(cari_id),
                            AnaTutar=total_price,
                            VadeTarihi=date.today(),
                            Aciklama=f"Stok Çıkışı: {u.UrunAdi} ({miktar} {u.Birim})"
                        )
                        db.session.add(r)
                
                db.session.commit()
                
                if cari_id:
                    update_cari_balance(int(cari_id))

                log_action("İşlem", "Stok", f"{u.UrunAdi}: {miktar} {u.Birim} {tur} yapıldı.")
                flash('Stok hareketi ve cari kayıt başarıyla kaydedildi.', 'success')
                return redirect(url_for('urun_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
        
        urunler = Urun.query.order_by(Urun.UrunAdi.asc()).all()
        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        return render_template('stok_hareket_form.html', urunler=urunler, cariler=cariler)

    @app.route('/stok/hareketler')
    @login_required
    @roles_required('admin', 'depo', 'muhasebe')
    def stok_hareketleri_listesi():
        """Tüm stok hareketlerini listeler"""
        try:
            hareketler = StokHareketi.query.order_by(StokHareketi.Tarih.desc()).all()
            return render_template('stok_hareketleri.html', hareketler=hareketler)
        except Exception as e:
            app.logger.exception("Stok hareket listesi hatası")
            return f"Hata: {str(e)}", 500

    # === SATIŞ VE SATIN ALMA (FATURA) ===
    @app.route('/faturalar')
    @login_required
    @roles_required('admin', 'muhasebe')
    def fatura_listesi():
        """Faturaları listeler"""
        tip = request.args.get('tip') # 'Alış' or 'Satış'
        query = Fatura.query.filter_by(Aktif=True)
        if tip:
            query = query.filter(Fatura.FaturaTuru == tip)
        
        faturalar = query.order_by(Fatura.Tarih.desc()).all()
        return render_template('fatura_listesi.html', faturalar=faturalar, tip=tip)

    @app.route('/fatura/<int:fid>')
    @login_required
    def fatura_detay(fid):
        """Fatura detaylarını görüntüler"""
        f = Fatura.query.get_or_404(fid)
        return render_template('fatura_detay.html', fatura=f)

    @app.route('/fatura/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def fatura_ekle():
        """Yeni fatura oluşturur"""
        if request.method == 'POST':
            try:
                # Ana fatura bilgileri
                f_turu = request.form.get('fatura_turu') # 'Alış' or 'Satış'
                f_no = request.form.get('fatura_no')
                cari_id = request.form.get('cari_id')
                tarih_str = request.form.get('tarih')
                f_tarih = datetime.strptime(tarih_str, '%Y-%m-%d') if tarih_str else datetime.utcnow()
                aciklama = request.form.get('aciklama')

                # Kalemleri al (Dinamik formdan gelecek)
                u_ids = request.form.getlist('urun_id[]')
                miktarlar = request.form.getlist('miktar[]')
                fiyatlar = request.form.getlist('birim_fiyat[]')
                kdvler = request.form.getlist('kdv[]')
                seriler = request.form.getlist('seri_no[]')

                if not u_ids:
                    flash('En az bir ürün eklemelisiniz.', 'warning')
                    return redirect(url_for('fatura_ekle'))

                fatura = Fatura(
                    FaturaNo=f_no,
                    FaturaTuru=f_turu,
                    CariID=int(cari_id),
                    Tarih=f_tarih,
                    Aciklama=aciklama,
                    AraToplam=0,
                    KDVToplam=0,
                    GenelToplam=0
                )
                db.session.add(fatura)
                db.session.flush()

                ara_toplam = 0
                kdv_toplam = 0

                for i in range(len(u_ids)):
                    uid = int(u_ids[i])
                    mik = parse_float(miktarlar[i])
                    fiy = parse_float(fiyatlar[i])
                    kdv_oran = int(kdvler[i])
                    
                    satir_ara = mik * fiy
                    satir_kdv = satir_ara * (kdv_oran / 100)
                    satir_toplam = satir_ara + satir_kdv

                    ara_toplam += satir_ara
                    kdv_toplam += satir_kdv

                    kalem = FaturaKalemi(
                        FaturaID=fatura.FaturaID,
                        UrunID=uid,
                        Miktar=mik,
                        BirimFiyat=fiy,
                        KDVOran=kdv_oran,
                        SatirToplami=satir_toplam,
                        SeriNo=seriler[i] if i < len(seriler) else None
                    )
                    db.session.add(kalem)

                    hareket_turu = 'Giriş' if f_turu == 'Alış' else 'Çıkış'
                    hareket = StokHareketi(
                        UrunID=uid,
                        FaturaID=fatura.FaturaID,
                        HareketTuru=hareket_turu,
                        Miktar=mik,
                        BirimFiyat=fiy,
                        Tarih=f_tarih,
                        CariID=int(cari_id),
                        Aciklama=f"{f_turu} Faturası No: {f_no}",
                        SeriNo=seriler[i] if i < len(seriler) else None
                    )
                    db.session.add(hareket)

                    u = Urun.query.get(uid)
                    if u:
                        if hareket_turu == 'Giriş':
                            u.StokMiktari += mik
                        else:
                            u.StokMiktari -= mik

                fatura.AraToplam = ara_toplam
                fatura.KDVToplam = kdv_toplam
                fatura.GenelToplam = ara_toplam + kdv_toplam

                if f_turu == 'Alış':
                    d = Debt(
                        CariID=int(cari_id),
                        AnaTutar=fatura.GenelToplam,
                        VadeTarihi=f_tarih.date(),
                        Aciklama=f"Alış Faturası: {f_no}"
                    )
                    db.session.add(d)
                else:
                    r = Receivable(
                        CariID=int(cari_id),
                        AnaTutar=fatura.GenelToplam,
                        VadeTarihi=f_tarih.date(),
                        Aciklama=f"Satış Faturası: {f_no}"
                    )
                    db.session.add(r)

                db.session.commit()
                update_cari_balance(int(cari_id))

                log_action("Ekleme", "Fatura", f"{f_no} nolu {f_turu} faturası kaydedildi.")
                flash(f'Fatura başarıyla oluşturuldu. Toplam: {fatura.GenelToplam:,.2f} ₺', 'success')
                return redirect(url_for('fatura_listesi'))

            except Exception as e:
                db.session.rollback()
                flash(f'Fatura kaydedilirken hata oluştu: {str(e)}', 'danger')

        current_no = f"FT-{datetime.now().strftime('%Y%m%d%H%M')}"
        now_date_str = date.today().strftime('%Y-%m-%d')
        urunler = Urun.query.order_by(Urun.UrunAdi.asc()).all()
        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        return render_template('fatura_form.html', urunler=urunler, cariler=cariler, current_no=current_no, now_date_str=now_date_str)

    # === TEKLİF YÖNETİMİ ===
    @app.route('/teklifler')
    @login_required
    @roles_required('admin', 'muhasebe')
    def teklif_listesi():
        """Teklifleri listeler"""
        tip = request.args.get('tip') # 'Alış' or 'Satış'
        query = Teklif.query.filter_by(Aktif=True)
        if tip:
            query = query.filter(Teklif.TeklifTuru == tip)
        teklifler = query.order_by(Teklif.Tarih.desc()).all()
        return render_template('teklif_listesi.html', teklifler=teklifler, tip=tip)

    @app.route('/teklif/<int:tid>')
    @login_required
    def teklif_detay(tid):
        """Teklif detaylarını görüntüler"""
        t = Teklif.query.get_or_404(tid)
        return render_template('teklif_detay.html', teklif=t)

    @app.route('/teklif/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def teklif_ekle():
        """Yeni teklif oluşturur"""
        if request.method == 'POST':
            try:
                t_turu = request.form.get('teklif_turu')
                t_no = request.form.get('teklif_no')
                cari_id = request.form.get('cari_id')
                tarih_str = request.form.get('tarih')
                gecerlilik_str = request.form.get('gecerlilik_tarihi')
                t_tarih = datetime.strptime(tarih_str, '%Y-%m-%d') if tarih_str else datetime.utcnow()
                g_tarih = datetime.strptime(gecerlilik_str, '%Y-%m-%d') if gecerlilik_str else None
                aciklama = request.form.get('aciklama')
                u_ids = request.form.getlist('urun_id[]')
                miktarlar = request.form.getlist('miktar[]')
                fiyatlar = request.form.getlist('birim_fiyat[]')
                kdvler = request.form.getlist('kdv[]')
                seriler = request.form.getlist('seri_no[]')


                teklif = Teklif(
                    TeklifNo=t_no,
                    TeklifTuru=t_turu,
                    CariID=int(cari_id),
                    Tarih=t_tarih,
                    GecerlilikTarihi=g_tarih,
                    Aciklama=aciklama
                )
                db.session.add(teklif)
                db.session.flush()

                ara_toplam = 0
                kdv_toplam = 0

                for i in range(len(u_ids)):
                    uid = int(u_ids[i])
                    mik = parse_float(miktarlar[i])
                    fiy = parse_float(fiyatlar[i])
                    kdv_oran = int(kdvler[i])
                    satir_ara = mik * fiy
                    satir_kdv = satir_ara * (kdv_oran / 100)
                    satir_toplam = satir_ara + satir_kdv
                    ara_toplam += satir_ara
                    kdv_toplam += satir_kdv

                    kalem = TeklifKalemi(
                        TeklifID=teklif.TeklifID,
                        UrunID=uid,
                        Miktar=mik,
                        BirimFiyat=fiy,
                        KDVOran=kdv_oran,
                        SatirToplami=satir_toplam,
                        SeriNo=seriler[i] if i < len(seriler) else None
                    )
                    db.session.add(kalem)

                teklif.AraToplam = ara_toplam
                teklif.KDVToplam = kdv_toplam
                teklif.GenelToplam = ara_toplam + kdv_toplam
                db.session.commit()

                log_action("Ekleme", "Teklif", f"{t_no} nolu {t_turu} teklifi oluşturuldu.")
                flash('Teklif başarıyla oluşturuldu.', 'success')
                return redirect(url_for('teklif_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        current_no = f"TK-{datetime.now().strftime('%Y%m%d%H%M')}"
        now_date_str = date.today().strftime('%Y-%m-%d')
        plus_7_days = (date.today() + timedelta(days=7)).strftime('%Y-%m-%d')
        urunler = Urun.query.order_by(Urun.UrunAdi.asc()).all()
        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        return render_template('teklif_form.html', urunler=urunler, cariler=cariler, current_no=current_no, now_date_str=now_date_str, gecerlilik_default=plus_7_days)

    # === SİPARİŞ YÖNETİMİ ===
    @app.route('/siparisler')
    @login_required
    @roles_required('admin', 'muhasebe')
    def siparis_listesi():
        """Siparişleri listeler"""
        tip = request.args.get('tip') # 'Alış' or 'Satış'
        query = Siparis.query.filter_by(Aktif=True)
        if tip:
            query = query.filter(Siparis.SiparisTuru == tip)
        siparisler = query.order_by(Siparis.Tarih.desc()).all()
        return render_template('siparis_listesi.html', siparisler=siparisler, tip=tip)

    @app.route('/siparis/<int:sid>')
    @login_required
    def siparis_detay(sid):
        """Sipariş detaylarını görüntüler"""
        s = Siparis.query.get_or_404(sid)
        return render_template('siparis_detay.html', siparis=s)

    @app.route('/siparis/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def siparis_ekle():
        """Yeni sipariş oluşturur"""
        if request.method == 'POST':
            try:
                s_turu = request.form.get('siparis_turu')
                s_no = request.form.get('siparis_no')
                cari_id = request.form.get('cari_id')
                tarih_str = request.form.get('tarih')
                teslim_str = request.form.get('teslim_tarihi')
                s_tarih = datetime.strptime(tarih_str, '%Y-%m-%d') if tarih_str else datetime.utcnow()
                t_tarih = datetime.strptime(teslim_str, '%Y-%m-%d') if teslim_str else None
                aciklama = request.form.get('aciklama')
                u_ids = request.form.getlist('urun_id[]')
                miktarlar = request.form.getlist('miktar[]')
                fiyatlar = request.form.getlist('birim_fiyat[]')
                kdvler = request.form.getlist('kdv[]')
                seriler = request.form.getlist('seri_no[]')


                siparis = Siparis(
                    SiparisNo=s_no,
                    SiparisTuru=s_turu,
                    CariID=int(cari_id),
                    Tarih=s_tarih,
                    TeslimTarihi=t_tarih,
                    Aciklama=aciklama
                )
                db.session.add(siparis)
                db.session.flush()

                ara_toplam = 0
                kdv_toplam = 0

                for i in range(len(u_ids)):
                    uid = int(u_ids[i])
                    mik = parse_float(miktarlar[i])
                    fiy = parse_float(fiyatlar[i])
                    kdv_oran = int(kdvler[i])
                    satir_ara = mik * fiy
                    satir_kdv = satir_ara * (kdv_oran / 100)
                    satir_toplam = satir_ara + satir_kdv
                    ara_toplam += satir_ara
                    kdv_toplam += satir_kdv

                    kalem = SiparisKalemi(
                        SiparisID=siparis.SiparisID,
                        UrunID=uid,
                        Miktar=mik,
                        BirimFiyat=fiy,
                        KDVOran=kdv_oran,
                        SatirToplami=satir_toplam,
                        SeriNo=seriler[i] if i < len(seriler) else None
                    )
                    db.session.add(kalem)

                siparis.AraToplam = ara_toplam
                siparis.KDVToplam = kdv_toplam
                siparis.GenelToplam = ara_toplam + kdv_toplam
                db.session.commit()

                log_action("Ekleme", "Sipariş", f"{s_no} nolu {s_turu} siparişi oluşturuldu.")
                flash('Sipariş başarıyla oluşturuldu.', 'success')
                return redirect(url_for('siparis_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        current_no = f"SP-{datetime.now().strftime('%Y%m%d%H%M')}"
        now_date_str = date.today().strftime('%Y-%m-%d')
        teslim_default = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
        urunler = Urun.query.order_by(Urun.UrunAdi.asc()).all()
        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        return render_template('siparis_form.html', urunler=urunler, cariler=cariler, current_no=current_no, now_date_str=now_date_str, teslim_default=teslim_default)

    @app.route('/siparis/<int:sid>/faturaya-donustur')
    @login_required
    @roles_required('admin', 'muhasebe')
    def siparis_faturaya_donustur(sid):
        """Siparişi faturaya dönüştürür ve stok hareketlerini oluşturur"""
        try:
            s = Siparis.query.get_or_404(sid)
            if s.Durum == 'Faturaya Dönüştü':
                flash('Bu sipariş zaten faturalandırılmış.', 'warning')
                return redirect(url_for('siparis_detay', sid=sid))

            # Faturayı oluştur
            f_no = f"FT-{datetime.now().strftime('%Y%m%d%H%M')}"
            fatura = Fatura(
                FaturaNo=f_no,
                FaturaTuru=s.SiparisTuru,
                CariID=s.CariID,
                Tarih=datetime.utcnow(),
                Aciklama=f"Siparişten Dönüştürüldü ({s.SiparisNo})",
                AraToplam=s.AraToplam,
                KDVToplam=s.KDVToplam,
                GenelToplam=s.GenelToplam
            )
            db.session.add(fatura)
            db.session.flush()

            # Kalemleri ve stok hareketlerini oluştur
            for sk in s.Kalemler:
                fk = FaturaKalemi(
                    FaturaID=fatura.FaturaID,
                    UrunID=sk.UrunID,
                    Miktar=sk.Miktar,
                    BirimFiyat=sk.BirimFiyat,
                    KDVOran=sk.KDVOran,
                    SatirToplami=sk.SatirToplami,
                    SeriNo=sk.SeriNo
                )
                db.session.add(fk)

                # Stok hareketi
                h_turu = 'Giriş' if s.SiparisTuru == 'Alış' else 'Çıkış'
                hareket = StokHareketi(
                    UrunID=sk.UrunID,
                    FaturaID=fatura.FaturaID,
                    HareketTuru=h_turu,
                    Miktar=sk.Miktar,
                    BirimFiyat=sk.BirimFiyat,
                    Tarih=datetime.utcnow(),
                    CariID=s.CariID,
                    Aciklama=f"Sipariş Faturalama ({s.SiparisNo})",
                    SeriNo=sk.SeriNo
                )
                db.session.add(hareket)

                # Stok güncelleme
                u = Urun.query.get(sk.UrunID)
                if u:
                    if h_turu == 'Giriş':
                        u.StokMiktari += sk.Miktar
                    else:
                        u.StokMiktari -= sk.Miktar

            # Finansal kayıt
            if s.SiparisTuru == 'Alış':
                d = Debt(CariID=s.CariID, AnaTutar=s.GenelToplam, VadeTarihi=date.today(), Aciklama=f"Sipariş Faturası: {f_no}")
                db.session.add(d)
            else:
                r = Receivable(CariID=s.CariID, AnaTutar=s.GenelToplam, VadeTarihi=date.today(), Aciklama=f"Sipariş Faturası: {f_no}")
                db.session.add(r)

            s.Durum = 'Faturaya Dönüştü'
            db.session.commit()
            update_cari_balance(s.CariID)
            
            log_action("İşlem", "Sipariş", f"{s.SiparisNo} nolu sipariş faturaya dönüştürüldü.")
            flash(f'Sipariş başarıyla faturalandırıldı. Fatura No: {f_no}', 'success')
            return redirect(url_for('fatura_detay', fid=fatura.FaturaID))
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Sipariş faturalama hatası")
            flash(f"Hata: {str(e)}", "danger")
            return redirect(url_for('siparis_detay', sid=sid))

    # === ÇEK VE SENET PORTFÖYÜ ===
    @app.route('/portfoy')
    @login_required
    @roles_required('admin', 'muhasebe')
    def portfoy_listesi():
        """Çek ve Senet portföyünü listeler"""
        tur = request.args.get('tur') # 'Çek' or 'Senet'
        query = CekSenet.query
        if tur:
            query = query.filter(CekSenet.EvrakTuru == tur)
        
        cekler = query.order_by(CekSenet.VadeTarihi.asc()).all()
        return render_template('portfoy_listesi.html', cekler=cekler, tur=tur)

    @app.route('/portfoy/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def portfoy_ekle():
        """Yeni çek veya senet kaydı"""
        if request.method == 'POST':
            try:
                evrak_no = request.form.get('evrak_no')
                e_turu = request.form.get('evrak_turu')
                i_turu = request.form.get('islem_turu')
                cari_id = request.form.get('cari_id')
                vade_str = request.form.get('vade_tarihi')
                tutar = parse_float(request.form.get('tutar'))
                banka_id = request.form.get('banka_id')
                aciklama = request.form.get('aciklama')
                asil_borclu = request.form.get('asil_borclu')

                vade_date = datetime.strptime(vade_str, '%Y-%m-%d').date() if vade_str else date.today()

                yeni = CekSenet(
                    EvrakNo=evrak_no,
                    EvrakTuru=e_turu,
                    IslemTuru=i_turu,
                    CariID=int(cari_id),
                    VadeTarihi=vade_date,
                    Tutar=tutar,
                    BankaID=int(banka_id) if banka_id else None,
                    AsilBorclu=asil_borclu,
                    Aciklama=aciklama
                )
                db.session.add(yeni)
                db.session.commit()
                
                log_action("Ekleme", "Finans", f"{evrak_no} nolu {e_turu} portföye eklendi.")
                flash('Kayıt başarıyla oluşturuldu.', 'success')
                return redirect(url_for('portfoy_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        cariler = CariAccount.query.order_by(CariAccount.Unvan.asc()).all()
        bankalar = BankAccount.query.all()
        return render_template('portfoy_form.html', cariler=cariler, bankalar=bankalar)

    @app.route('/portfoy/<int:csid>/durum', methods=['POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def portfoy_durum_guncelle(csid):
        """Çek veya senet durumunu günceller"""
        try:
            cs = CekSenet.query.get_or_404(csid)
            yeni_durum = request.form.get('durum')
            cs.Durum = yeni_durum
            
            # Eğer 'Ödendi' veya 'Tahsilde' ise finansal işlem gerekebilir
            # Şimdilik sadece durum güncelliyoruz
            
            db.session.commit()
            flash(f'Evrak durumu "{yeni_durum}" olarak güncellendi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
        return redirect(url_for('portfoy_listesi'))

    # === ÜRETİM VE REÇETE YÖNETİMİ ===
    @app.route('/receteler')
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def recete_listesi():
        """Tüm ürün reçetelerini listeler"""
        receteler = Recete.query.filter_by(Aktif=True).order_by(Recete.ReceteID.desc()).all()
        return render_template('recete_listesi.html', receteler=receteler)

    @app.route('/recete/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def recete_ekle():
        """Yeni ürün reçetesi oluşturur"""
        if request.method == 'POST':
            try:
                mamul_id = request.form.get('mamul_id')
                recete_adi = request.form.get('recete_adi')
                varsayilan_miktar = parse_float(request.form.get('varsayilan_miktar'))
                aciklama = request.form.get('aciklama')

                # Kalemleri al
                h_ids = request.form.getlist('hammadde_id[]')
                m_miktarlar = request.form.getlist('miktar[]')

                recete = Recete(
                    MamulID=int(mamul_id),
                    ReceteAdi=recete_adi,
                    VarsayilanMiktar=varsayilan_miktar,
                    Aciklama=aciklama
                )
                db.session.add(recete)
                db.session.flush()

                for i in range(len(h_ids)):
                    kalem = ReceteKalemi(
                        ReceteID=recete.ReceteID,
                        HammaddeID=int(h_ids[i]),
                        Miktar=parse_float(m_miktarlar[i])
                    )
                    db.session.add(kalem)

                db.session.commit()
                log_action("Ekleme", "Üretim", f"{recete_adi} reçetesi oluşturuldu.")
                flash('Reçete başarıyla kaydedildi.', 'success')
                return redirect(url_for('recete_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        mamuller = Urun.query.filter_by(Aktif=True).order_by(Urun.UrunAdi.asc()).all()
        return render_template('recete_form.html', mamuller=mamuller)

    @app.route('/recete/<int:rid>/duzenle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def recete_duzenle(rid):
        """Mevcut reçeteyi düzenler"""
        recete = Recete.query.get_or_404(rid)
        
        if request.method == 'POST':
            try:
                recete.MamulID = request.form.get('mamul_id')
                recete.ReceteAdi = request.form.get('recete_adi')
                recete.VarsayilanMiktar = parse_float(request.form.get('varsayilan_miktar'))
                recete.Aciklama = request.form.get('aciklama')
                
                # Mevcut kalemleri temizle ve yenilerini ekle
                ReceteKalemi.query.filter_by(ReceteID=rid).delete()
                
                h_ids = request.form.getlist('hammadde_id[]')
                m_miktarlar = request.form.getlist('miktar[]')
                fires = request.form.getlist('fire_orani[]')
                
                for i, hid in enumerate(h_ids):
                    if hid and m_miktarlar[i]:
                        kalem = ReceteKalemi(
                            ReceteID=recete.ReceteID,
                            HammaddeID=hid,
                            Miktar=parse_float(m_miktarlar[i]),
                            FireOrani=parse_float(fires[i]) if i < len(fires) else 0
                        )
                        db.session.add(kalem)
                
                db.session.commit()
                log_action("Güncelleme", "Reçete", f"Reçete güncellendi: {recete.ReceteAdi}")
                flash('Reçete başarıyla güncellendi.', 'success')
                return redirect(url_for('recete_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        mamuller = Urun.query.filter_by(Aktif=True).order_by(Urun.UrunAdi.asc()).all()
        return render_template('recete_form.html', recete=recete, mamuller=mamuller)

    @app.route('/recete/<int:rid>/sil', methods=['POST'])
    @login_required
    @roles_required('admin', 'muhasebe')
    def recete_sil(rid):
        """Reçeteyi arşivler"""
        try:
            recete = Recete.query.get_or_404(rid)
            recete.Aktif = False # Soft delete
            db.session.commit()
            flash('Reçete arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
        return redirect(url_for('recete_listesi'))

    @app.route('/uretim')
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def uretim_listesi():
        """Üretim emirlerini listeler"""
        emirler = UretimEmri.query.filter_by(Aktif=True).order_by(UretimEmri.EmirID.desc()).all()
        return render_template('uretim_listesi.html', emirler=emirler)

    @app.route('/uretim/ekle', methods=['GET', 'POST'])
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def uretim_ekle():
        """Yeni üretim emri oluşturur"""
        if request.method == 'POST':
            try:
                recete_id = request.form.get('recete_id')
                miktar = parse_float(request.form.get('miktar'))
                aciklama = request.form.get('aciklama')

                emir = UretimEmri(
                    ReceteID=int(recete_id),
                    Miktar=miktar,
                    Aciklama=aciklama
                )
                db.session.add(emir)
                db.session.commit()
                
                log_action("Ekleme", "Üretim", f"{miktar} birim üretim emri planlandı.")
                flash('Üretim emri başarıyla planlandı.', 'success')
                return redirect(url_for('uretim_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        receteler = Recete.query.all()
        return render_template('uretim_form.html', receteler=receteler)

    @app.route('/uretim/<int:ueid>/tamamla')
    @login_required
    @roles_required('admin', 'muhasebe', 'imalat')
    def uretim_tamamla(ueid):
        """Üretim emrini tamamlar ve stok hareketlerini işler"""
        try:
            emir = UretimEmri.query.get_or_404(ueid)
            if emir.Durum == 'Tamamlandı':
                flash('Bu emir zaten tamamlanmış.', 'warning')
                return redirect(url_for('uretim_listesi'))

            recete = emir.Recete
            
            # 1. Hammaddeleri Stoktan Düş
            for rk in recete.Kalemler:
                kullanim_miktari = (rk.Miktar / recete.VarsayilanMiktar) * emir.Miktar
                
                hareket = StokHareketi(
                    UrunID=rk.HammaddeID,
                    HareketTuru='Çıkış',
                    Miktar=kullanim_miktari,
                    Tarih=datetime.utcnow(),
                    Aciklama=f"Üretim Tüketimi (Emir No: {emir.EmirID})"
                )
                db.session.add(hareket)
                
                u = Urun.query.get(rk.HammaddeID)
                if u:
                    u.StokMiktari -= kullanim_miktari

            # 2. Mamulü Stoka Giriş Yap
            mamul_hareket = StokHareketi(
                UrunID=recete.MamulID,
                HareketTuru='Giriş',
                Miktar=emir.Miktar,
                Tarih=datetime.utcnow(),
                Aciklama=f"Üretim Girişi (Emir No: {emir.EmirID})"
            )
            db.session.add(mamul_hareket)
            
            m = Urun.query.get(recete.MamulID)
            if m:
                m.StokMiktari += emir.Miktar

            emir.Durum = 'Tamamlandı'
            db.session.commit()
            
            log_action("Güncelleme", "Üretim", f"Emir ID {ueid} tamamlandı, stoklar güncellendi.")
            flash(f'Üretim başarıyla tamamlandı. {emir.Miktar} adet {recete.Mamul.UrunAdi} stoka eklendi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
        
        return redirect(url_for('uretim_listesi'))

    # === DÖKÜMAN VE BELGE YÖNETİMİ ===
    @app.route('/belgeler')
    @login_required
    def belge_listesi():
        """Sistemdeki tüm belgeleri listeler"""
        kat = request.args.get('kategori')
        query = Document.query
        if kat:
            query = query.filter(Document.Kategori == kat)
        
        belgeler = query.order_by(Document.EklemeTarihi.desc()).all()
        return render_template('belge_listesi.html', belgeler=belgeler, kategori=kat)

    @app.route('/belge/yukle', methods=['GET', 'POST'])
    @login_required
    def belge_yukle():
        """Yeni belge yükleme işlemi"""
        if request.method == 'POST':
            try:
                file = request.files.get('dosya')
                if not file:
                    flash('Lütfen bir dosya seçin.', 'warning')
                    return redirect(request.url)

                filename = secure_filename(file.filename)
                # Benzersiz dosya adı oluştur
                unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                
                upload_folder = os.path.join(config.UPLOADS_DIR, 'documents')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)

                # Veritabanına kaydet
                doc = Document(
                    DosyaYolu=f"documents/{unique_filename}",
                    DosyaAdi=filename,
                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else 'bin',
                    DosyaBoyutu=os.path.getsize(filepath),
                    Kategori=request.form.get('kategori', 'Diğer'),
                    CariID=int(request.form.get('cari_id')) if request.form.get('cari_id') else None,
                    FaturaID=int(request.form.get('fatura_id')) if request.form.get('fatura_id') else None,
                    PersonelID=int(request.form.get('personel_id')) if request.form.get('personel_id') else None,
                    Aciklama=request.form.get('aciklama')
                )
                db.session.add(doc)
                db.session.commit()
                
                log_action("Ekleme", "Belge", f"{filename} isimli belge sisteme yüklendi.")
                flash('Belge başarıyla yüklendi.', 'success')
                return redirect(url_for('belge_listesi'))
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')

        cariler = CariAccount.query.filter_by(Aktif=True).all()
        faturalar = Fatura.query.filter_by(Aktif=True).order_by(Fatura.FaturaID.desc()).limit(100).all()
        personeller = Personel.query.filter_by(Aktif=True).all()
        return render_template('belge_form.html', cariler=cariler, faturalar=faturalar, personeller=personeller)

    @app.route('/belge/sil/<int:bid>')
    @login_required
    @roles_required('admin')
    def belge_sil(bid):
        """Belgeyi sistemden tamamen siler"""
        try:
            doc = Document.query.get_or_404(bid)
            # Fiziksel dosyayı sil
            fullpath = os.path.join(config.UPLOADS_DIR, doc.DosyaYolu)
            if os.path.exists(fullpath):
                os.remove(fullpath)
            
            db.session.delete(doc)
            db.session.commit()
            flash('Belge ve ilişkili dosya silindi.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
        return redirect(url_for('belge_listesi'))


    # === GELİŞMİŞ RAPORLAMA VE BI ===
    @app.route('/raporlar')
    @login_required
    @roles_required('admin', 'muhasebe')
    def raporlar_dashboard():
        """Genel raporlama ve BI paneli"""
        try:
            # 1. Satış ve Alış Özetleri
            total_sales = db.session.query(func.sum(Fatura.GenelToplam)).filter(Fatura.FaturaTuru == 'Satış').scalar() or 0
            total_purchases = db.session.query(func.sum(Fatura.GenelToplam)).filter(Fatura.FaturaTuru == 'Alış').scalar() or 0
            
            # 2. Ürün Bazlı Performans (En Çok Satan 5 Ürün)
            top_products = db.session.query(
                Urun.UrunAdi, 
                func.sum(FaturaKalemi.Miktar).label('toplam_miktar'),
                func.sum(FaturaKalemi.SatirToplami).label('toplam_tutar')
            ).join(FaturaKalemi, Urun.UrunID == FaturaKalemi.UrunID)\
             .join(Fatura, Fatura.FaturaID == FaturaKalemi.FaturaID)\
             .filter(Fatura.FaturaTuru == 'Satış')\
             .group_by(Urun.UrunAdi)\
             .order_by(text('toplam_miktar DESC'))\
             .limit(5).all()

            # 3. Cari Bazlı Performans (En Çok Alım Yapan 5 Müşteri)
            top_customers = db.session.query(
                CariAccount.Unvan,
                func.sum(Fatura.GenelToplam).label('toplam_tutar')
            ).join(Fatura, CariAccount.CariID == Fatura.CariID)\
             .filter(Fatura.FaturaTuru == 'Satış')\
             .group_by(CariAccount.Unvan)\
             .order_by(text('toplam_tutar DESC'))\
             .limit(5).all()

            # 4. Aylık Trend Verileri (Görselleştirme için)
            current_year = datetime.now().year
            monthly_sales = []
            monthly_purchases = []
            months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
            
            for m in range(1, 13):
                s = db.session.query(func.sum(Fatura.GenelToplam))\
                    .filter(Fatura.FaturaTuru == 'Satış', func.strftime('%m', Fatura.Tarih) == f"{m:02d}", func.strftime('%Y', Fatura.Tarih) == str(current_year)).scalar() or 0
                p = db.session.query(func.sum(Fatura.GenelToplam))\
                    .filter(Fatura.FaturaTuru == 'Alış', func.strftime('%m', Fatura.Tarih) == f"{m:02d}", func.strftime('%Y', Fatura.Tarih) == str(current_year)).scalar() or 0
                monthly_sales.append(float(s))
                monthly_purchases.append(float(p))

            # 5. Stok Değerleme (Son Alış Fiyatı Üzerinden)
            # Alt sorgu: Her ürün için en son giriş hareketi fiyatını bul
            subquery = db.session.query(
                StokHareketi.UrunID,
                func.max(StokHareketi.HareketID).label('max_id')
            ).filter(StokHareketi.HareketTuru == 'Giriş').group_by(StokHareketi.UrunID).subquery()

            latest_prices = db.session.query(
                StokHareketi.UrunID,
                StokHareketi.BirimFiyat
            ).join(subquery, StokHareketi.HareketID == subquery.c.max_id).all()
            
            price_map = {p.UrunID: p.BirimFiyat for p in latest_prices}
            
            
            all_products = Urun.query.filter_by(Aktif=True).all()
            stock_valuation = 0
            for prod in all_products:
                p_val = price_map.get(prod.UrunID)
                if p_val is None:
                    p_val = prod.AlisFiyati or 0
                if p_val is None:
                    p_val = 0.0
                
                stock_valuation += (prod.StokMiktari or 0) * float(p_val)

            # 6. Nakit Akışı ve Finansal Sağlık
            kasa_toplam = db.session.query(func.sum(Finance.Tutar)).filter(Finance.IslemTuru == 'Gelir', Finance.Aktif == True).scalar() or 0
            kasa_cikisi = db.session.query(func.sum(Finance.Tutar)).filter(Finance.IslemTuru == 'Gider', Finance.Aktif == True).scalar() or 0
            net_kasa = kasa_toplam - kasa_cikisi
            
            banka_bakiyeler = db.session.query(func.sum(BankAccount.Bakiye)).filter(BankAccount.Aktif == True).scalar() or 0
            
            borclar = db.session.query(func.sum(Debt.KalanTutar)).filter(Debt.Aktif == True).scalar() or 0
            alacaklar = db.session.query(func.sum(Receivable.KalanTutar)).filter(Receivable.Aktif == True).scalar() or 0
            
            verilen_cekler = db.session.query(func.sum(CekSenet.Tutar)).filter(CekSenet.IslemTuru == 'Verilen', CekSenet.Durum != 'Ödendi').scalar() or 0
            alinan_cekler = db.session.query(func.sum(CekSenet.Tutar)).filter(CekSenet.IslemTuru == 'Alınan', CekSenet.Durum != 'Ödendi').scalar() or 0

            bi_data = {
                'total_sales': total_sales,
                'total_purchases': total_purchases,
                'gross_profit': total_sales - total_purchases,
                'top_products': top_products,
                'top_customers': top_customers,
                'stock_valuation': stock_valuation,
                'total_assets': net_kasa + banka_bakiyeler + alacaklar + alinan_cekler,
                'total_liabilities': borclar + verilen_cekler,
                'chart': {
                    'labels': months,
                    'sales': monthly_sales,
                    'purchases': monthly_purchases
                }
            }

            return render_template('raporlar.html', bi=bi_data)
        except Exception as e:
            app.logger.exception("Reporting error")
            return f"Reporting Error: {str(e)}", 500

    @app.route('/bankalar')
    @login_required
    @roles_required('admin', 'muhasebe')
    def bankalar():
        try:
            banks = BankAccount.query.filter_by(Aktif=True).all()
            for b in banks:
                update_bank_balance(b.BankaID)
            # Bakiyeler güncellendikten sonra tekrar çek
            banks = BankAccount.query.filter_by(Aktif=True).all()
            today = date.today()

            checks = Finance.query.filter(Finance.Aktif==True, func.lower(Finance.Kategori).like('%çek%')).all()

            for b in banks:
                b.pending_checks = []
                b.pending_checks_total = 0.0

            for c in checks:
                cat_lower = (c.Kategori or '').lower()
                desc_lower = (c.Aciklama or '').lower()
                if 'bankaya verildi' not in cat_lower and 'bankaya verildi' not in desc_lower and 'bankaya verilen çek' not in desc_lower and 'bankaya verilen cek' not in desc_lower:
                    continue

                def normalize_tr(text):
                    if not text: return ""
                    text = text.lower()
                    text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
                    return text

                target_bank = None
                n_cat = normalize_tr(cat_lower)
                n_desc = normalize_tr(desc_lower)
                for b in banks:
                    n_bank = normalize_tr(b.BankaAdi)
                    if n_bank and (n_bank in n_cat or n_bank in n_desc):
                        target_bank = b
                        break
                if not target_bank:
                    continue

                desc_lower = (c.Aciklama or '').lower()
                if 'tahsil edildi' in desc_lower:
                    continue

                amount = float(c.Tutar or 0)
                target_bank.pending_checks.append(c)
                target_bank.pending_checks_total += amount

            db.session.commit()

            entries = Finance.query.order_by(Finance.Tarih.desc()).all()
            for b in banks:
                b.movements = []
                for e in entries:
                    is_match = False
                    if e.BankaID == b.BankaID:
                        is_match = True
                    else:
                        desc_lower = (e.Aciklama or '').lower()
                        cat_lower = (e.Kategori or '').lower()
                        name_lower = (b.BankaAdi or '').lower()
                        if name_lower and (name_lower in desc_lower or name_lower in cat_lower):
                            is_match = True
                    
                    if is_match:
                        # Eğer bu bir çek ise ve BankaID eşleşmesi yoksa (sadece isim eşleşmesi varsa),
                        # sadece "bankaya verildi" veya "tahsil edildi" durumlarındaysa göster.
                        if e.BankaID != b.BankaID:
                            cat_lower = (e.Kategori or '').lower()
                            desc_lower = (e.Aciklama or '').lower()
                            is_cek = 'çek' in cat_lower or 'cek' in cat_lower or 'çek' in desc_lower or 'cek' in desc_lower
                            if is_cek:
                                if 'bankaya verildi' not in cat_lower and 'bankaya verildi' not in desc_lower and 'tahsil edildi' not in cat_lower and 'tahsil edildi' not in desc_lower:
                                    is_match = False

                    if is_match:
                        b.movements.append(e)
                        if len(b.movements) >= 20:
                            break

            tl_balance = sum(b.Bakiye for b in banks if (b.ParaBirimi or 'TRY') == 'TRY')
            
            fx_map = {}
            for b in banks:
                code = b.ParaBirimi or 'TRY'
                if code != 'TRY':
                    fx_map[code] = fx_map.get(code, 0.0) + b.Bakiye
            
            fx_balances = [{'code': k, 'amount': v} for k, v in fx_map.items()]
            fx_balances.sort(key=lambda x: x['code'])

            rates = get_exchange_rates()
            total_assets_tl = tl_balance
            for fx in fx_balances:
                rate = rates.get(fx['code'], 1.0)
                total_assets_tl += (fx['amount'] * rate)

            today_date = today.strftime('%Y-%m-%d')
            return render_template('bankalar.html',
                                   banks=banks,
                                   total_assets=total_assets_tl,
                                   tl_balance=tl_balance,
                                   fx_balances=fx_balances,
                                   rates=rates,
                                   today_date=today_date)
        except Exception as e:
            app.logger.exception('Bankalar error')
            return "Error: {}".format(e), 500

    @app.route('/bankalar/ekle', methods=['GET', 'POST'])
    @login_required
    def bankalar_ekle():
        if request.method == 'POST':
            try:
                data = request.form
                b = BankAccount(
                    BankaAdi=data.get('BankaAdi'),
                    HesapAdi=data.get('HesapAdi'),
                    HesapTipi=data.get('HesapTipi'),
                    Sube=data.get('Sube'),
                    HesapNo=data.get('HesapNo'),
                    IBAN=data.get('IBAN'),
                    Bakiye=float(data.get('Bakiye') or 0),
                    ParaBirimi=data.get('ParaBirimi', 'TRY')
                )
                db.session.add(b)
                db.session.flush() # Get the ID

                # Başlangıç bakiyesi varsa finans girişi yap
                if b.Bakiye != 0:
                    f = Finance(
                        Tarih=date.today(),
                        Tutar=abs(b.Bakiye),
                        IslemTuru='Gelir' if b.Bakiye > 0 else 'Gider',
                        Kategori='Devir Bakiyesi',
                        Aciklama=f"{b.BankaAdi} - Açılış Bakiyesi",
                        BankaID=b.BankaID
                    )
                    db.session.add(f)
                
                db.session.commit()
                log_action("Ekleme", "Banka", f"{b.BankaAdi} hesabı eklendi.")
                flash('Banka hesabı başarıyla eklendi.', 'success')
                return redirect(url_for('bankalar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Banka ekle error')
                flash('Hata: {}'.format(e), 'danger')
        return render_template('banka_ekle.html')

    @app.route('/bankalar/<int:bid>/islem', methods=['POST'])
    @login_required
    def bankalar_islem(bid):
        b = BankAccount.query.get_or_404(bid)
        try:
            data = request.form
            raw_amount = (data.get('amount') or '0').replace(',', '.')
            amount = float(raw_amount or 0)
            trx_type = data.get('transactionType') or 'deposit'
            date_str = data.get('date')
            dt = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
            category = data.get('category') or 'Banka İşlemi'
            desc = data.get('description') or ''
            target_account = data.get('target_account') or ''

            if trx_type == 'deposit':
                islem_turu = 'Gelir'
                delta = amount
            else:
                islem_turu = 'Gider'
                delta = -amount

            extra_parts = []
            if trx_type == 'transfer':
                extra_parts.append('Transfer')
            if target_account:
                extra_parts.append(f'Hedef: {target_account}')
            extra_str = ' | '.join(extra_parts)
            full_desc = desc
            if extra_str and desc:
                full_desc = f"{extra_str} - {desc}"
            elif extra_str:
                full_desc = extra_str

            f = Finance(
                Tarih=dt,
                Tutar=amount,
                IslemTuru=islem_turu,
                Kategori=category,
                Aciklama=f"{b.BankaAdi} - {full_desc}" if full_desc else b.BankaAdi,
                BankaID=b.BankaID
            )
            db.session.add(f)

            b.Bakiye = (b.Bakiye or 0) + delta

            db.session.commit()
            log_action("İşlem", "Banka", f"{b.BankaAdi}: {islem_turu} - {amount:,.2f} TL ({full_desc})")
            flash('Banka işlemi kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Banka islem error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('bankalar'))

    @app.route('/bankalar/<int:bid>/edit', methods=['GET', 'POST'])
    @login_required
    def bankalar_edit(bid):
        b = BankAccount.query.get_or_404(bid)
        if request.method == 'POST':
            try:
                data = request.form
                old_bakiye = float(b.Bakiye or 0)
                new_bakiye = float(data.get('Bakiye') or 0)
                
                b.BankaAdi = data.get('BankaAdi')
                b.HesapAdi = data.get('HesapAdi')
                b.HesapTipi = data.get('HesapTipi')
                b.Sube = data.get('Sube')
                b.HesapNo = data.get('HesapNo')
                b.IBAN = data.get('IBAN')
                b.Bakiye = new_bakiye
                b.ParaBirimi = data.get('ParaBirimi', 'TRY')
                
                # Başlangıç bakiyesi değiştiyse Devir Bakiyesi kaydını güncelle veya oluştur
                if old_bakiye != new_bakiye:
                    devir = Finance.query.filter_by(BankaID=b.BankaID, Kategori='Devir Bakiyesi').first()
                    if devir:
                        devir.Tutar = abs(new_bakiye)
                        devir.IslemTuru = 'Gelir' if new_bakiye > 0 else 'Gider'
                    else:
                        f = Finance(
                            Tarih=date.today(),
                            Tutar=abs(new_bakiye),
                            IslemTuru = 'Gelir' if new_bakiye > 0 else 'Gider',
                            Kategori='Devir Bakiyesi',
                            Aciklama=f"{b.BankaAdi} - Açılış Bakiyesi",
                            BankaID=b.BankaID
                        )
                        db.session.add(f)

                db.session.commit()
                # Bakiyeyi tekrar hesapla
                update_bank_balance(b.BankaID)
                
                log_action("Güncelleme", "Banka", f"{b.BankaAdi} hesabı güncellendi.")
                flash('Banka hesabı güncellendi.', 'success')
                return redirect(url_for('bankalar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Banka edit error')
                flash('Hata: {}'.format(e), 'danger')
        return render_template('banka_ekle.html', bank=b)

    @app.route('/bankalar/<int:bid>/delete', methods=['POST'])
    @login_required
    def bankalar_delete(bid):
        try:
            b = BankAccount.query.get_or_404(bid)
            b.Aktif = False # Soft delete
            db.session.commit()
            log_action("Arşivleme", "Banka", f"{b.BankaAdi} hesabı arşivlendi.")
            flash('Banka hesabı arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Banka delete error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('bankalar'))

    @app.route('/alacaklar')
    @login_required
    def alacaklar():
        try:
            receivables = Receivable.query.filter_by(Aktif=True).order_by(Receivable.VadeTarihi.asc()).all()
            total_receivables = sum(r.AnaTutar for r in receivables)
            collected_amount = sum(r.AnaTutar - r.KalanTutar for r in receivables)
            pending_amount = sum(r.KalanTutar for r in receivables)
            banks = BankAccount.query.filter_by(Aktif=True).all()
            cariler = CariAccount.query.filter_by(Aktif=True).all()
            
            # Alacak tahsilatında kullanılabilecek çekler
            customer_checks = Finance.query.filter(
                Finance.Aktif == True,
                Finance.IslemTuru == 'Gelir',
                (Finance.Kategori.ilike('%çek%') | Finance.Kategori.ilike('%cek%') | Finance.Aciklama.ilike('%çek%') | Finance.Aciklama.ilike('%cek%')),
                ~Finance.Aciklama.ilike('%tahsil edildi%'),
                ~Finance.Aciklama.ilike('%silindi%'),
                ~Finance.Aciklama.ilike('%ciro edildi%')
            ).all()

            pre_selected_cari_id = request.args.get('cari_id')
            return render_template('alacaklar.html', 
                                 receivables=receivables, 
                                 total_receivables=total_receivables, 
                                 collected_amount=collected_amount, 
                                 pending_amount=pending_amount, 
                                 banks=banks, 
                                 cariler=cariler,
                                 customer_checks=customer_checks,
                                 pre_selected_cari_id=pre_selected_cari_id)
        except Exception as e:
            app.logger.exception('Alacaklar error')
            return "Error: {}".format(e), 500

    @app.route('/alacaklar/ekle', methods=['GET', 'POST'])
    @login_required
    def alacaklar_ekle():
        if request.method == 'POST':
            try:
                data = request.form
                tutar = parse_float(data.get('AnaTutar'))
                vade = datetime.strptime(data.get('VadeTarihi'), '%Y-%m-%d').date() if data.get('VadeTarihi') else None
                baslik_raw = (data.get('Baslik') or '').strip()
                if not baslik_raw:
                    parts = []
                    if data.get('AlacakTuru'):
                        parts.append(data.get('AlacakTuru'))
                    if data.get('Alacakli'):
                        parts.append(data.get('Alacakli'))
                    baslik_raw = ' - '.join(parts) or 'Alacak'
                r = Receivable(
                    Baslik=baslik_raw,
                    Alacakli=data.get('Alacakli'),
                    AlacakTuru=data.get('AlacakTuru'),
                    AnaTutar=tutar,
                    KalanTutar=tutar,
                    Tutar=tutar,
                    VadeTarihi=vade,
                    Aciklama=data.get('Aciklama'),
                    CariID=data.get('cari_id') if data.get('cari_id') else None,
                    Durum='Bekliyor'
                )
                db.session.add(r)
                db.session.commit()
                if r.CariID:
                    update_cari_balance(r.CariID)
                log_action("Ekleme", "Alacak", f"{r.Alacakli} - {r.AnaTutar:,.2f} TL")
                flash('Alacak kaydı oluşturuldu.', 'success')
                return redirect(url_for('alacaklar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Alacak ekle error')
                flash('Hata: {}'.format(e), 'danger')
        cariler = CariAccount.query.filter(or_(CariAccount.CariTipi == 'Müşteri', CariAccount.CariTipi == 'Her İkisi'), CariAccount.Aktif == True).order_by(CariAccount.Unvan.asc()).all()
        return render_template('alacak_ekle.html', cariler=cariler)

    @app.route('/alacaklar/<int:aid>/edit', methods=['GET', 'POST'])
    @login_required
    def alacaklar_edit(aid):
        r = Receivable.query.get_or_404(aid)
        if request.method == 'POST':
            try:
                data = request.form
                baslik_raw = (data.get('Baslik') or '').strip()
                if not baslik_raw:
                    parts = []
                    if data.get('AlacakTuru'):
                        parts.append(data.get('AlacakTuru'))
                    if data.get('Alacakli'):
                        parts.append(data.get('Alacakli'))
                    baslik_raw = ' - '.join(parts) or r.Baslik or 'Alacak'
                r.Baslik = baslik_raw
                r.Alacakli = data.get('Alacakli')
                r.AlacakTuru = data.get('AlacakTuru')
                r.AnaTutar = parse_float(data.get('AnaTutar'))
                r.Tutar = r.AnaTutar
                r.KalanTutar = parse_float(data.get('KalanTutar'), r.KalanTutar)
                if data.get('VadeTarihi'):
                    r.VadeTarihi = datetime.strptime(data.get('VadeTarihi'), '%Y-%m-%d').date()
                old_cari_id = r.CariID
                r.Aciklama = data.get('Aciklama')
                r.Durum = data.get('Durum') or r.Durum
                r.CariID = data.get('cari_id') if data.get('cari_id') else None
                
                db.session.commit()
                if old_cari_id:
                    update_cari_balance(old_cari_id)
                if r.CariID and r.CariID != str(old_cari_id):
                    update_cari_balance(r.CariID)
                flash('Alacak kaydı güncellendi.', 'success')
                return redirect(url_for('alacaklar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Alacak edit error')
                flash('Hata: {}'.format(e), 'danger')
        cariler = CariAccount.query.filter_by(Aktif=True).all()
        return render_template('alacak_ekle.html', entry=r, cariler=cariler)

    @app.route('/alacaklar/<int:aid>/delete', methods=['POST'])
    @login_required
    def alacaklar_delete(aid):
        try:
            r = Receivable.query.get_or_404(aid)
            cid = r.CariID
            r.Aktif = False # Soft delete
            db.session.commit()
            if cid:
                update_cari_balance(cid)
            flash('Alacak kaydı arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Alacak delete error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('alacaklar'))

    @app.route('/alacaklar/<int:aid>/collect', methods=['POST'])
    @login_required
    def alacaklar_collect(aid):
        try:
            r = Receivable.query.get_or_404(aid)

            if r.KalanTutar <= 0 or r.Durum == 'Tahsil Edildi':
                flash('Bu alacak zaten tahsil edilmiş görünüyor.', 'info')
                return redirect(url_for('alacaklar'))

            data = request.form
            amount = parse_float(data.get('amount'))

            if amount <= 0:
                flash('Geçerli bir tahsilat tutarı girmelisiniz.', 'danger')
                return redirect(url_for('alacaklar'))

            if amount > (r.KalanTutar or 0):
                amount = r.KalanTutar or 0

            method = (data.get('payment_method') or '').lower()
            bank_id_raw = data.get('bank_id') or ''

            if method not in ('cash', 'bank', 'cek'):
                flash('Geçersiz tahsilat yöntemi seçildi.', 'danger')
                return redirect(url_for('alacaklar'))

            bank = None
            if method == 'bank':
                try:
                    bank_id = int(bank_id_raw)
                except ValueError:
                    bank_id = None

                if not bank_id:
                    flash('Banka ile tahsilat için bir hesap seçmelisiniz.', 'danger')
                    return redirect(url_for('alacaklar'))

                bank = BankAccount.query.get(bank_id)
                if not bank:
                    flash('Seçilen banka hesabı bulunamadı.', 'danger')
                    return redirect(url_for('alacaklar'))

            remaining_before = float(r.KalanTutar or 0)
            remaining_after = remaining_before - amount
            if remaining_after <= 0.01:
                r.KalanTutar = 0.0
                r.Durum = 'Tahsil Edildi'
            else:
                r.KalanTutar = remaining_after
                if r.KalanTutar < r.AnaTutar:
                    r.Durum = 'Kısmi Tahsil'

            method_label = 'Nakit'
            check_details = ""
            if method == 'bank' and bank:
                method_label = f"Banka: {bank.BankaAdi}"
            elif method == 'cek':
                check_no = data.get('check_no')
                due_date = data.get('check_due_date')
                parts = []
                if check_no: parts.append(f"No:{check_no}")
                if due_date: parts.append(f"Vade:{due_date}")
                if parts:
                    check_details = " (" + ", ".join(parts) + ")"
                method_label = f"Çek{check_details}"

            desc_parts = []
            if r.Alacakli:
                desc_parts.append(f"{r.Alacakli} için alacak tahsilatı")
            desc_parts.append(f"Alacak ID: {r.AlacakID}")
            desc_parts.append(method_label)
            aciklama = " | ".join(desc_parts)

            kategori = 'Alacak Tahsilatı'
            if method == 'cek':
                if r.Alacakli:
                    kategori = f"Çek - {r.Alacakli}"
                else:
                    kategori = 'Çek'

            f_rec = Finance(
                Tarih=date.today(),
                Tutar=amount,
                IslemTuru='Gelir',
                Kategori=kategori,
                Aciklama=aciklama,
                CariID=r.CariID
            )
            db.session.add(f_rec)

            if method == 'bank' and bank:
                bank.Bakiye = (bank.Bakiye or 0) + amount

            db.session.commit()
            log_action("İşlem", "Alacak", f"{r.Alacakli} alacağından {amount:,.2f} TL tahsil edildi.")
            
            if r.CariID:
                update_cari_balance(r.CariID)
            
            flash('Alacak tahsilatı kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Alacak collect error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('alacaklar'))

    @app.route('/mesailer')
    @login_required
    def mesailer():
        try:
            today = date.today()
            selected_year = int(request.args.get('year') or today.year)
            selected_month = int(request.args.get('month') or today.month)
            search_query = (request.args.get('q') or '').strip()
            selected_department = (request.args.get('department') or '').strip()

            month_choices = [
                (1, 'Ocak'), (2, 'Şubat'), (3, 'Mart'), (4, 'Nisan'),
                (5, 'Mayıs'), (6, 'Haziran'), (7, 'Temmuz'), (8, 'Ağustos'),
                (9, 'Eylül'), (10, 'Ekim'), (11, 'Kasım'), (12, 'Aralık')
            ]
            year_choices = [today.year - 1, today.year, today.year + 1]

            start_date = date(selected_year, selected_month, 1)
            if selected_month == 12:
                end_date = date(selected_year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(selected_year, selected_month + 1, 1) - timedelta(days=1)

            personel_query = Personel.query
            if selected_department:
                personel_query = personel_query.filter_by(Aktif=True).filter(Personel.Departman == selected_department)
            else:
                personel_query = personel_query.filter_by(Aktif=True)
            if search_query:
                like_expr = f"%{search_query}%"
                personel_query = personel_query.filter(
                    or_(Personel.Ad.ilike(like_expr), Personel.Soyad.ilike(like_expr))
                )
            personeller = personel_query.all()

            company = Company.query.first()
            settings = company.get_settings() if company else {}
            weekly_schedule = settings.get('weekly_schedule', {}) if settings else {}
            public_holidays = settings.get('public_holidays', []) if settings else []
            monthly_hours = float(settings.get('monthly_working_hours', 225)) if settings else 225.0
            daily_net_work_hours = monthly_hours / 30.0 if monthly_hours > 0 else 0.0

            rows = []
            toplam_mesai_saat = 0.0
            tahmini_odeme = 0.0
            mesai_personel_sayisi = 0

            period_date = date(selected_year, selected_month, 1)
            empty_person_deductions = {}

            for p in personeller:
                payroll_data = services.get_payroll_for_person(
                    p,
                    period_date,
                    weekly_schedule,
                    public_holidays,
                    monthly_hours,
                    daily_net_work_hours,
                    empty_person_deductions
                )
                mesai_saat = float(payroll_data.get('overtime_hours') or 0.0)
                odeme = float(payroll_data.get('overtime_pay') or 0.0)
                if mesai_saat > 0:
                    mesai_personel_sayisi += 1
                toplam_mesai_saat += mesai_saat
                tahmini_odeme += odeme
                rows.append({
                    'personel': p,
                    'toplam_mesai_saat': mesai_saat,
                    'tahmini_odeme': odeme
                })

            stats = {
                'mesai_personel_sayisi': mesai_personel_sayisi,
                'toplam_mesai_saat': toplam_mesai_saat,
                'tahmini_odeme': tahmini_odeme
            }

            departments = sorted({p.Departman for p in personeller if p.Departman})

            mesai_states = settings.get('mesai_states', {}) if settings else {}
            period_key = f"{selected_year:04d}-{selected_month:02d}"
            mesai_state = mesai_states.get(period_key, 'open')

            return render_template(
                'mesailer.html',
                rows=rows,
                stats=stats,
                month_choices=month_choices,
                year_choices=year_choices,
                selected_month=selected_month,
                selected_year=selected_year,
                department_choices=departments,
                selected_department=selected_department,
                search_query=search_query,
                mesai_state=mesai_state
            )
        except Exception as e:
            app.logger.exception('Mesailer error')
            return "Error: {}".format(e), 500

    @app.route('/mesailer/lock', methods=['POST'])
    @login_required
    def mesailer_lock():
        try:
            year = int(request.form.get('year'))
            month = int(request.form.get('month'))
            next_state = (request.form.get('next_state') or 'open').strip()

            company = Company.query.first()
            if not company:
                flash('Şirket ayarları bulunamadı.', 'danger')
                return redirect(url_for('mesailer', year=year, month=month))

            settings = company.get_settings() or {}
            mesai_states = settings.get('mesai_states', {})
            period_key = f"{year:04d}-{month:02d}"
            mesai_states[period_key] = 'locked' if next_state == 'locked' else 'open'
            settings['mesai_states'] = mesai_states
            company.set_settings(settings)
            db.session.commit()

            if next_state == 'locked':
                flash(f'{month:02d}/{year} dönemi için mesailer kilitlendi.', 'success')
            else:
                flash(f'{month:02d}/{year} dönemi için mesai kilidi kaldırıldı.', 'success')

            return redirect(url_for('mesailer', year=year, month=month))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Mesailer lock error')
            flash('Mesai durumu güncellenirken bir hata oluştu.', 'danger')
            return redirect(url_for('mesailer'))

    @app.route('/mesailer/<int:personel_id>')
    @login_required
    def mesailer_detay(personel_id):
        try:
            today = date.today()
            selected_year = int(request.args.get('year') or today.year)
            selected_month = int(request.args.get('month') or today.month)

            start_date = date(selected_year, selected_month, 1)
            if selected_month == 12:
                end_date = date(selected_year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(selected_year, selected_month + 1, 1) - timedelta(days=1)

            person = Personel.query.get_or_404(personel_id)

            records = (
                Puantaj.query
                .filter(
                    Puantaj.PersonelID == personel_id,
                    Puantaj.Tarih >= start_date,
                    Puantaj.Tarih <= end_date
                )
                .order_by(Puantaj.Tarih.asc())
                .all()
            )

            company = Company.query.first()
            settings = company.get_settings() if company else {}
            weekly_schedule = settings.get('weekly_schedule', {}) if settings else {}
            public_holidays = settings.get('public_holidays', []) if settings else {}
            monthly_hours = float(settings.get('monthly_working_hours', 225)) if settings else 225.0
            daily_net_work_hours = monthly_hours / 30.0 if monthly_hours > 0 else 0.0

            salary = float(person.NetMaas or 0)
            saatlik_mesai_ucreti = 0.0
            if daily_net_work_hours > 0:
                saatlik_mesai_ucreti = salary / 30.0 / daily_net_work_hours

            rows = []
            num_days = end_date.day
            
            # Detailed calculation matching get_payroll_for_person priority logic
            total_mesai_pay = 0.0
            total_overtime_hours = 0.0
            total_missing_hours = 0.0
            total_absence_deduction_hours = 0.0
            total_absence_deduction_maas = 0.0 # From 'Maaş' type records

            overtime_by_type = {
                'public_holiday': {'hours': 0.0, 'pay': 0.0, 'multiplier': 2.0},
                'weekend': {'hours': 0.0, 'pay': 0.0, 'multiplier': 2.0},
                'weekday': {'hours': 0.0, 'pay': 0.0, 'multiplier': 1.5}
            }

            # Map records by date for easy lookup
            record_map = {r.Tarih.day: r for r in records}

            for day in range(1, num_days + 1):
                curr_date = date(selected_year, selected_month, day)
                r = record_map.get(day)
                
                days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_name = days_map[curr_date.weekday()]
                day_config = weekly_schedule.get(day_name, {})
                is_public_holiday = any(holiday['date'] == curr_date.strftime('%Y-%m-%d') for holiday in public_holidays)
                
                if is_public_holiday:
                    ot_type = 'public_holiday'
                    default_mult = float(next((h['multiplier'] for h in public_holidays if h['date'] == curr_date.strftime('%Y-%m-%d')), 2.0))
                else:
                    ot_type = 'weekend' if day_name in ['saturday', 'sunday'] else 'weekday'
                    d_mult = 2.0 if ot_type == 'weekend' else 1.5
                    default_mult = float(day_config.get('multiplier', d_mult))
                
                # Resolve final multiplier (using saved or setting)
                if r:
                    display_carpan = services.resolve_multiplier(r.Carpan, default_mult)
                    mesai_saat = float(r.MesaiSaati or 0.0)
                    eksik_saat = float(r.EksikSaat or 0.0)
                    durum = r.Durum or 'Geldi'
                    kesinti_turu = r.KesintiTuru or 'Maaş'
                else:
                    display_carpan = default_mult
                    mesai_saat = 0.0
                    eksik_saat = 0.0
                    durum = 'Geldi'
                    kesinti_turu = 'Maaş'

                # Calculate overtime for THIS day
                pay = mesai_saat * saatlik_mesai_ucreti * display_carpan
                if mesai_saat > 0:
                    overtime_by_type[ot_type]['hours'] += mesai_saat
                    overtime_by_type[ot_type]['pay'] += pay
                    total_mesai_pay += pay
                    total_overtime_hours += mesai_saat

                # Calculate absences/missing
                if durum.lower() == 'gelmedi':
                    total_missing_hours += daily_net_work_hours
                    if kesinti_turu == 'Maaş':
                        total_absence_deduction_maas += salary / 30.0
                    else:
                        total_absence_deduction_hours += daily_net_work_hours
                elif durum.lower() == 'geç geldi' or eksik_saat > 0:
                    total_missing_hours += eksik_saat
                    if kesinti_turu == 'Maaş':
                        total_absence_deduction_maas += eksik_saat * saatlik_mesai_ucreti
                    else:
                        total_absence_deduction_hours += eksik_saat

                rows.append({
                    'day': day,
                    'date': curr_date,
                    'record': r,
                    'display_carpan': display_carpan,
                    'mesai_saat': mesai_saat,
                    'eksik_saat': eksik_saat,
                    'durum': durum,
                    'kesinti_turu': kesinti_turu,
                    'mesai_ucreti': pay
                })

            # Priority-based deduction from mesai hours (Matches Bordro logic exactly)
            remaining_hours_to_deduct = total_absence_deduction_hours
            total_deducted_from_mesai_pay = 0.0
            for ot_type in ['public_holiday', 'weekend', 'weekday']:
                if remaining_hours_to_deduct <= 0:
                    break
                available_hours = overtime_by_type[ot_type]['hours']
                if available_hours > 0:
                    deduct_hours = min(remaining_hours_to_deduct, available_hours)
                    # Deduct proportional pay for these hours
                    deduct_pay = (deduct_hours / available_hours) * overtime_by_type[ot_type]['pay']
                    total_mesai_pay -= deduct_pay
                    total_deducted_from_mesai_pay += deduct_pay
                    remaining_hours_to_deduct -= deduct_hours

            # If still remaining mesai-type hours, they must deduct from salary (shown in stats as deduction)
            if remaining_hours_to_deduct > 0:
                total_deducted_from_mesai_pay += remaining_hours_to_deduct * saatlik_mesai_ucreti
                total_mesai_pay -= remaining_hours_to_deduct * saatlik_mesai_ucreti

            stats = {
                'toplam_mesai_saat': total_overtime_hours,
                'tahmini_odeme': total_mesai_pay + total_deducted_from_mesai_pay, # Gross overtime pay before hour deductions
                'total_deduction': total_deducted_from_mesai_pay,
                'net_mesai_odeme': max(0, total_mesai_pay),
                'is_negative': total_mesai_pay < 0
            }

            return render_template(
                'mesai_detay.html',
                person=person,
                rows=rows,
                stats=stats,
                selected_month=selected_month,
                selected_year=selected_year,
                saatlik_mesai_ucreti=saatlik_mesai_ucreti
            )
        except Exception as e:
            app.logger.exception('Mesailer detay error')
            return "Error: {}".format(e), 500

    @app.route('/mesailer/<int:personel_id>/update', methods=['POST'])
    @login_required
    def mesailer_detay_update(personel_id):
        try:
            year = int(request.form.get('year'))
            month = int(request.form.get('month'))
            
            # Formdan gelen tüm günleri al
            days = request.form.getlist('day[]')
            
            for d in days:
                day_int = int(d)
                target_date = date(year, month, day_int)
                
                # Mevcut kaydı bul veya yeni oluştur
                record = Puantaj.query.filter_by(PersonelID=personel_id, Tarih=target_date).first()
                if not record:
                    record = Puantaj(PersonelID=personel_id, Tarih=target_date)
                    db.session.add(record)
                
                # Form verilerini al
                record.Durum = request.form.get(f'durum_{d}')
                record.KesintiTuru = request.form.get(f'kesinti_turu_{d}', 'Maaş')
                
                def safe_float(v, default=0.0):
                    if not v: return default
                    try:
                        return float(str(v).replace(',', '.'))
                    except:
                        return default

                # Calculate default multiplier for this day to use if not provided
                # Only used if the form value is empty or invalid
                company = Company.query.first()
                settings = company.get_settings() if company else {}
                weekly_schedule = settings.get('weekly_schedule', {})
                public_holidays = settings.get('public_holidays', [])
                
                days_map = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                day_name = days_map[target_date.weekday()]
                day_config = weekly_schedule.get(day_name, {})
                is_public_holiday = any(holiday['date'] == target_date.strftime('%Y-%m-%d') for holiday in public_holidays)

                if is_public_holiday:
                    default_mult = float(next((h['multiplier'] for h in public_holidays if h['date'] == target_date.strftime('%Y-%m-%d')), 2.0))
                else:
                    ot_type = 'weekend' if day_name in ['saturday', 'sunday'] else 'weekday'
                    d_mult = 2.0 if ot_type == 'weekend' else 1.5
                    default_mult = float(day_config.get('multiplier', d_mult))

                record.MesaiSaati = safe_float(request.form.get(f'mesai_{d}'))
                record.EksikSaat = safe_float(request.form.get(f'eksik_{d}'))
                record.Carpan = safe_float(request.form.get(f'carpan_{d}'), default_mult)
            
            db.session.commit()
            flash('Mesai kayıtları başarıyla güncellendi.', 'success')
            return redirect(url_for('mesailer_detay', personel_id=personel_id, year=year, month=month))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Mesailer detay update error')
            flash(f'Hata: {str(e)}', 'danger')
            return redirect(url_for('mesailer_detay', personel_id=personel_id))

    @app.route('/borclar')
    @login_required
    def borclar():
        try:
            debts = Debt.query.filter_by(Aktif=True).order_by(Debt.VadeTarihi.asc()).all()
            banks = BankAccount.query.filter_by(Aktif=True).all()
            total_debts = sum(d.KalanTutar for d in debts)
            paid_debts_amount = sum(d.AnaTutar - d.KalanTutar for d in debts)
            overdue_debts_count = Debt.query.filter(Debt.VadeTarihi < date.today(), Debt.Durum != 'Ödendi', Debt.Aktif == True).count()
            # Ciro yapılabilecek çekleri getir
            customer_checks = Finance.query.filter(
                Finance.IslemTuru == 'Gelir',
                (Finance.Kategori.ilike('%çek%') | Finance.Kategori.ilike('%cek%') | Finance.Aciklama.ilike('%çek%') | Finance.Aciklama.ilike('%cek%')),
                ~Finance.Aciklama.ilike('%tahsil edildi%'),
                ~Finance.Aciklama.ilike('%silindi%'),
                ~Finance.Aciklama.ilike('%ciro edildi%')
            ).all()
            pre_selected_cari_id = request.args.get('cari_id')
            return render_template(
                'borclar.html',
                debts=debts,
                total_debts=total_debts,
                paid_debts_amount=paid_debts_amount,
                overdue_debts_count=overdue_debts_count,
                banks=banks,
                customer_checks=customer_checks,
                cariler=CariAccount.query.filter_by(Aktif=True).all(),
                pre_selected_cari_id=pre_selected_cari_id
            )
        except Exception as e:
            app.logger.exception('Borclar error')
            return "Error: {}".format(e), 500

    @app.route('/borclar/ekle', methods=['GET', 'POST'])
    @login_required
    def borclar_ekle():
        if request.method == 'POST':
            try:
                data = request.form
                tutar = parse_float(data.get('AnaTutar'))
                vade = datetime.strptime(data.get('VadeTarihi'), '%Y-%m-%d').date() if data.get('VadeTarihi') else None
                baslik_raw = (data.get('Baslik') or '').strip()
                if not baslik_raw:
                    parts = []
                    if data.get('BorcTuru'):
                        parts.append(data.get('BorcTuru'))
                    if data.get('BorcVeren'):
                        parts.append(data.get('BorcVeren'))
                    baslik_raw = ' - '.join(parts) or 'Borç'
                d = Debt(
                    Baslik=baslik_raw,
                    BorcVeren=data.get('BorcVeren'),
                    BorcTuru=data.get('BorcTuru'),
                    AnaTutar=tutar,
                    KalanTutar=tutar,
                    Tutar=tutar,
                    VadeTarihi=vade,
                    Aciklama=data.get('Aciklama'),
                    CariID=data.get('cari_id') if data.get('cari_id') else None,
                    Durum='Bekliyor'
                )
                db.session.add(d)
                db.session.commit()
                if d.CariID:
                    update_cari_balance(d.CariID)
                log_action("Ekleme", "Borç", f"{d.BorcVeren} - {d.AnaTutar:,.2f} TL")
                flash('Borç kaydı oluşturuldu.', 'success')
                return redirect(url_for('borclar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Borç ekle error')
                flash('Hata: {}'.format(e), 'danger')
        cariler = CariAccount.query.filter(or_(CariAccount.CariTipi == 'Tedarikçi', CariAccount.CariTipi == 'Her İkisi')).order_by(CariAccount.Unvan.asc()).all()
        return render_template('borc_ekle.html', cariler=cariler)

    @app.route('/borclar/<int:did>/edit', methods=['GET', 'POST'])
    @login_required
    def borclar_edit(did):
        d = Debt.query.get_or_404(did)
        if request.method == 'POST':
            try:
                data = request.form
                baslik_raw = (data.get('Baslik') or '').strip()
                if not baslik_raw:
                    parts = []
                    if data.get('BorcTuru'):
                        parts.append(data.get('BorcTuru'))
                    if data.get('BorcVeren'):
                        parts.append(data.get('BorcVeren'))
                    baslik_raw = ' - '.join(parts) or d.Baslik or 'Borç'
                d.Baslik = baslik_raw
                d.BorcVeren = data.get('BorcVeren')
                d.BorcTuru = data.get('BorcTuru')
                d.AnaTutar = parse_float(data.get('AnaTutar'))
                d.Tutar = d.AnaTutar
                d.KalanTutar = parse_float(data.get('KalanTutar'), d.KalanTutar)
                if data.get('VadeTarihi'):
                    d.VadeTarihi = datetime.strptime(data.get('VadeTarihi'), '%Y-%m-%d').date()
                old_cari_id = d.CariID
                d.Aciklama = data.get('Aciklama')
                d.Durum = data.get('Durum') or d.Durum
                d.CariID = data.get('cari_id') if data.get('cari_id') else None
                
                db.session.commit()
                if old_cari_id:
                    update_cari_balance(old_cari_id)
                if d.CariID and d.CariID != str(old_cari_id):
                    update_cari_balance(d.CariID)
                flash('Borç kaydı güncellendi.', 'success')
                return redirect(url_for('borclar'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Borç edit error')
                flash('Hata: {}'.format(e), 'danger')
        cariler = CariAccount.query.filter_by(Aktif=True).all()
        return render_template('borc_ekle.html', debt=d, cariler=cariler)

    @app.route('/borclar/<int:did>/pay', methods=['POST'])
    @login_required
    def borclar_pay(did):
        try:
            d = Debt.query.get_or_404(did)

            if d.KalanTutar <= 0 or d.Durum == 'Ödendi':
                flash('Bu borç zaten ödenmiş görünüyor.', 'info')
                return redirect(url_for('borclar'))

            data = request.form
            amount = parse_float(data.get('amount'))

            method = (data.get('payment_method') or '').lower()
            bank_id_raw = data.get('bank_id') or ''
            check_source_raw = (data.get('check_source') or 'own').lower()
            customer_check_id_raw = data.get('customer_check_id') or ''

            if method not in ('cash', 'bank', 'cek'):
                flash('Geçersiz ödeme yöntemi seçildi.', 'danger')
                return redirect(url_for('borclar'))

            bank = None
            if method == 'bank':
                try:
                    bank_id = int(bank_id_raw)
                except ValueError:
                    bank_id = None

                if not bank_id:
                    flash('Banka ile ödeme için bir hesap seçmelisiniz.', 'danger')
                    return redirect(url_for('borclar'))

                bank = BankAccount.query.get(bank_id)
                if not bank:
                    flash('Seçilen banka hesabı bulunamadı.', 'danger')
                    return redirect(url_for('borclar'))

            customer_check = None
            check_source = 'own'
            if method == 'cek':
                if check_source_raw == 'customer':
                    check_source = 'customer'
                    try:
                        customer_check_id = int(customer_check_id_raw)
                    except ValueError:
                        customer_check_id = None

                    if not customer_check_id:
                        flash('Müşteri çeki ile ödeme için bir çek seçmelisiniz.', 'danger')
                        return redirect(url_for('borclar'))

                    customer_check = Finance.query.get(customer_check_id)
                    if not customer_check:
                        flash('Seçilen müşteri çeki bulunamadı.', 'danger')
                        return redirect(url_for('borclar'))

                    kategori_lower = (customer_check.Kategori or '').lower()
                    if (customer_check.IslemTuru or '').lower() != 'gelir' or 'çek' not in kategori_lower:
                        flash('Seçilen kayıt geçerli bir müşteri çeki değil.', 'danger')
                        return redirect(url_for('borclar'))

                    try:
                        amount = float(customer_check.Tutar or 0)
                    except (TypeError, ValueError):
                        amount = 0.0

            if amount <= 0:
                flash('Geçerli bir ödeme tutarı girmelisiniz.', 'danger')
                return redirect(url_for('borclar'))

            if amount > d.KalanTutar:
                amount = d.KalanTutar

            remaining_before = float(d.KalanTutar or 0)
            remaining_after = remaining_before - amount
            if remaining_after <= 0.01:
                d.KalanTutar = 0.0
                d.Durum = 'Ödendi'
            else:
                d.KalanTutar = remaining_after
                if d.KalanTutar < d.AnaTutar:
                    d.Durum = 'Kısmi Ödendi'

            check_details = ""
            if method == 'cek':
                check_no = data.get('check_no')
                due_date = data.get('check_due_date')
                parts = []
                if check_no: parts.append(f"No:{check_no}")
                if due_date: parts.append(f"Vade:{due_date}")
                
                if check_source == 'customer' and customer_check:
                    customer_check.Aciklama = (customer_check.Aciklama or "") + f" - {d.BorcVeren} borcuna ciro edildi."
                    parts.append("Müşteri Çeki (Ciro)")
                else:
                    parts.append("Kendi Çekimiz")
                
                if parts:
                    check_details = " (" + ", ".join(parts) + ")"
                
                method_label = f"Çek{check_details}"

            desc_parts = []
            if d.BorcVeren:
                desc_parts.append(f"{d.BorcVeren} için borç ödemesi")
            desc_parts.append(f"Borç ID: {d.BorcID}")
            desc_parts.append(method_label)
            aciklama = " | ".join(desc_parts)

            kategori = 'Borç Ödemesi'
            if method == 'cek':
                kategori = 'Çek'
                cc_desc = customer_check.Aciklama or ''
                borc_id_tag = f"Borç ID: {d.BorcID}"
                if borc_id_tag not in (cc_desc or ''):
                    if cc_desc:
                        customer_check.Aciklama = cc_desc + f" | {borc_id_tag} için verildi"
                    else:
                        customer_check.Aciklama = f"{borc_id_tag} için verildi"
            elif method == 'cek' and check_source == 'own':
                own_check_no = (data.get('own_check_no') or '').strip()
                own_check_due_raw = data.get('own_check_due_date') or ''
                if own_check_due_raw:
                    try:
                        own_check_due_date = datetime.strptime(own_check_due_raw, '%Y-%m-%d').date()
                    except ValueError:
                        own_check_due_date = date.today()
                else:
                    own_check_due_date = date.today()

                desc_parts = []
                if own_check_no:
                    desc_parts.append(f"Çek No: {own_check_no}")
                desc_parts.append('Giden Çek')
                extra_parts = []
                if d.BorcVeren:
                    extra_parts.append(f"{d.BorcVeren} için borç ödemesi")
                extra_parts.append(f"Borç ID: {d.BorcID}")
                desc_parts.append(" | ".join(extra_parts))
                aciklama = " | ".join(desc_parts)

                if d.BorcVeren:
                    kategori = f"Çek - {d.BorcVeren}"
                else:
                    kategori = "Çek"

                f_rec = Finance(
                    Tarih=own_check_due_date,
                    Tutar=amount,
                    IslemTuru='Gider',
                    Kategori=kategori,
                    Aciklama=aciklama,
                    CariID=d.CariID
                )
                db.session.add(f_rec)
            else:
                desc_parts = []
                if d.BorcVeren:
                    desc_parts.append(f"{d.BorcVeren} için borç ödemesi")
                desc_parts.append(f"Borç ID: {d.BorcID}")
                desc_parts.append(method_label)
                aciklama = " | ".join(desc_parts)

                f_rec = Finance(
                    Tarih=date.today(),
                    Tutar=amount,
                    IslemTuru='Gider',
                    Kategori=kategori,
                    Aciklama=aciklama,
                    CariID=d.CariID
                )
                db.session.add(f_rec)

            if method == 'bank' and bank:
                bank.Bakiye = (bank.Bakiye or 0) - amount

            db.session.commit()
            log_action("İşlem", "Borç", f"{d.BorcVeren} borcuna {amount:,.2f} TL ödeme yapıldı.")
            
            if d.CariID:
                update_cari_balance(d.CariID)
            
            flash('Borç ödemesi kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Borç pay error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('borclar'))

    @app.route('/borclar/<int:did>/delete', methods=['POST'])
    @login_required
    def borclar_delete(did):
        try:
            d = Debt.query.get_or_404(did)
            cid = d.CariID
            d.Aktif = False # Soft delete
            db.session.commit()
            if cid:
                update_cari_balance(cid)
            log_action("Arşivleme", "Borç", f"{d.BorcVeren} borcu arşivlendi.")
            flash('Borç kaydı arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Borç delete error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('borclar'))

    @app.route('/finans/<int:fid>/delete', methods=['POST'])
    @login_required
    def finans_delete(fid):
        try:
            f = Finance.query.get_or_404(fid)
            kategori = f.Kategori
            
            # Eğer banka ile ilişkili bir işlemse bakiyeyi geri düzelt
            if f.BankaID:
                from models import BankAccount
                bank = BankAccount.query.get(f.BankaID)
                if bank:
                    if f.IslemTuru == 'Gelir':
                        bank.Bakiye -= f.Tutar
                    else:
                        bank.Bakiye += f.Tutar
            
            f.Aktif = False # Soft delete
            db.session.commit()
            
            if f.BankaID:
                update_bank_balance(f.BankaID)
                
            if f.CariID:
                update_cari_balance(f.CariID)
                
            log_action("Arşivleme", "Finans", f"{f.IslemTuru}: {kategori} - {f.Tutar:,.2f} TL arşivlendi.")
            flash('İşlem arşivlendi.', 'success')
            
            # Geldiği sayfaya yönlendir
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            if kategori and kategori.lower().startswith('kesinti'):
                return redirect(url_for('kesintiler'))
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Finans delete error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('dashboard'))

    @app.route('/kesintiler/<int:fid>/edit', methods=['GET', 'POST'])
    @login_required
    def kesintiler_edit(fid):
        f = Finance.query.get_or_404(fid)
        if request.method == 'POST':
            try:
                data = request.form
                personel_id_raw = data.get('personel_id') or ''
                deduction_type = (data.get('type') or '').strip()
                amount_raw = data.get('amount') or '0'
                date_raw = data.get('date') or ''
                installment_enabled = data.get('installment_enabled') == '1'
                installment_count_raw = data.get('installment_count') or ''
                installment_start_raw = data.get('installment_start') or ''
                description = (data.get('description') or '').strip()

                try:
                    amount = float(amount_raw.replace(',', '.'))
                except ValueError:
                    amount = 0.0

                if date_raw:
                    dt = datetime.strptime(date_raw, '%Y-%m-%d').date()
                else:
                    dt = date.today()

                personel_id = int(personel_id_raw) if personel_id_raw.isdigit() else None
                
                if installment_enabled:
                    installment_count = int(installment_count_raw) if installment_count_raw.isdigit() else None
                    if installment_start_raw:
                        installment_start = datetime.strptime(installment_start_raw, '%Y-%m-%d').date()
                    else:
                        installment_start = dt
                else:
                    installment_count = None
                    installment_start = None

                kategori_parts = ['Kesinti']
                kategori_parts.append(str(personel_id) if personel_id else '')
                kategori_parts.append(deduction_type or '')
                kategori_parts.append(str(installment_count) if installment_count else '')
                kategori_parts.append(installment_start.strftime('%Y-%m-%d') if installment_start else '')
                kategori = '|'.join(kategori_parts)

                payment_method = data.get('payment_method')
                bank_id_raw = data.get('bank_id')
                bank_id = int(bank_id_raw) if bank_id_raw and bank_id_raw.isdigit() else None

                # Eski ve yeni bankaları takibe al (bakiye güncellemesi için)
                old_bank_id = f.BankaID

                f.Tarih = dt
                f.Tutar = amount
                f.Kategori = kategori
                f.Aciklama = description
                f.BankaID = bank_id if payment_method == 'bank' else None
                
                db.session.commit()
                
                # Banka bakiyelerini güncelle
                if old_bank_id:
                    update_bank_balance(old_bank_id)
                if f.BankaID and f.BankaID != old_bank_id:
                    update_bank_balance(f.BankaID)

                flash('Kesinti güncellendi.', 'success')
                return redirect(url_for('kesintiler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Kesintiler edit error')
                flash('Hata: {}'.format(e), 'danger')
        
        parts = (f.Kategori or '').split('|')
        p_id = parts[1] if len(parts) > 1 else ''
        d_type = parts[2] if len(parts) > 2 else ''
        i_count = parts[3] if len(parts) > 3 else ''
        i_start = parts[4] if len(parts) > 4 else ''
        
        people = Personel.query.filter_by(Aktif=True).order_by(Personel.Ad.asc(), Personel.Soyad.asc()).all()
        banks = BankAccount.query.filter_by(Aktif=True).all()
        return render_template(
            'kesinti_ekle.html',
            people=people,
            entry=f,
            p_id=p_id,
            d_type=d_type,
            i_count=i_count,
            i_start=i_start,
            banks=banks
        )

    @app.route('/vergiler/add', methods=['GET', 'POST'])
    @login_required
    def vergiler_add():
        if request.method == 'POST':
            try:
                data = request.form
                vergi_tipi = data.get('vergi_tipi')
                kdv_turu = data.get('kdv_turu')
                tutar = float(data.get('tutar') or 0)
                tarih_str = data.get('tarih')
                durum = data.get('durum')
                aciklama = data.get('aciklama', '')

                dt = datetime.strptime(tarih_str, '%Y-%m-%d').date() if tarih_str else date.today()
                
                kategori = vergi_tipi
                if vergi_tipi == 'KDV' and kdv_turu:
                    kategori = f"KDV - {kdv_turu}"

                cat_lower = (kategori or '').lower()
                is_indirilecek_kdv = 'kdv' in cat_lower and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower))
                if is_indirilecek_kdv:
                    islem_turu = 'Bekleyen'
                else:
                    islem_turu = 'Gider' if durum == 'Ödendi' else 'Bekleyen'
                
                f = Finance(
                    Tarih=dt,
                    Tutar=tutar,
                    IslemTuru=islem_turu,
                    Kategori=kategori,
                    Aciklama=aciklama
                )
                db.session.add(f)
                db.session.commit()
                flash('Vergi kaydı başarıyla oluşturuldu.', 'success')
                return redirect(url_for('vergiler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Vergiler add error')
                flash(f'Hata: {e}', 'danger')
        
        return render_template('vergi_ekle.html', today=date.today().strftime('%Y-%m-%d'))

    @app.route('/vergiler')
    @login_required
    def vergiler():
        try:
            tax_query = Finance.query
            tax_query = tax_query.filter(
                func.lower(Finance.Kategori).like('%vergi%') |
                func.lower(Finance.Kategori).like('%kdv%') |
                func.lower(Finance.Kategori).like('%sgk%') |
                func.lower(Finance.Kategori).like('%stopaj%') |
                func.lower(Finance.Kategori).like('%muhtasar%')
            )

            period = (request.args.get('period') or '').strip()
            period_label = 'Tüm Dönemler'
            if period:
                try:
                    year, month = map(int, period.split('-'))
                    start_date = date(year, month, 1)
                    if month == 12:
                        end_date = date(year + 1, 1, 1)
                    else:
                        end_date = date(year, month + 1, 1)
                    tax_query = tax_query.filter(Finance.Tarih >= start_date, Finance.Tarih < end_date)
                    period_label = f"{month:02d}.{year}"
                except Exception:
                    period = ''

            entries = tax_query.order_by(Finance.Tarih.desc()).all()

            total_paid = 0.0
            pending_amount = 0.0
            for e in entries:
                amount = float(e.Tutar or 0)
                name_for_totals = e.Kategori or ''
                cat_lower_totals = (name_for_totals or '').lower()
                is_kdv_totals = 'kdv' in cat_lower_totals
                is_indirilecek_kdv_totals = is_kdv_totals and (('indirilecek' in cat_lower_totals) or ('i̇ndirilecek' in cat_lower_totals))
                if is_indirilecek_kdv_totals:
                    continue
                islem_totals = (e.IslemTuru or '').lower()
                if islem_totals == 'gider':
                    total_paid += amount
                elif islem_totals == 'bekleyen':
                    pending_amount += amount
            total_expected = total_paid + pending_amount

            category_totals = {}
            for e in entries:
                name = e.Kategori or 'Vergi'
                main_cat = name.split('-')[0].strip() if name else 'Diğer'
                key = main_cat or 'Diğer'
                if key not in category_totals:
                    category_totals[key] = {
                        'name': key,
                        'total': 0.0,
                        'paid': 0.0,
                        'pending': 0.0
                    }
                amount = float(e.Tutar or 0)
                cat_lower = (name or '').lower()
                is_kdv = 'kdv' in cat_lower
                is_indirilecek_kdv = is_kdv and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower))
                include_in_kdv_card = not (key == 'KDV' and is_indirilecek_kdv)
                if include_in_kdv_card:
                    category_totals[key]['total'] += amount
                    islem = (e.IslemTuru or '').lower()
                    if islem == 'gider':
                        category_totals[key]['paid'] += amount
                    elif islem == 'bekleyen':
                        category_totals[key]['pending'] += amount

            kdv_hesaplanan = 0.0
            kdv_indirilecek = 0.0
            for e in entries:
                name = e.Kategori or ''
                cat_lower = (name or '').lower()
                if 'kdv' in cat_lower:
                    amount = float(e.Tutar or 0)
                    if 'hesaplanan' in cat_lower:
                        kdv_hesaplanan += amount
                    elif ('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower):
                        kdv_indirilecek += amount
            kdv_net = kdv_hesaplanan - kdv_indirilecek

            banks = BankAccount.query.filter_by(Aktif=True).all()

            return render_template(
                'vergiler.html',
                entries=entries,
                total_paid=total_paid,
                pending_amount=pending_amount,
                next_month_estimate=total_expected,
                category_totals=list(category_totals.values()),
                kdv_hesaplanan=kdv_hesaplanan,
                kdv_indirilecek=kdv_indirilecek,
                kdv_net=kdv_net,
                selected_period=period,
                period_label=period_label,
                banks=banks
            )
        except Exception as e:
            app.logger.exception('Vergiler error')
            return "Error: {}".format(e), 500

    @app.route('/vergiler/<int:vid>/edit', methods=['GET', 'POST'])
    @login_required
    def vergiler_edit(vid):
        entry = Finance.query.get_or_404(vid)
        if request.method == 'POST':
            try:
                data = request.form
                vergi_tipi = data.get('vergi_tipi')
                kdv_turu = data.get('kdv_turu')
                tutar = float(data.get('tutar') or 0)
                tarih_str = data.get('tarih')
                durum = data.get('durum')
                aciklama = data.get('aciklama', '')

                dt = datetime.strptime(tarih_str, '%Y-%m-%d').date() if tarih_str else entry.Tarih
                
                kategori = vergi_tipi
                if vergi_tipi == 'KDV' and kdv_turu:
                    kategori = f"KDV - {kdv_turu}"

                cat_lower = (kategori or '').lower()
                is_indirilecek_kdv = 'kdv' in cat_lower and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower))
                if is_indirilecek_kdv:
                    islem_turu = 'Bekleyen'
                else:
                    islem_turu = 'Gider' if durum == 'Ödendi' else 'Bekleyen'
                
                entry.Tarih = dt
                entry.Tutar = tutar
                entry.IslemTuru = islem_turu
                entry.Kategori = kategori
                entry.Aciklama = aciklama
                
                db.session.commit()
                flash('Vergi kaydı güncellendi.', 'success')
                return redirect(url_for('vergiler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Vergiler edit error')
                flash(f'Hata: {e}', 'danger')
        
        return render_template('vergi_ekle.html', entry=entry, today=date.today().strftime('%Y-%m-%d'))

    @app.route('/vergiler/<int:vid>/pay', methods=['POST'])
    @login_required
    def vergiler_pay(vid):
        try:
            entry = Finance.query.get_or_404(vid)

            name = entry.Kategori or ''
            cat_lower = (name or '').lower()
            if 'kdv' in cat_lower and (('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower)):
                flash('İndirilecek KDV için ödeme işlemi yapılmaz. Bu kayıt sadece hesaplamada kullanılır.', 'info')
                return redirect(url_for('vergiler'))

            if (entry.IslemTuru or '').lower() == 'gider':
                flash('Bu vergi kaydı zaten ödendi olarak işaretli.', 'info')
                return redirect(url_for('vergiler'))

            method = (request.form.get('payment_method') or '').lower()
            bank_id_raw = request.form.get('bank_id') or ''

            if method not in ('cash', 'bank'):
                flash('Geçersiz ödeme yöntemi seçildi.', 'danger')
                return redirect(url_for('vergiler'))

            bank = None
            if method == 'bank':
                try:
                    bank_id = int(bank_id_raw)
                except ValueError:
                    bank_id = None

                if not bank_id:
                    flash('Banka ile ödeme için bir hesap seçmelisiniz.', 'danger')
                    return redirect(url_for('vergiler'))

                bank = BankAccount.query.get(bank_id)
                if not bank:
                    flash('Seçilen banka hesabı bulunamadı.', 'danger')
                    return redirect(url_for('vergiler'))

            entry.IslemTuru = 'Gider'

            method_label = 'Nakit'
            if method == 'bank' and bank:
                method_label = f"Banka: {bank.BankaAdi}"

            existing_desc = entry.Aciklama or ''
            if existing_desc:
                entry.Aciklama = f"{existing_desc} | Ödeme yöntemi: {method_label}"
            else:
                entry.Aciklama = f"Ödeme yöntemi: {method_label}"

            amount = float(entry.Tutar or 0)

            if method == 'bank' and bank:
                bank.Bakiye = (bank.Bakiye or 0) - amount

            db.session.commit()
            flash('Vergi kaydı ödeme bilgileriyle birlikte ödendi olarak işaretlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Vergiler pay error')
            flash(f'Hata: {e}', 'danger')
        return redirect(url_for('vergiler'))

    @app.route('/vergiler/kdv/pay', methods=['POST'])
    @login_required
    def vergiler_kdv_pay():
        try:
            period = (request.form.get('period') or '').strip()

            tax_query = Finance.query
            tax_query = tax_query.filter(func.lower(Finance.Kategori).like('%kdv%'))

            period_label = 'Tüm Dönemler'
            if period:
                try:
                    year, month = map(int, period.split('-'))
                    start_date = date(year, month, 1)
                    if month == 12:
                        end_date = date(year + 1, 1, 1)
                    else:
                        end_date = date(year, month + 1, 1)
                    tax_query = tax_query.filter(Finance.Tarih >= start_date, Finance.Tarih < end_date)
                    period_label = f"{month:02d}.{year}"
                except Exception:
                    period = ''

            entries = tax_query.all()

            kdv_hesaplanan = 0.0
            kdv_indirilecek = 0.0
            for e in entries:
                name = e.Kategori or ''
                cat_lower = (name or '').lower()
                if 'kdv' in cat_lower:
                    amount = float(e.Tutar or 0)
                    if 'hesaplanan' in cat_lower:
                        kdv_hesaplanan += amount
                    elif ('indirilecek' in cat_lower) or ('i̇ndirilecek' in cat_lower):
                        kdv_indirilecek += amount
            kdv_net = kdv_hesaplanan - kdv_indirilecek

            if kdv_net <= 0:
                flash('Bu dönem için ödenecek KDV bulunmuyor.', 'info')
                return redirect(url_for('vergiler'))

            method = (request.form.get('payment_method') or '').lower()
            bank_id_raw = request.form.get('bank_id') or ''

            if method not in ('cash', 'bank'):
                flash('Geçersiz ödeme yöntemi seçildi.', 'danger')
                return redirect(url_for('vergiler'))

            bank = None
            if method == 'bank':
                try:
                    bank_id = int(bank_id_raw)
                except ValueError:
                    bank_id = None

                if not bank_id:
                    flash('Banka ile ödeme için bir hesap seçmelisiniz.', 'danger')
                    return redirect(url_for('vergiler'))

                bank = BankAccount.query.get(bank_id)
                if not bank:
                    flash('Seçilen banka hesabı bulunamadı.', 'danger')
                    return redirect(url_for('vergiler'))

            method_label = 'Nakit'
            if method == 'bank' and bank:
                method_label = f"Banka: {bank.BankaAdi}"

            today_date = date.today()
            desc = f"{period_label} dönemi net KDV ödemesi ({method_label})"

            f = Finance(
                Tarih=today_date,
                Tutar=kdv_net,
                IslemTuru='Gider',
                Kategori='KDV - Ödeme',
                Aciklama=desc
            )
            db.session.add(f)

            if method == 'bank' and bank:
                bank.Bakiye = (bank.Bakiye or 0) - kdv_net

            db.session.commit()
            flash('Net KDV ödemesi kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Vergiler KDV pay error')
            flash(f'Hata: {e}', 'danger')
        return redirect(url_for('vergiler'))

    @app.route('/vergiler/<int:vid>/delete')
    @login_required
    def vergiler_delete(vid):
        try:
            entry = Finance.query.get_or_404(vid)
            entry.Aktif = False # Soft delete
            db.session.commit()
            flash('Vergi kaydı arşivlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Vergiler delete error')
            flash(f'Hata: {e}', 'danger')
        return redirect(url_for('vergiler'))

    @app.route('/cekler')
    @login_required
    def cekler():
        try:
            checks_query = Finance.query.filter(
                ((Finance.Kategori.ilike('%çek%')) |
                 (Finance.Kategori.ilike('%Çek%')) |
                 (Finance.Kategori.ilike('%ÇEK%')) |
                 (Finance.Kategori.ilike('%cek%')) |
                 (Finance.Kategori.ilike('%CEK%')) |
                 (Finance.Kategori.ilike('%karşılıksız%')) |
                 (Finance.Kategori.ilike('%KARŞILIKSIZ%')) |
                 (Finance.Kategori.ilike('%karsiliksiz%')) |
                 (Finance.Kategori.ilike('%KARSILIKSIZ%')) |
                 (Finance.Aciklama.ilike('%çek%')) |
                 (Finance.Aciklama.ilike('%Çek%')) |
                 (Finance.Aciklama.ilike('%ÇEK%')) |
                 (Finance.Aciklama.ilike('%cek%')) |
                 (Finance.Aciklama.ilike('%CEK%')) |
                 (Finance.Aciklama.ilike('%karşılıksız%')) |
                 (Finance.Aciklama.ilike('%KARŞILIKSIZ%')) |
                 (Finance.Aciklama.ilike('%karsiliksiz%')) |
                 (Finance.Aciklama.ilike('%KARSILIKSIZ%'))),
                ~Finance.Kategori.ilike('%KDV%'),
                ~Finance.Kategori.ilike('%indirilecek%'),
                ~Finance.Kategori.ilike('%i̇ndirilecek%'),
                ~Finance.Kategori.ilike('%hesaplanan%')
            )
            checks = checks_query.order_by(Finance.Tarih.desc()).all()

            banks = BankAccount.query.filter_by(Aktif=True).all()

            def normalize_tr(text):
                if not text: return ""
                text = text.lower()
                text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
                return text

            def is_collected(check):
                n_cat = normalize_tr(check.Kategori)
                n_desc = normalize_tr(check.Aciklama)
                # 'tahsil edildi' -> 'tahsil edildi' (normalized)
                return 'tahsil edildi' in n_cat or 'tahsil edildi' in n_desc or 'odendi' in n_cat or 'odendi' in n_desc

            def is_bad(check):
                n_cat = normalize_tr(check.Kategori)
                n_desc = normalize_tr(check.Aciklama)
                # 'karşılıksız' -> 'karsiliksiz' (normalized)
                return 'karsiliksiz' in n_cat or 'karsiliksiz' in n_desc

            def is_bank_verildi(c):
                n_cat = normalize_tr(c.Kategori)
                n_desc = normalize_tr(c.Aciklama)
                is_income = (c.IslemTuru or '').lower() == 'gelir'
                is_expense = (c.IslemTuru or '').lower() == 'gider'
                
                if is_income:
                    return 'bankaya verildi' in n_cat or 'bankaya verildi' in n_desc
                if is_expense:
                    return 'bankaya verilen' in n_cat or 'bankaya verilen' in n_desc
                return False

            bad_checks = [c for c in checks if is_bad(c)]
            bank_checks = [c for c in checks if not is_collected(c) and not is_bad(c) and is_bank_verildi(c)]

            customer_checks = []
            for c in checks:
                if is_collected(c) or is_bad(c):
                    continue
                if (c.IslemTuru or '').lower() != 'gelir':
                    continue
                n_cat = normalize_tr(c.Kategori)
                n_desc = normalize_tr(c.Aciklama)
                # 'verildi' kategoride varsa veya açıklamada 'ciro edildi' geçiyorsa müşteri çekidir
                if ('verildi' in n_cat and 'bankaya' not in n_cat) or ('ciro edildi' in n_desc):
                    customer_checks.append(c)

            portfolio_checks = [
                c for c in checks
                if (c.IslemTuru or '').lower() == 'gelir'
                and not is_collected(c)
                and not is_bad(c)
                and c not in customer_checks
                and c not in bank_checks
            ]

            payable_checks = [
                c for c in checks
                if (c.IslemTuru or '').lower() == 'gider'
                and not is_collected(c)
                and not is_bad(c)
                and c not in bank_checks
                and 'ciro' not in normalize_tr(c.Kategori)
                and 'ciro' not in normalize_tr(c.Aciklama)
            ]

            collected_checks = [c for c in checks if is_collected(c)]

            portfolio_total = sum((c.Tutar or 0) for c in portfolio_checks)
            payable_total = sum((c.Tutar or 0) for c in payable_checks)
            bank_total = sum((c.Tutar or 0) for c in bank_checks)
            customer_total = sum((c.Tutar or 0) for c in customer_checks)
            customer_count = len(customer_checks)
            collected_total = sum((c.Tutar or 0) for c in collected_checks)
            collected_count = len(collected_checks)
            bad_total = sum((c.Tutar or 0) for c in bad_checks)
            bad_count = len(bad_checks)

            today = date.today()

            return render_template(
                'cekler.html',
                checks=checks,
                portfolio_total=portfolio_total,
                incoming_count=len(portfolio_checks),
                payable_total=payable_total,
                outgoing_count=len(payable_checks),
                bank_total=bank_total,
                customer_total=customer_total,
                customer_count=customer_count,
                collected_total=collected_total,
                collected_count=collected_count,
                bad_total=bad_total,
                bad_count=bad_count,
                banks=banks,
                cariler=CariAccount.query.filter_by(Aktif=True).all(),
                today=today
            )
        except Exception as e:
            app.logger.exception('Cekler error')
            return "Error: {}".format(e), 500

    @app.route('/cekler/<int:fid>/bad', methods=['POST'])
    @login_required
    def cekler_bad(fid):
        try:
            check = Finance.query.get_or_404(fid)
            
            cat = check.Kategori or 'Çek'
            desc = check.Aciklama or ''
            
            tag = "Karşılıksız"
            if tag.lower() not in (cat or '').lower():
                check.Kategori = f"{cat} | {tag}" if cat else tag
            
            if tag.lower() not in (desc or '').lower():
                if desc:
                    check.Aciklama = f"{desc} | {tag}"
                else:
                    check.Aciklama = tag
                    
            db.session.commit()
            
            # Cari bakiyesini güncelle
            if check.CariID:
                update_cari_balance(check.CariID)
                
            log_action("İşlem", "Çek", f"{check.Aciklama} çek karşılıksız olarak işaretlendi.")
            flash('Çek karşılıksız olarak işaretlendi.', 'warning')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cekler bad error')
            flash(f'Hata: {e}', 'danger')
        return redirect(url_for('cekler'))

    @app.route('/cekler/<int:fid>/to_bank', methods=['POST'])
    @login_required
    def cekler_to_bank(fid):
        try:
            check = Finance.query.get_or_404(fid)

            if (check.IslemTuru or '').lower() != 'gelir':
                flash('Sadece gelen çekler bankaya verilebilir.', 'danger')
                return redirect(url_for('cekler'))

            bank_id_raw = request.form.get('bank_id') or ''
            try:
                bank_id = int(bank_id_raw)
            except ValueError:
                bank_id = None

            if not bank_id:
                flash('Lütfen bir banka hesabı seçin.', 'danger')
                return redirect(url_for('cekler'))

            bank = BankAccount.query.get(bank_id)
            if not bank:
                flash('Seçilen banka hesabı bulunamadı.', 'danger')
                return redirect(url_for('cekler'))

            amount = float(check.Tutar or 0)

            cat = check.Kategori or 'Çek'
            desc = check.Aciklama or ''
            bank_tag = f"Bankaya verildi: {bank.BankaAdi}"
            if bank_tag.lower() not in (cat or '').lower():
                check.Kategori = f"{cat} | {bank_tag}" if cat else bank_tag

            if 'Bankaya Verilen Çek' not in (desc or ''):
                extra = "Bankaya Verilen Çek"
                if desc:
                    check.Aciklama = f"{desc} | {extra}"
                else:
                    check.Aciklama = extra

            db.session.commit()
            log_action("İşlem", "Çek", f"{check.Aciklama} çek bankaya verildi: {bank.BankaAdi}")
            flash('Çek seçilen bankaya verildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cekler to_bank error')
        return redirect(url_for('cekler'))

    @app.route('/cekler/<int:fid>/to_customer', methods=['POST'])
    @login_required
    def cekler_to_customer(fid):
        try:
            check = Finance.query.get_or_404(fid)

            if (check.IslemTuru or '').lower() != 'gelir':
                flash('Sadece gelen çekler müşteriye verilebilir.', 'danger')
                return redirect(url_for('cekler'))

            cari_id_raw = request.form.get('cari_id') or ''
            try:
                cari_id = int(cari_id_raw)
            except ValueError:
                cari_id = None

            if not cari_id:
                flash('Lütfen bir müşteri seçin.', 'danger')
                return redirect(url_for('cekler'))

            cari = CariAccount.query.get(cari_id)
            if not cari:
                flash('Seçilen müşteri bulunamadı.', 'danger')
                return redirect(url_for('cekler'))

            # Update check status
            cat = check.Kategori or 'Çek'
            desc = check.Aciklama or ''
            
            verildi_tag = f"Verildi: {cari.Unvan}"
            if verildi_tag.lower() not in (cat or '').lower():
                check.Kategori = f"{cat} | {verildi_tag}" if cat else verildi_tag

            if 'Müşteriye Verildi' not in (desc or ''):
                extra = f"{cari.Unvan} isimli cariye ciro edildi."
                if desc:
                    check.Aciklama = f"{desc} | {extra}"
                else:
                    check.Aciklama = extra

            # Cari hesabına ödeme (Gider) olarak işle
            payment_desc = f"Çek Cirosu - {check.Aciklama}"
            ciro_payment = Finance(
                Tarih=date.today(),
                Tutar=amount,
                IslemTuru='Gider',
                Kategori='Çek Cirosu',
                Aciklama=payment_desc,
                CariID=cari.CariID
            )
            db.session.add(ciro_payment)

            db.session.commit()
            
            # Cari bakiyesini güncelle
            update_cari_balance(cari.CariID)
            
            log_action("İşlem", "Çek", f"{check.Aciklama} çek müşteriye verildi: {cari.Unvan}")
            flash(f'Çek {cari.Unvan} isimli cariye verildi ve cari hesabına işlendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cekler to_customer error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('cekler'))

    @app.route('/cekler/<int:fid>/tahsil', methods=['POST'])
    @login_required
    def cekler_tahsil(fid):
        try:
            check = Finance.query.get_or_404(fid)

            cat = check.Kategori or ''
            desc = check.Aciklama or ''
            cat_lower = cat.lower()
            desc_lower = desc.lower()

            if 'tahsil edildi' in cat_lower or 'tahsil edildi' in desc_lower:
                flash('Bu çek zaten tahsil edilmiş.', 'info')
                return redirect(url_for('cekler'))

            if 'bankaya verildi' not in cat_lower and 'bankaya verilen çek' not in desc_lower:
                flash('Sadece bankaya verilen çekler tahsil edilebilir.', 'danger')
                return redirect(url_for('cekler'))

            bank_name = None
            if 'bankaya verildi' in cat_lower:
                parts = [p.strip() for p in cat.split('|') if p.strip()]
                for part in parts:
                    p_lower = part.lower()
                    if p_lower.startswith('bankaya verildi'):
                        if ':' in part:
                            bank_name = part.split(':', 1)[1].strip()
                        else:
                            bank_name = part.replace('Bankaya verildi', '').replace(':', '').strip()
                        break

            if not bank_name:
                flash('Bu çek için banka bilgisi bulunamadı.', 'danger')
                return redirect(url_for('cekler'))

            bank = BankAccount.query.filter(func.lower(BankAccount.BankaAdi) == bank_name.lower()).first()
            if not bank:
                bank = BankAccount.query.filter(func.lower(BankAccount.BankaAdi).like('%' + bank_name.lower() + '%')).first()
            if not bank:
                flash('İlgili banka hesabı bulunamadı.', 'danger')
                return redirect(url_for('cekler'))

            amount = float(check.Tutar or 0)
            bank.Bakiye = (bank.Bakiye or 0) + amount

            desc = check.Aciklama or ''
            desc_lower = desc.lower()
            if 'tahsil edildi' not in desc_lower:
                extra = 'Tahsil edildi'
                if desc:
                    check.Aciklama = desc + ' | ' + extra
                else:
                    check.Aciklama = extra

            db.session.commit()
            log_action("İşlem", "Çek", f"{check.Aciklama} çek tahsil edildi.")
            flash('Çek tahsil edildi ve banka bakiyesine eklendi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cekler tahsil error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('cekler'))

    @app.route('/cekler/<int:fid>/pay', methods=['POST'])
    @login_required
    def cekler_pay(fid):
        try:
            check = Finance.query.get_or_404(fid)

            if (check.IslemTuru or '').lower() != 'gider':
                flash('Sadece giden çekler için ödeme yapılabilir.', 'danger')
                return redirect(url_for('cekler'))

            cat = check.Kategori or ''
            desc = check.Aciklama or ''
            cat_lower = cat.lower()
            desc_lower = desc.lower()

            if 'ödendi' in cat_lower or 'ödendi' in desc_lower:
                flash('Bu çek zaten ödenmiş görünüyor.', 'info')
                return redirect(url_for('cekler'))

            data = request.form
            method = (data.get('payment_method') or '').lower()
            bank_id_raw = data.get('bank_id') or ''

            if method not in ('cash', 'bank'):
                flash('Geçersiz ödeme yöntemi seçildi.', 'danger')
                return redirect(url_for('cekler'))

            bank = None
            if method == 'bank':
                try:
                    bank_id = int(bank_id_raw)
                except ValueError:
                    bank_id = None

                if not bank_id:
                    flash('Banka ile ödeme için bir hesap seçmelisiniz.', 'danger')
                    return redirect(url_for('cekler'))

                bank = BankAccount.query.get(bank_id)
                if not bank:
                    flash('Seçilen banka hesabı bulunamadı.', 'danger')
                    return redirect(url_for('cekler'))

            try:
                amount = float(check.Tutar or 0)
            except (TypeError, ValueError):
                amount = 0.0

            if amount <= 0:
                flash('Geçerli bir çek tutarı bulunamadı.', 'danger')
                return redirect(url_for('cekler'))

            if 'ödendi' not in cat_lower:
                if cat:
                    check.Kategori = f"{cat} | Ödendi"
                else:
                    check.Kategori = 'Ödendi'

            method_label = 'Nakit'
            if method == 'bank' and bank:
                method_label = f"Banka: {bank.BankaAdi}"

            existing_desc = check.Aciklama or ''
            tag = f"Ödeme yöntemi: {method_label}"
            if tag not in (existing_desc or ''):
                if existing_desc:
                    check.Aciklama = existing_desc + ' | ' + tag
                else:
                    check.Aciklama = tag

            if method == 'bank' and bank:
                bank.Bakiye = (bank.Bakiye or 0) - amount

            db.session.commit()
            log_action("İşlem", "Çek", f"{check.Aciklama} çek ödendi.")
            flash('Çek ödemesi kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.exception('Cekler pay error')
            flash('Hata: {}'.format(e), 'danger')
        return redirect(url_for('cekler'))

    @app.route('/cekler/add', methods=['GET', 'POST'])
    @login_required
    def cekler_add():
        if request.method == 'POST':
            try:
                data = request.form
                status = (data.get('status') or '').lower()
                cek_no = (data.get('cek_no') or '').strip()
                payee = (data.get('payee') or '').strip()
                amount_raw = data.get('amount') or '0'
                bank_name = (data.get('check_bank') or '').strip()
                desc_extra = (data.get('description') or '').strip()
                due_raw = data.get('due_date') or ''

                try:
                    amount = float(amount_raw.replace(',', '.'))
                except ValueError:
                    amount = 0.0

                if due_raw:
                    try:
                        due_date = datetime.strptime(due_raw, '%Y-%m-%d').date()
                    except ValueError:
                        due_date = date.today()
                else:
                    due_date = date.today()

                if status == 'gelen':
                    islem_turu = 'Gelir'
                    durum_text = 'Gelen Çek'
                elif status == 'banka':
                    islem_turu = 'Gelir' # Fixed: Moving an income check to bank is still income
                    durum_text = 'Bankaya Verilen Çek'
                else:
                    islem_turu = 'Gider'
                    durum_text = 'Giden Çek'

                if payee:
                    kategori = f"Çek - {payee}"
                else:
                    kategori = "Çek"

                if status == 'banka' and bank_name:
                    kategori = f"{kategori} | Bankaya verildi: {bank_name}"

                desc_parts = []
                if cek_no:
                    desc_parts.append(f"Çek No: {cek_no}")
                desc_parts.append(durum_text)
                if bank_name:
                    desc_parts.append(f"Banka: {bank_name}")
                if desc_extra:
                    desc_parts.append(desc_extra)
                aciklama = " | ".join(desc_parts)

                record = Finance(
                    Tarih=due_date,
                    Tutar=amount,
                    IslemTuru=islem_turu,
                    Kategori=kategori,
                    Aciklama=aciklama,
                    CariID=data.get('cari_id') if data.get('cari_id') else None
                )
                db.session.add(record)
                db.session.commit()
                log_action("Ekleme", "Çek", f"{cek_no} nolu {amount:,.2f} TL tutarındaki çek eklendi.")

                # Handle file uploads
                if 'files[]' in request.files:
                    files = request.files.getlist('files[]')
                    descriptions = request.form.getlist('descriptions[]')
                    for idx, file in enumerate(files):
                        if file and file.filename:
                            try:
                                filename = secure_filename(file.filename)
                                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                                save_dir = Path(config.UPLOADS_DIR) / 'Cek'
                                save_dir.mkdir(parents=True, exist_ok=True)
                                file_path = save_dir / unique_filename
                                file.save(str(file_path))
                                
                                doc = Document(
                                    DosyaYolu=f"Cek/{unique_filename}",
                                    DosyaAdi=filename,
                                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else None,
                                    Aciklama=descriptions[idx] if idx < len(descriptions) else 'Çek Görseli',
                                    RelationType='Cek',
                                    RelationID=record.FinansID
                                )
                                db.session.add(doc)
                            except Exception as e:
                                app.logger.error(f"File upload error during check creation: {e}")
                    db.session.commit()

                if record.CariID:
                    update_cari_balance(record.CariID)
                
                flash('Çek kaydı eklendi.', 'success')
                return redirect(url_for('cekler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Cekler add error')
                flash('Hata: {}'.format(e), 'danger')
        return render_template('cek_ekle.html',
                               status='gelen',
                               cek_no='',
                               payee='',
                               amount='',
                               due_date_str=date.today().strftime('%Y-%m-%d'),
                               desc_extra='',
                               bank_name='',
                               documents=[],
                               cariler=CariAccount.query.filter_by(Aktif=True).all())

    @app.route('/cekler/<int:fid>/edit', methods=['GET', 'POST'])
    @login_required
    def cekler_edit(fid):
        record = Finance.query.get_or_404(fid)
        if request.method == 'POST':
            try:
                data = request.form
                status = (data.get('status') or '').lower()
                cek_no = (data.get('cek_no') or '').strip()
                payee = (data.get('payee') or '').strip()
                amount_raw = data.get('amount') or '0'
                bank_name = (data.get('check_bank') or '').strip()
                desc_extra = (data.get('description') or '').strip()
                due_raw = data.get('due_date') or ''

                try:
                    amount = float(amount_raw.replace(',', '.'))
                except ValueError:
                    amount = 0.0

                if due_raw:
                    try:
                        due_date = datetime.strptime(due_raw, '%Y-%m-%d').date()
                    except ValueError:
                        due_date = date.today()
                else:
                    due_date = date.today()

                if status == 'gelen':
                    islem_turu = 'Gelir'
                    durum_text = 'Gelen Çek'
                elif status == 'banka':
                    islem_turu = 'Gelir'
                    durum_text = 'Bankaya Verilen Çek'
                else:
                    islem_turu = 'Gider'
                    durum_text = 'Giden Çek'

                if payee:
                    kategori = f"Çek - {payee}"
                else:
                    kategori = "Çek"

                if status == 'banka' and bank_name:
                    kategori = f"{kategori} | Bankaya verildi: {bank_name}"

                desc_parts = []
                if cek_no:
                    desc_parts.append(f"Çek No: {cek_no}")
                desc_parts.append(durum_text)
                if bank_name:
                    desc_parts.append(f"Banka: {bank_name}")
                if desc_extra:
                    desc_parts.append(desc_extra)
                aciklama = " | ".join(desc_parts)

                record.Tarih = due_date
                record.Tutar = amount
                record.IslemTuru = islem_turu
                record.Kategori = kategori
                record.Aciklama = aciklama
                record.CariID = data.get('cari_id') if data.get('cari_id') else None

                db.session.commit()
                log_action("Güncelleme", "Çek", f"{record.Aciklama} nolu çek güncellendi.")
                if record.CariID:
                    update_cari_balance(record.CariID)

                # Handle file uploads
                if 'files[]' in request.files:
                    files = request.files.getlist('files[]')
                    descriptions = request.form.getlist('descriptions[]')
                    for idx, file in enumerate(files):
                        if file and file.filename:
                            try:
                                filename = secure_filename(file.filename)
                                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                                save_dir = Path(config.UPLOADS_DIR) / 'Cek'
                                save_dir.mkdir(parents=True, exist_ok=True)
                                file_path = save_dir / unique_filename
                                file.save(str(file_path))
                                
                                doc = Document(
                                    DosyaYolu=f"Cek/{unique_filename}",
                                    DosyaAdi=filename,
                                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else None,
                                    Aciklama=descriptions[idx] if idx < len(descriptions) else 'Çek Görseli',
                                    RelationType='Cek',
                                    RelationID=record.FinansID
                                )
                                db.session.add(doc)
                            except Exception as e:
                                app.logger.error(f"File upload error during check update: {e}")
                    db.session.commit()

                flash('Çek kaydı güncellendi.', 'success')
                return redirect(url_for('cekler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Cekler edit error')
                flash('Hata: {}'.format(e), 'danger')

        kategori = record.Kategori or ''
        payee = ''
        if kategori.startswith('Çek -'):
            payee = kategori.split('Çek -', 1)[1].strip()

        cek_no = ''
        status = 'gelen'
        desc_extra = ''
        bank_name = ''

        aciklama = record.Aciklama or ''
        if aciklama:
            parts = [p.strip() for p in aciklama.split('|') if p.strip()]
            if parts and parts[0].startswith('Çek No:'):
                cek_no = parts[0].split('Çek No:', 1)[1].strip()
                parts = parts[1:]
            durum_index = None
            bank_index = None
            for idx, p in enumerate(parts):
                lower_p = p.lower()
                if p.startswith('Banka:'):
                    bank_index = idx
                    continue
                if 'bankaya verilen çek' in lower_p:
                    status = 'banka'
                    durum_index = idx
                    break
                if 'gelen çek' in lower_p:
                    status = 'gelen'
                    durum_index = idx
                    break
                if 'giden çek' in lower_p:
                    status = 'giden'
                    durum_index = idx
                    break
            if bank_index is not None and 0 <= bank_index < len(parts):
                bank_part = parts.pop(bank_index)
                bank_name = bank_part.split('Banka:', 1)[1].strip() if ':' in bank_part else bank_part.replace('Banka', '').strip()
            if durum_index is not None and 0 <= durum_index < len(parts):
                parts.pop(durum_index)
            else:
                islem = (record.IslemTuru or '').lower()
                if islem == 'gelir':
                    status = 'gelen'
                else:
                    status = 'giden'
            desc_extra = ' | '.join(parts) if parts else ''

        if record.Tarih:
            due_date_str = record.Tarih.strftime('%Y-%m-%d')
        else:
            due_date_str = date.today().strftime('%Y-%m-%d')

        # Get documents
        documents = Document.query.filter_by(RelationType='Cek', RelationID=fid).all()

        return render_template('cek_ekle.html',
                               entry=record,
                               status=status,
                               cek_no=cek_no,
                               payee=payee,
                               amount=record.Tutar,
                               due_date_str=due_date_str,
                               bank_name=bank_name,
                               desc_extra=desc_extra,
                               documents=documents,
                               cariler=CariAccount.query.filter_by(Aktif=True).all())

    @app.route('/kesintiler')
    @login_required
    def kesintiler():
        try:
            query = Finance.query.filter(func.lower(Finance.Kategori).like('kesinti%'))
            records = query.order_by(Finance.Tarih.desc()).all()

            today = date.today()
            deductions = []

            for rec in records:
                kategori = rec.Kategori or ''
                parts = kategori.split('|')
                if not parts or parts[0].strip().lower() != 'kesinti':
                    continue

                personel_id = None
                deduction_type = None
                installment_count = None
                installment_start = None

                if len(parts) > 1 and parts[1].strip().isdigit():
                    personel_id = int(parts[1].strip())
                if len(parts) > 2:
                    deduction_type = parts[2].strip() or None
                if len(parts) > 3 and parts[3].strip().isdigit():
                    installment_count = int(parts[3].strip())
                if len(parts) > 4 and parts[4].strip():
                    try:
                        installment_start = datetime.strptime(parts[4].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        installment_start = rec.Tarih

                current_installment = None
                if installment_count and installment_count > 1 and installment_start:
                    months = (today.year - installment_start.year) * 12 + (today.month - installment_start.month)
                    current_installment = months + 1
                    if current_installment < 1:
                        current_installment = 1
                    if current_installment > installment_count:
                        current_installment = installment_count

                person = Personel.query.get(personel_id) if personel_id else None
                if person:
                    full_name = f"{person.Ad} {person.Soyad}"
                    initials = ''.join([part[0] for part in [person.Ad, person.Soyad] if part][:2]).upper()
                    pid = person.PersonelID
                else:
                    full_name = 'Bilinmeyen Personel'
                    initials = 'BP'
                    pid = None

                deductions.append({
                    'record': rec,
                    'personel_id': pid,
                    'full_name': full_name,
                    'initials': initials,
                    'type': deduction_type or 'Diğer',
                    'installment_count': installment_count,
                    'current_installment': current_installment
                })

            return render_template('kesintiler.html', deductions=deductions)
        except Exception as e:
            app.logger.exception('Kesintiler error')
            return "Error: {}".format(e), 500

    @app.route('/kesintiler/add', methods=['GET', 'POST'])
    @login_required
    def kesintiler_add():
        if request.method == 'POST':
            try:
                data = request.form
                personel_id_raw = data.get('personel_id') or ''
                deduction_type = (data.get('type') or '').strip()
                amount_raw = data.get('amount') or '0'
                date_raw = data.get('date') or ''
                installment_enabled = data.get('installment_enabled') == '1'
                installment_count_raw = data.get('installment_count') or ''
                installment_start_raw = data.get('installment_start') or ''
                description = (data.get('description') or '').strip()

                try:
                    amount = float(amount_raw.replace(',', '.'))
                except ValueError:
                    amount = 0.0

                if date_raw:
                    try:
                        dt = datetime.strptime(date_raw, '%Y-%m-%d').date()
                    except ValueError:
                        dt = date.today()
                else:
                    dt = date.today()

                personel_id = int(personel_id_raw) if personel_id_raw.isdigit() else None
                person = Personel.query.get(personel_id) if personel_id else None

                if installment_enabled:
                    try:
                        installment_count = int(installment_count_raw)
                    except ValueError:
                        installment_count = None
                    if installment_start_raw:
                        try:
                            installment_start = datetime.strptime(installment_start_raw, '%Y-%m-%d').date()
                        except ValueError:
                            installment_start = dt
                    else:
                        installment_start = dt
                else:
                    installment_count = None
                    installment_start = None

                kategori_parts = ['Kesinti']
                kategori_parts.append(str(person.PersonelID) if person else '')
                kategori_parts.append(deduction_type or '')
                kategori_parts.append(str(installment_count) if installment_count else '')
                kategori_parts.append(installment_start.strftime('%Y-%m-%d') if installment_start else '')
                kategori = '|'.join(kategori_parts)

                if not description:
                    if person:
                        description = f"{deduction_type or 'Kesinti'} - {person.Ad} {person.Soyad}"
                    else:
                        description = deduction_type or 'Kesinti'

                payment_method = data.get('payment_method')
                bank_id_raw = data.get('bank_id')
                bank_id = int(bank_id_raw) if bank_id_raw and bank_id_raw.isdigit() else None

                record = Finance(
                    Tarih=dt,
                    Tutar=amount,
                    IslemTuru='Gider',
                    Kategori=kategori,
                    Aciklama=description,
                    BankaID=bank_id if payment_method == 'bank' else None
                )
                db.session.add(record)
                
                # Eğer bankadan ödeniyorsa banka bakiyesini de düşür
                if payment_method == 'bank' and bank_id:
                    bank = BankAccount.query.get(bank_id)
                    if bank:
                        bank.Bakiye -= amount
                
                db.session.commit()
                log_action("Ekleme", "Kesinti", f"{person.Ad} {person.Soyad}: {deduction_type} - {amount:,.2f} TL")
                flash('Kesinti kaydı eklendi.', 'success')
                return redirect(url_for('kesintiler'))
            except Exception as e:
                db.session.rollback()
                app.logger.exception('Kesintiler add error')
                flash('Hata: {}'.format(e), 'danger')
        people = Personel.query.filter_by(Aktif=True).order_by(Personel.Ad.asc(), Personel.Soyad.asc()).all()
        banks = BankAccount.query.filter_by(Aktif=True).all()
        return render_template('kesinti_ekle.html', people=people, banks=banks)


    # Bordro (Payroll) - converts React useState dynamic logic to server-side calculation
    @app.route('/bordro/pay', methods=['POST'])
    @login_required
    def bordro_pay():
        try:
            personel_id = request.form.get('personel_id')
            total_amount = float(request.form.get('amount') or 0)
            month = int(request.form.get('month'))
            year = int(request.form.get('year'))
            
            payment_method = request.form.get('payment_method')
            bank_id_raw = request.form.get('bank_id')
            bank_id = int(bank_id_raw) if bank_id_raw and bank_id_raw.isdigit() else None
            
            p = Personel.query.get_or_404(personel_id)
            
            # Check if already paid
            kategori_pattern = f"Maaş Ödemesi|{personel_id}|{month}|{year}"
            existing = Finance.query.filter(Finance.Kategori == kategori_pattern).first()
            
            if existing:
                flash(f'{p.Ad} {p.Soyad} için bu ayın maaşı zaten ödenmiş.', 'warning')
                return redirect(url_for('bordro', month=month, year=year))
            
            months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            month_name = months_tr[month-1]
            
            # Helper to create finance entry
            def create_finance_entry(amt, b_id, suffix=''):
                desc = f"{p.Ad} {p.Soyad} - {month_name} {year} Maaş Ödemesi{suffix}"
                f = Finance(
                    Tarih=date.today(),
                    Tutar=amt,
                    IslemTuru='Gider',
                    Kategori=kategori_pattern,
                    Aciklama=desc,
                    BankaID=b_id
                )
                db.session.add(f)
                if b_id:
                    bank = BankAccount.query.get(b_id)
                    if bank:
                        bank.Bakiye -= amt

            if payment_method == 'mixed':
                cash_amt = float(request.form.get('mixed_cash_amount') or 0)
                bank_amt = float(request.form.get('mixed_bank_amount') or 0)
                
                # Check sums
                if abs((cash_amt + bank_amt) - total_amount) > 0.01:
                    total_amount = cash_amt + bank_amt # Use the sum from inputs

                if cash_amt > 0:
                    create_finance_entry(cash_amt, None, ' (Nakit)')
                if bank_amt > 0:
                    create_finance_entry(bank_amt, bank_id, ' (Banka)')
            elif payment_method == 'bank':
                create_finance_entry(total_amount, bank_id)
            else: # cash
                create_finance_entry(total_amount, None)

            db.session.commit()
            log_action("İşlem", "Bordro", f"{p.Ad} {p.Soyad} için {total_amount:,.2f} TL maaş ödemesi yapıldı.")
            flash(f'{p.Ad} {p.Soyad} için {total_amount:,.2f} TL maaş ödemesi kaydedildi.', 'success')
        except Exception as e:
            db.session.rollback()
        return redirect(url_for('bordro', month=month, year=year))

    @app.route('/bordro')
    @login_required
    @roles_required('admin', 'ik')
    def bordro():
        try:
            req_month = request.args.get('month', type=int)
            req_year = request.args.get('year', type=int)
            
            today = date.today()
            target_month = req_month if req_month else today.month
            target_year = req_year if req_year else today.year
            target_date = date(target_year, target_month, 1)

            company = Company.query.first()
            settings = company.get_settings() if company else {}
            weekly_schedule = settings.get('weekly_schedule', {})
            public_holidays = settings.get('public_holidays', [])
            monthly_hours = float(settings.get('monthly_working_hours', 225))
            daily_net_work_hours = monthly_hours / 30.0

            deduction_records = Finance.query.filter(func.lower(Finance.Kategori).like('kesinti%')).all()
            person_deductions = {}
            for rec in deduction_records:
                kategori = rec.Kategori or ''
                parts = kategori.split('|')
                if not parts or parts[0].strip().lower() != 'kesinti':
                    continue

                personel_id = None
                installment_count = None
                installment_start = None

                if len(parts) > 1 and parts[1].strip().isdigit():
                    personel_id = int(parts[1].strip())
                if len(parts) > 3 and parts[3].strip().isdigit():
                    installment_count = int(parts[3].strip())
                if len(parts) > 4 and parts[4].strip():
                    try:
                        installment_start = datetime.strptime(parts[4].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        installment_start = rec.Tarih

                if not personel_id:
                    continue

                amount = float(rec.Tutar or 0)
                deduction_amount = 0.0

                if installment_count and installment_count > 1 and installment_start:
                    months = (target_year - installment_start.year) * 12 + (target_month - installment_start.month)
                    installment_index = months + 1
                    if 1 <= installment_index <= installment_count:
                        deduction_amount = amount / float(installment_count)
                else:
                    if rec.Tarih and rec.Tarih.year == target_year and rec.Tarih.month == target_month:
                        deduction_amount = amount

                if deduction_amount > 0 and personel_id:
                    person_deductions[personel_id] = person_deductions.get(personel_id, 0.0) + deduction_amount

            results = []
            people = Personel.query.filter_by(Aktif=True).all()
            
            # Get all salary payments for this month to check status
            payment_records = Finance.query.filter(
                Finance.Kategori.like(f'Maaş Ödemesi|%|{target_month}|{target_year}')
            ).all()
            paid_personel_ids = set()
            for pr in payment_records:
                parts = pr.Kategori.split('|')
                if len(parts) > 1 and parts[1].isdigit():
                    paid_personel_ids.add(int(parts[1]))

            for p in people:
                payroll_data = services.get_payroll_for_person(p, target_date, weekly_schedule, public_holidays, monthly_hours, daily_net_work_hours, person_deductions)
                payroll_data['is_paid'] = p.PersonelID in paid_personel_ids
                payroll_data['month'] = target_month
                payroll_data['year'] = target_year
                results.append(payroll_data)
            
            banks = BankAccount.query.filter_by(Aktif=True).all()
            years = range(today.year - 2, today.year + 2)
            
            return render_template('bordro.html', results=results, current_month=target_month, current_year=target_year, banks=banks, years=years)
        except Exception as e:
            app.logger.exception('Bordro error')
            flash(f"Hata: {e}", "danger")
            return redirect(url_for('dashboard'))

    @app.route('/bordro/<int:personel_id>/send_email')
    @login_required
    def bordro_send_email(personel_id):
        """Bordro pusulasını personelin e-postasına gönderir"""
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        p = Personel.query.get_or_404(personel_id)
        if not p.Email:
            flash(f'{p.Ad} {p.Soyad} için e-posta adresi tanımlı değil.', 'warning')
            return redirect(request.referrer)

        # Basit bir HTML içeriği oluştur (Pusula şablonundan esinlenen)
        company = Company.query.first()
        company_name = company.SirketAdi if company else "ERP Sistemi"
        
        subject = f"Maaş Bordrosu - {month}/{year} - {company_name}"
        body = f"""
        <html>
            <body>
                <h2>Maaş Bordrosu</h2>
                <p>Sayın {p.Ad} {p.Soyad},</p>
                <p>{month}/{year} dönemine ait maaş bordronuz ekte veya aşağıda bilgilerinize sunulmuştur.</p>
                <p>İyi çalışmalar dileriz.</p>
                <br>
                <p><b>{company_name} İnsan Kaynakları</b></p>
            </body>
        </html>
        """
        
        # Gelecekte buraya PDF üretilip attachment olarak eklenebilir. 
        # Şimdilik sadece bilgilendirme gönderiyoruz.
        success, msg = services.send_email(subject, body, p.Email)
        if success:
            flash(f'Bordro {p.Email} adresine başarıyla gönderildi.', 'success')
        else:
            flash(f'E-posta gönderim hatası: {msg}', 'error')
            
        return redirect(request.referrer)

    @app.route('/bordro/whatsapp')
    @login_required
    @roles_required('admin', 'ik')
    def bordro_whatsapp():
        """WhatsApp Web üzerinden mesaj taslağı oluşturur"""
        phone = request.args.get('phone', '')
        message = request.args.get('message', '')
        
        if not phone:
            flash('Telefon numarası bulunamadı.', 'warning')
            return redirect(request.referrer)
            
        # Numaradaki boşlukları vs temizle
        phone = "".join(filter(str.isdigit, phone))
        if phone.startswith('0'):
            phone = '9' + phone
        elif not phone.startswith('9'):
            phone = '90' + phone

        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        
        wa_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}"
        return redirect(wa_url)

    @app.route('/bordro/<int:personel_id>/pusula')
    @login_required
    def bordro_pusula(personel_id):
        try:
            today = date.today()
            company = Company.query.first()
            p = Personel.query.get_or_404(personel_id)
            
            settings = company.get_settings() if company else {}
            weekly_schedule = settings.get('weekly_schedule', {})
            public_holidays = settings.get('public_holidays', [])
            monthly_hours = float(settings.get('monthly_working_hours', 225))
            daily_net_work_hours = monthly_hours / 30.0

            deduction_records = Finance.query.filter(func.lower(Finance.Kategori).like('kesinti%')).all()
            person_deductions = {}
            deduction_details = []
            
            for rec in deduction_records:
                kategori = rec.Kategori or ''
                parts = kategori.split('|')
                if not parts or parts[0].strip().lower() != 'kesinti':
                    continue

                pid_match = None
                if len(parts) > 1 and parts[1].strip().isdigit():
                    pid_match = int(parts[1].strip())
                
                if pid_match != personel_id:
                    continue

                deduction_type = parts[2].strip() if len(parts) > 2 else "Kesinti"
                installment_count = None
                installment_start = None
                if len(parts) > 3 and parts[3].strip().isdigit():
                    installment_count = int(parts[3].strip())
                if len(parts) > 4 and parts[4].strip():
                    try:
                        installment_start = datetime.strptime(parts[4].strip(), '%Y-%m-%d').date()
                    except ValueError:
                        installment_start = rec.Tarih

                amount = float(rec.Tutar or 0)
                deduction_amount = 0.0
                info_text = deduction_type

                if installment_count and installment_count > 1 and installment_start:
                    months = (today.year - installment_start.year) * 12 + (today.month - installment_start.month)
                    installment_index = months + 1
                    if 1 <= installment_index <= installment_count:
                        deduction_amount = amount / float(installment_count)
                        info_text = f"{deduction_type} ({installment_index}/{installment_count} Taksit)"
                else:
                    if rec.Tarih and rec.Tarih.year == today.year and rec.Tarih.month == today.month:
                        deduction_amount = amount

                if deduction_amount > 0:
                    person_deductions[personel_id] = person_deductions.get(personel_id, 0.0) + deduction_amount
                    deduction_details.append({
                        'type': info_text,
                        'amount': deduction_amount
                    })

            result = services.get_payroll_for_person(p, today, weekly_schedule, public_holidays, monthly_hours, daily_net_work_hours, person_deductions)
            
            # Period name in Turkish
            months_tr = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
            period_name = f"{months_tr[today.month-1]} {today.year}"

            return render_template('bordro_pusula.html', 
                                   result=result, 
                                   deduction_details=deduction_details,
                                   company_name=company.SirketAdi if company else "ERP Sistemi",
                                   vergi_no=company.VergiNo if company else "-",
                                   period_name=period_name,
                                   net_tutar_yazi="Maaş Ödemesi") # Simplification for now
        except Exception as e:
            app.logger.exception('Bordro Pusula error')
            return "Error: {}".format(e), 500

    # Minimal API endpoints to support front-end interactivity if needed
    @app.route('/api/personel')
    def api_personel_list():
        try:
            people = Personel.query.all()
            return jsonify([{
                'id': p.PersonelID,
                'first_name': p.Ad,
                'last_name': p.Soyad,
                'net_salary': p.NetMaas
            } for p in people])
        except Exception as e:
            app.logger.exception('API personel error')
            return jsonify({'error': str(e)}), 500

    # Document Management Routes
    @app.route('/api/documents/<rel_type>/<int:rel_id>')
    @login_required
    def api_get_documents(rel_type, rel_id):
        """İlgili kayda ait belgeleri JSON olarak döner"""
        try:
            docs = Document.query.filter_by(RelationType=rel_type, RelationID=rel_id).all()
            return jsonify([{
                'id': d.BelgeID,
                'path': d.DosyaYolu,
                'name': d.DosyaAdi,
                'type': d.DosyaTuru,
                'desc': d.Aciklama
            } for d in docs])
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/upload_document/<rel_type>/<int:rel_id>', methods=['POST'])
    @login_required
    def upload_document(rel_type, rel_id):
        if 'file' not in request.files:
            flash('Dosya seçilmedi.', 'error')
            return redirect(request.referrer)
        file = request.files['file']
        if file.filename == '':
            flash('Dosya seçilmedi.', 'error')
            return redirect(request.referrer)
        if file:
            try:
                filename = secure_filename(file.filename)
                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                save_dir = Path(config.UPLOADS_DIR) / rel_type
                save_dir.mkdir(parents=True, exist_ok=True)
                file_path = save_dir / unique_filename
                file.save(str(file_path))
                relative_path = f"{rel_type}/{unique_filename}"

                doc = Document(
                    DosyaYolu=relative_path,
                    DosyaAdi=filename,
                    DosyaTuru=filename.split('.')[-1].lower() if '.' in filename else None,
                    Aciklama=request.form.get('aciklama', ''),
                    RelationType=rel_type,
                    RelationID=rel_id
                )
                db.session.add(doc)
                db.session.commit()
                
                # Check if it's an AJAX request
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': True, 'doc': {
                        'id': doc.BelgeID,
                        'name': doc.DosyaAdi,
                        'path': doc.DosyaYolu
                    }})
                
                flash('Dosya başarıyla yüklendi', 'success')
            except Exception as e:
                app.logger.error(f"File upload error: {e}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': str(e)}), 500
                flash(f'Yükleme hatası: {str(e)}', 'error')
                
        return redirect(request.referrer)

    @app.route('/view_document/<int:doc_id>')
    @login_required
    def view_document(doc_id):
        doc = Document.query.get_or_404(doc_id)
        file_path = Path(config.UPLOADS_DIR) / doc.DosyaYolu
        if not file_path.exists():
            return "Dosya bulunamadı", 404
        return send_from_directory(file_path.parent, file_path.name)

    @app.route('/delete_document/<int:doc_id>', methods=['POST'])
    @login_required
    def delete_document(doc_id):
        doc = Document.query.get_or_404(doc_id)
        try:
            # Delete physical file
            file_path = Path(config.UPLOADS_DIR) / doc.DosyaYolu
            if file_path.exists():
                os.remove(file_path)
                
            db.session.delete(doc)
            db.session.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True})
                
            flash('Belge silindi', 'success')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Silme hatası: {str(e)}', 'error')
        return redirect(request.referrer)

    return app


from apscheduler.schedulers.background import BackgroundScheduler

def run_auto_tests():
    """Sistem testlerini otomatik çalıştırır ve sonucu kaydeder"""
    import subprocess
    import sys
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    status_file = os.path.join(base_dir, 'tests', 'status.json')
    
    try:
        # Run pytest
        # capture_output=True requires Python 3.7+
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests'], 
            cwd=base_dir, 
            capture_output=True, 
            text=True
        )
        
        success = (result.returncode == 0)
        # Output'un son kısımlarını al (özet genellikle sondadır)
        output = result.stdout + "\n" + result.stderr
        
        status = {
            'last_run': timestamp,
            'success': success,
            'output': output
        }
        
        # Ensure tests dir exists inside function too just in case
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
            
        print(f"[{timestamp}] Auto-tests completed. Success: {success}")
        
    except Exception as e:
        print(f"Auto-test failed to run: {e}")

def init_scheduler(app):
    scheduler = BackgroundScheduler()
    
    # Veritabanı Yedekleme (Günde bir kez)
    scheduler.add_job(
        func=create_backup,
        trigger='interval',
        days=1,
        next_run_time=datetime.now() + timedelta(seconds=10)
    )
    
    # Otomatik Sistem Testleri (Her sabah 05:00'te)
    scheduler.add_job(
        func=run_auto_tests,
        trigger='cron',
        hour=5,
        minute=0
    )
    
    # Vade Hatırlatıcı Bildirimleri (Her sabah 09:00'da kontrol et)
    scheduler.add_job(
        func=services.check_upcoming_vades,
        args=[app],
        trigger='cron',
        hour=9,
        minute=0
    )
    
    # Günlük Kasa Özeti E-postası (Her akşam 20:00'de gönder)
    scheduler.add_job(
        func=services.send_daily_summary,
        args=[app],
        trigger='cron',
        hour=20,
        minute=0
    )
    
    scheduler.start()
    return scheduler

if __name__ == '__main__':
    import webbrowser
    from threading import Timer

    app = create_app()
    init_scheduler(app)
    
    def open_browser():
        try:
            webbrowser.open('http://127.0.0.1:5000')
        except:
            pass

    # Wait 1.5 seconds for the server to start, then open browser
    Timer(1.5, open_browser).start()
    
    print(f"DEBUG: Template Folder used by Flask: {app.template_folder}")
    print(f"DEBUG: Static Folder used by Flask: {app.static_folder}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
