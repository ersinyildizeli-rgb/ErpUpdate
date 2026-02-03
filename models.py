from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import Index, event, DDL, text
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import validates
import os

db = SQLAlchemy()

def get_db_uri():
    """Get database URI from config"""
    from config import DATABASE_URI
    return DATABASE_URI

# SQLite için özel ayarlar
if 'sqlite' in get_db_uri():
    from sqlalchemy.engine import Engine
    from sqlalchemy import event

    # SQLite yabancı anahtar desteğini etkinleştir
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # SQLite için transaction düzeyi ayarı
    @event.listens_for(Engine, "begin")
    def receive_begin(conn):
        conn.execute(text("PRAGMA read_uncommitted = 0"))
        conn.execute(text("PRAGMA synchronous = NORMAL"))
        
    # VACUUM ve WAL Modu Ayarları
    @event.listens_for(Engine, "connect")
    def set_sqlite_wal(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # WAL modunu aç
        cursor.execute("PRAGMA cache_size=-64000") # 64MB cache (negatif değer kb cinsinden)
        cursor.close()

class Personel(db.Model):
    __tablename__ = 'Personel'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    PersonelID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Ad = db.Column(db.String(120), nullable=False)
    Soyad = db.Column(db.String(120), nullable=False)
    TC = db.Column(db.String(11), unique=True, nullable=True)
    Telefon = db.Column(db.String(20), nullable=True)
    Email = db.Column(db.String(200), nullable=True)
    Departman = db.Column(db.String(120), nullable=True)
    NetMaas = db.Column(db.Float, nullable=False, default=0.0)
    IsGirisTarihi = db.Column(db.Date, nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    Unvan = db.Column(db.String(120), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # İlişkiler
    Puantaj = db.relationship('Puantaj', back_populates='Personel', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        date_fields = ['IsGirisTarihi']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    kwargs[field] = None
        super(Personel, self).__init__(**kwargs)

    def __repr__(self):
        return f"<Personel {self.PersonelID} {self.Ad} {self.Soyad}>"

class Finance(db.Model):
    __tablename__ = 'Finans'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    FinansID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Tarih = db.Column(db.Date, nullable=False, default=datetime.utcnow().date())
    Tutar = db.Column(db.Float, nullable=False)
    IslemTuru = db.Column(db.String(20), nullable=False)  # 'Gelir' or 'Gider'
    Kategori = db.Column(db.String(80), nullable=True)  # Satış, Kira, Maaş, vb.
    Aciklama = db.Column(db.String(500), nullable=True)
    BankaID = db.Column(db.Integer, db.ForeignKey('BankaHesabi.BankaID'), nullable=True)
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    
    Cari = db.relationship('CariAccount', backref='finance_entries')
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        date_fields = ['Tarih']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    kwargs[field] = datetime.utcnow().date()
        super(Finance, self).__init__(**kwargs)

    def __repr__(self):
        return f"<Finance {self.FinansID} {self.IslemTuru} {self.Tutar}>"

class Puantaj(db.Model):
    __tablename__ = 'Puantaj'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    PuantajID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    PersonelID = db.Column(db.Integer, db.ForeignKey('Personel.PersonelID', ondelete='CASCADE'), nullable=False)
    Tarih = db.Column(db.Date, nullable=False)
    Durum = db.Column(db.String(20), nullable=False)  # Geldi/Gelmedi/İzinli/Geç Geldi
    MesaiSaati = db.Column(db.Float, nullable=False, default=0.0)
    EksikSaat = db.Column(db.Float, nullable=False, default=0.0)
    KesintiTuru = db.Column(db.String(20), nullable=True)  # 'Maaş' veya 'Mesai'
    Carpan = db.Column(db.Float, nullable=False, default=1.5)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    Personel = db.relationship('Personel', back_populates='Puantaj')
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        date_fields = ['Tarih']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    kwargs[field] = datetime.utcnow().date()
        super(Puantaj, self).__init__(**kwargs)

    def __repr__(self):
        return f"<Puantaj {self.PuantajID} P:{self.PersonelID} {self.Tarih} {self.Durum}>"

class Company(db.Model):
    __tablename__ = 'Sirket'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    SirketID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SirketAdi = db.Column(db.String(200), nullable=False)
    VergiNo = db.Column(db.String(50), nullable=True)
    MesaiUcreti = db.Column(db.Float, nullable=False, default=50.0)  # Saatlik mesai ücreti
    Ayarlar = db.Column(db.String(1000), nullable=True)  # JSON string olarak saklanır
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        if 'Ayarlar' in kwargs and isinstance(kwargs['Ayarlar'], dict):
            import json
            kwargs['Ayarlar'] = json.dumps(kwargs['Ayarlar'])
        super(Company, self).__init__(**kwargs)

    def get_settings(self):
        import json
        try:
            return json.loads(self.Ayarlar) if self.Ayarlar else {}
        except Exception:
            return {}

    def set_settings(self, obj):
        import json
        self.Ayarlar = json.dumps(obj)

    def __repr__(self):
        return f"<Company {self.SirketID} {self.SirketAdi}>"


class User(db.Model):
    __tablename__ = 'Kullanici'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KullaniciID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    KullaniciAdi = db.Column(db.String(120), unique=True, nullable=False)
    Email = db.Column(db.String(200), unique=True, nullable=True)
    SifreHash = db.Column(db.String(255), nullable=False)
    Rol = db.Column(db.String(50), nullable=False, default='admin')
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    @validates('Email')
    def validate_email(self, key, email):
        if email and '@' not in email:
            raise ValueError('Geçersiz e-posta adresi')
        return email

    def set_password(self, password):
        self.SifreHash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.SifreHash, password)

    def __repr__(self):
        return f"<User {self.KullaniciID} {self.KullaniciAdi}>"

class BankAccount(db.Model):
    __tablename__ = 'BankaHesabi'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    BankaID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    BankaAdi = db.Column(db.String(100), nullable=False)
    HesapAdi = db.Column(db.String(100), nullable=False)
    HesapTipi = db.Column(db.String(50), nullable=True) # vadesiz, vadeli, kredi, pos
    Sube = db.Column(db.String(100), nullable=True)
    HesapNo = db.Column(db.String(50), nullable=True)
    IBAN = db.Column(db.String(34), nullable=True)
    Bakiye = db.Column(db.Float, nullable=False, default=0.0)
    ParaBirimi = db.Column(db.String(10), nullable=False, default='TRY')
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    
    @validates('IBAN')
    def validate_iban(self, key, iban):
        if iban and len(iban) > 34:
            raise ValueError('IBAN en fazla 34 karakter olabilir')
        return iban

    def __repr__(self):
        return f"<BankAccount {self.BankaID} {self.BankaAdi} - {self.Bakiye}>"

class Debt(db.Model):
    __tablename__ = 'Borclar'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    BorcID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Baslik = db.Column(db.String(200), nullable=True)
    BorcVeren = db.Column(db.String(200), nullable=False)
    BorcTuru = db.Column(db.String(100), nullable=False)
    AnaTutar = db.Column(db.Float, nullable=False)
    KalanTutar = db.Column(db.Float, nullable=False)
    Tutar = db.Column(db.Float, nullable=False, default=0.0)
    VadeTarihi = db.Column(db.Date, nullable=True)
    Durum = db.Column(db.String(50), nullable=False, default='Bekliyor') # Bekliyor, Kısmi Ödendi, Ödendi
    Aciklama = db.Column(db.String(500), nullable=True)
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        date_fields = ['VadeTarihi']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    kwargs[field] = None
        
        # Varsayılan değerler
        if 'KalanTutar' not in kwargs and 'AnaTutar' in kwargs:
            kwargs['KalanTutar'] = kwargs['AnaTutar']
            
        super(Debt, self).__init__(**kwargs)

    def __repr__(self):
        return f"<Debt {self.BorcID} {self.BorcVeren} - {self.AnaTutar}>"

class Receivable(db.Model):
    __tablename__ = 'Alacaklar'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    AlacakID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Baslik = db.Column(db.String(200), nullable=True)
    Alacakli = db.Column(db.String(200), nullable=False)
    AlacakTuru = db.Column(db.String(100), nullable=False)
    AnaTutar = db.Column(db.Float, nullable=False)
    KalanTutar = db.Column(db.Float, nullable=False)
    Tutar = db.Column(db.Float, nullable=False, default=0.0)
    VadeTarihi = db.Column(db.Date, nullable=True)
    Durum = db.Column(db.String(50), nullable=False, default='Bekliyor') # Bekliyor, Kısmi Ödendi, Alındı
    Aciklama = db.Column(db.String(500), nullable=True)
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)
    
    def __init__(self, **kwargs):
        # SQLite için tarih alanlarını doğru formata getir
        date_fields = ['VadeTarihi']
        for field in date_fields:
            if field in kwargs and isinstance(kwargs[field], str):
                try:
                    kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    kwargs[field] = None
        
        # Varsayılan değerler
        if 'KalanTutar' not in kwargs and 'AnaTutar' in kwargs:
            kwargs['KalanTutar'] = kwargs['AnaTutar']
            
        super(Receivable, self).__init__(**kwargs)

    def __repr__(self):
        return f"<Receivable {self.AlacakID} {self.Alacakli} - {self.AnaTutar}>"

class Document(db.Model):
    __tablename__ = 'Belgeler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    BelgeID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    DosyaYolu = db.Column(db.String(500), nullable=False)
    DosyaAdi = db.Column(db.String(200), nullable=False)
    DosyaTuru = db.Column(db.String(50), nullable=True) # pdf, image, etc.
    DosyaBoyutu = db.Column(db.Integer, nullable=True) # byte cinsinden
    RelationType = db.Column(db.String(50), nullable=True) # Cari, Fatura, Personel vb.
    RelationID = db.Column(db.Integer, nullable=True)
    Kategori = db.Column(db.String(50), nullable=True)
    Aciklama = db.Column(db.String(500), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def Cari(self):
        if self.RelationType == 'Cari' and self.RelationID:
            return CariAccount.query.get(self.RelationID)
        return None

    @property
    def Personel(self):
        if self.RelationType == 'Personel' and self.RelationID:
            return Personel.query.get(self.RelationID)
        return None

    def __repr__(self):
        return f"<Document {self.BelgeID} {self.DosyaAdi}>"

class ActionLog(db.Model):
    __tablename__ = 'IslemLoglari'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    LogID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    KullaniciID = db.Column(db.Integer, db.ForeignKey('Kullanici.KullaniciID'), nullable=True)
    IslemTuru = db.Column(db.String(50), nullable=False) # Ekleme, Silme, Güncelleme
    Modul = db.Column(db.String(50), nullable=False) # Personel, Stok, Finans
    Detay = db.Column(db.String(500), nullable=True)
    IpAdresi = db.Column(db.String(50), nullable=True)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    Kullanici = db.relationship('User', backref='loglar')

    def __repr__(self):
        return f"<ActionLog {self.LogID} {self.IslemTipi} on {self.Modul}>"

class CekSenet(db.Model):
    __tablename__ = 'CekSenetler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    CekSenetID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    EvrakNo = db.Column(db.String(50), nullable=False)
    EvrakTuru = db.Column(db.String(20), nullable=False) # 'Çek' or 'Senet'
    IslemTuru = db.Column(db.String(20), nullable=False) # 'Alınan' or 'Verilen'
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=False)
    VadeTarihi = db.Column(db.Date, nullable=False)
    Tutar = db.Column(db.Float, nullable=False, default=0.0)
    BankaID = db.Column(db.Integer, db.ForeignKey('BankaHesabi.BankaID'), nullable=True)
    BankaAdi = db.Column(db.String(100), nullable=True) # BankaID yoksa manuel giriş için
    Sube = db.Column(db.String(100), nullable=True)
    HesapNo = db.Column(db.String(100), nullable=True)
    Durum = db.Column(db.String(30), default='Portföyde') # Portföyde, Bankada, Tahsilde, Ciro Edildi, Ödendi, Karşılıksız, İadesi
    AsilBorclu = db.Column(db.String(200), nullable=True)
    Aciklama = db.Column(db.String(500), nullable=True)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    Cari = db.relationship('CariAccount', backref='cek_senetler')
    Banka = db.relationship('BankAccount', backref='cek_senetler')

    def __repr__(self):
        return f"<CekSenet {self.CekSenetID} {self.EvrakNo} {self.EvrakTuru}>"

class CariAccount(db.Model):
    __tablename__ = 'CariHesaplar'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    CariID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Unvan = db.Column(db.String(200), nullable=False)
    CariTipi = db.Column(db.String(50), nullable=False) # Müşteri, Tedarikçi, Her İkisi
    VergiDairesi = db.Column(db.String(100), nullable=True)
    VergiNo = db.Column(db.String(50), nullable=True)
    Telefon = db.Column(db.String(20), nullable=True)
    Email = db.Column(db.String(200), nullable=True)
    Adres = db.Column(db.String(500), nullable=True)
    Bakiye = db.Column(db.Float, nullable=False, default=0.0)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<CariAccount {self.CariID} {self.Unvan}>"

class Urun(db.Model):
    __tablename__ = 'Urunler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    UrunID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    UrunAdi = db.Column(db.String(200), nullable=False)
    Birim = db.Column(db.String(20), nullable=False, default='Adet') # Adet, KG, Metre vb.
    KritikStok = db.Column(db.Float, nullable=True, default=0.0)
    SatisFiyati = db.Column(db.Float, nullable=True, default=0.0)
    AlisFiyati = db.Column(db.Float, nullable=True, default=0.0)
    KDV = db.Column(db.Integer, default=20) # 0, 1, 10, 20
    Barkod = db.Column(db.String(50), nullable=True)
    StokMiktari = db.Column(db.Float, nullable=False, default=0.0)
    EklemeTarihi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Urun {self.UrunID} {self.UrunAdi}>"

class StokHareketi(db.Model):
    __tablename__ = 'StokHareketleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    HareketID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    UrunID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    FaturaID = db.Column(db.Integer, db.ForeignKey('Faturalar.FaturaID'), nullable=True)
    HareketTuru = db.Column(db.String(20), nullable=False) # 'Giriş' or 'Çıkış'
    Miktar = db.Column(db.Float, nullable=False)
    BirimFiyat = db.Column(db.Float, nullable=True)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=True)
    Aciklama = db.Column(db.String(500), nullable=True)
    SeriNo = db.Column(db.String(100), nullable=True)

    Urun = db.relationship('Urun', backref='hareketler')
    Cari = db.relationship('CariAccount', backref='stok_hareketleri')

    def __repr__(self):
        return f"<StokHareketi {self.HareketID} {self.HareketTuru} {self.Miktar}>"

class Fatura(db.Model):
    __tablename__ = 'Faturalar'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    FaturaID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FaturaNo = db.Column(db.String(50), nullable=False)
    FaturaTuru = db.Column(db.String(20), nullable=False) # 'Alış' or 'Satış'
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=False)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    AraToplam = db.Column(db.Float, default=0.0)
    KDVToplam = db.Column(db.Float, default=0.0)
    GenelToplam = db.Column(db.Float, default=0.0)
    Aciklama = db.Column(db.String(500), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    Cari = db.relationship('CariAccount', backref='faturalar')
    Kalemler = db.relationship('FaturaKalemi', backref='fatura', cascade="all, delete-orphan")
    StokHareketleri = db.relationship('StokHareketi', backref='fatura')

    def __repr__(self):
        return f"<Fatura {self.FaturaID} {self.FaturaNo}>"

class FaturaKalemi(db.Model):
    __tablename__ = 'FaturaKalemleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KalemID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    FaturaID = db.Column(db.Integer, db.ForeignKey('Faturalar.FaturaID'), nullable=False)
    UrunID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    Miktar = db.Column(db.Float, nullable=False)
    BirimFiyat = db.Column(db.Float, nullable=False)
    KDVOran = db.Column(db.Integer, default=20)
    SatirToplami = db.Column(db.Float, nullable=False)
    SeriNo = db.Column(db.String(100), nullable=True)

    Urun = db.relationship('Urun')

    def __repr__(self):
        return f"<FaturaKalemi {self.KalemID} In:{self.FaturaID}>"

# === TEKLİF VE SİPARİŞ MODELLERİ ===

class Teklif(db.Model):
    __tablename__ = 'Teklifler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    TeklifID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TeklifNo = db.Column(db.String(50), nullable=False)
    TeklifTuru = db.Column(db.String(20), nullable=False) # 'Alış' or 'Satış'
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=False)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    GecerlilikTarihi = db.Column(db.DateTime, nullable=True)
    Durum = db.Column(db.String(30), default='Beklemede') # Beklemede, Onaylandı, Reddedildi, Faturaya Dönüştü
    AraToplam = db.Column(db.Float, default=0.0)
    KDVToplam = db.Column(db.Float, default=0.0)
    GenelToplam = db.Column(db.Float, default=0.0)
    Aciklama = db.Column(db.String(500), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    Cari = db.relationship('CariAccount', backref='teklifler')
    Kalemler = db.relationship('TeklifKalemi', backref='teklif', cascade="all, delete-orphan")

class TeklifKalemi(db.Model):
    __tablename__ = 'TeklifKalemleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KalemID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TeklifID = db.Column(db.Integer, db.ForeignKey('Teklifler.TeklifID'), nullable=False)
    UrunID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    Miktar = db.Column(db.Float, nullable=False)
    BirimFiyat = db.Column(db.Float, nullable=False)
    KDVOran = db.Column(db.Integer, default=20)
    SatirToplami = db.Column(db.Float, nullable=False)
    SeriNo = db.Column(db.String(100), nullable=True)

    Urun = db.relationship('Urun')

class Siparis(db.Model):
    __tablename__ = 'Siparisler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    SiparisID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SiparisNo = db.Column(db.String(50), nullable=False)
    SiparisTuru = db.Column(db.String(20), nullable=False) # 'Alış' or 'Satış'
    CariID = db.Column(db.Integer, db.ForeignKey('CariHesaplar.CariID'), nullable=False)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    TeslimTarihi = db.Column(db.DateTime, nullable=True)
    Durum = db.Column(db.String(30), default='Beklemede') # Beklemede, Hazırlanıyor, Sevk Edildi, Tamamlandı, Faturaya Dönüştü
    AraToplam = db.Column(db.Float, default=0.0)
    KDVToplam = db.Column(db.Float, default=0.0)
    GenelToplam = db.Column(db.Float, default=0.0)
    Aciklama = db.Column(db.String(500), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    Cari = db.relationship('CariAccount', backref='siparisler')
    Kalemler = db.relationship('SiparisKalemi', backref='siparis', cascade="all, delete-orphan")

class SiparisKalemi(db.Model):
    __tablename__ = 'SiparisKalemleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KalemID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    SiparisID = db.Column(db.Integer, db.ForeignKey('Siparisler.SiparisID'), nullable=False)
    UrunID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    Miktar = db.Column(db.Float, nullable=False)
    BirimFiyat = db.Column(db.Float, nullable=False)
    KDVOran = db.Column(db.Integer, default=20)
    SatirToplami = db.Column(db.Float, nullable=False)
    SeriNo = db.Column(db.String(100), nullable=True)

    Urun = db.relationship('Urun')

# === ÜRETİM VE REÇETE MODELLERİ ===

class Recete(db.Model):
    __tablename__ = 'Receteler'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    ReceteID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    MamulID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    ReceteAdi = db.Column(db.String(200), nullable=False)
    VarsayilanMiktar = db.Column(db.Float, default=1.0) # 1 birim üretim için gerekenler
    Aciklama = db.Column(db.String(500), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    Mamul = db.relationship('Urun', foreign_keys=[MamulID])
    Kalemler = db.relationship('ReceteKalemi', backref='recete', cascade="all, delete-orphan")

class ReceteKalemi(db.Model):
    __tablename__ = 'ReceteKalemleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KalemID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ReceteID = db.Column(db.Integer, db.ForeignKey('Receteler.ReceteID'), nullable=False)
    HammaddeID = db.Column(db.Integer, db.ForeignKey('Urunler.UrunID'), nullable=False)
    Miktar = db.Column(db.Float, nullable=False)

    Hammadde = db.relationship('Urun', foreign_keys=[HammaddeID])

class UretimEmri(db.Model):
    __tablename__ = 'UretimEmirleri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    EmirID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ReceteID = db.Column(db.Integer, db.ForeignKey('Receteler.ReceteID'), nullable=False)
    Miktar = db.Column(db.Float, nullable=False)
    Tarih = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    Durum = db.Column(db.String(30), default='Planlandı') # Planlandı, Üretimde, Tamamlandı, İptal
    Aciklama = db.Column(db.String(500), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    Recete = db.relationship('Recete', backref='emirler')

class ExpenseCategory(db.Model):
    __tablename__ = 'GiderKategorileri'
    __table_args__ = {
        'sqlite_autoincrement': True
    }
    KategoriID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    KategoriAdi = db.Column(db.String(100), nullable=False)
    Aciklama = db.Column(db.String(200), nullable=True)
    Aktif = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<ExpenseCategory {self.KategoriAdi}>"
