Turkish Language Support & SQL Server Configuration Guide

Türkçe Dil Desteği ve SQL Server Kurulum Rehberi

## 1. SQL Server Veritabanı Kurulumu

Dosya: `db_schema.sql`

### SQL Server Management Studio (SSMS) ile kurulum:
1. SSMS'i açın ve SQL Server'a bağlanın (192.168.1.53, sa, Gs1905.Gs1905..)
2. "New Query" seçin
3. `db_schema.sql` dosyasının içeriğini kopyalayıp yapıştırın
4. "Execute" (F5) basın
5. Veritabanı `erp_db` ve tüm tablolar otomatik olarak oluşturulacak

### sqlcmd ile kurulum (Command Line):
```powershell
$sqlScript = Get-Content -Path "db_schema.sql" -Raw
$sqlcmdParams = @(
    "-S", "192.168.1.53"
    "-U", "sa"
    "-P", "Gs1905.Gs1905.."
    "-d", "master"
)
$sqlScript | sqlcmd @sqlcmdParams
```

## 2. Tablo Yapısı (Özet)

### Sirket (Şirket Bilgileri)
- SirketID (INT, Primary Key, IDENTITY)
- SirketAdi (NVARCHAR(200), NOT NULL)
- VergiNo (NVARCHAR(50))
- MesaiUcreti (FLOAT, Default: 50.0)
- Ayarlar (NVARCHAR(1000), JSON uyumlu)
- EklemeTarihi (DATETIME, Default: GETDATE())

### Personel (Çalışan Bilgileri)
- PersonelID (INT, Primary Key, IDENTITY)
- Ad (NVARCHAR(120), NOT NULL)
- Soyad (NVARCHAR(120), NOT NULL)
- TC (NVARCHAR(11), UNIQUE)
- Telefon (NVARCHAR(20))
- Departman (NVARCHAR(120))
- NetMaas (FLOAT, Default: 0.0)
- IsGirisTarihi (DATE)
- EklemeTarihi (DATETIME)

### Finans (Finansal İşlemler)
- FinansID (INT, Primary Key, IDENTITY)
- Tarih (DATE, Default: Today)
- Tutar (FLOAT)
- IslemTuru (NVARCHAR(20), 'Gelir' or 'Gider')
- Kategori (NVARCHAR(80), örn: Satış, Kira, Maaş)
- Aciklama (NVARCHAR(500))
- EklemeTarihi (DATETIME)

### Puantaj (Attendance/Presence)
- PuantajID (INT, Primary Key, IDENTITY)
- PersonelID (INT, Foreign Key -> Personel)
- Tarih (DATE)
- Durum (NVARCHAR(20), Geldi/Gelmedi/İzinli)
- MesaiSaati (FLOAT, Default: 0.0)
- EklemeTarihi (DATETIME)

## 3. Indices (Performans)

Tüm tabloların sık sorgulanan kolonlarında INDEX'ler otomatik oluşturulur:
- Personel: Ad, Soyad, TC
- Finans: Tarih, IslemTuru, Kategori
- Puantaj: PersonelID, Tarih, Durum

## 4. Türkçe Karakter Desteği

- Tüm NVARCHAR alanları Türkçe karakterleri destekler (ç, ğ, ı, ö, ş, ü, etc.)
- Flask uygulaması `JSON_AS_ASCII = False` ile yapılandırılmış
- HTML şablonları `<meta charset="utf-8">` içerir

## 5. Bağlantı Bilgileri

Database: erp_db
Host: 192.168.1.53
Port: 1433 (default)
User: sa
Password: Gs1905.Gs1905..
Driver: pymssql (Python)

Connection String (Python/Flask):
```
mssql+pymssql://sa:Gs1905.Gs1905..@192.168.1.53:1433/erp_db
```

## 6. Login Hatası Çözümü

Eğer "Login failed for user 'sa'" hatası alırsanız:
1. SQL Server'da sa kullanıcısının enabled olduğundan emin olun
2. SQL Server Authentication modu aktif olduğundan emin olun (Windows Auth değil)
3. Şifrenin doğru olduğundan emin olun: Gs1905.Gs1905..
4. Port 1433'ün açık olduğundan emin olun

## 7. Örnek Veriler

- Şirket: "Örnek Şirket" (VergiNo: 0000000000)
- Personel: 3 kişi (Ahmet Kaya, Ayşe Yılmaz, Mehmet Demir)
- Finans: 3 işlem (Satış, Kira, Maaş)

Veritabanı kurulduktan sonra Flask uygulaması otomatik olarak bağlanacak.
