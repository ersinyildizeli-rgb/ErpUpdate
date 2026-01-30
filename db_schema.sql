-- ERP Veritabanı Tam Şema (SQL Server)
-- Veritabanı: erp_db
-- Kullanıcı: sa
-- Şifre: Gs1905.Gs1905..

-- Veritabanını oluştur (varsa atla)
USE master;
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = 'erp_db')
BEGIN
    CREATE DATABASE erp_db;
END
GO

USE erp_db;
GO

-- =====================================================
-- 1. Şirket Bilgileri (Sirket)
-- =====================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Sirket')
BEGIN
    CREATE TABLE Sirket (
        SirketID INT PRIMARY KEY IDENTITY(1,1),
        SirketAdi NVARCHAR(200) NOT NULL,
        VergiNo NVARCHAR(50) NULL,
        MesaiUcreti FLOAT NOT NULL DEFAULT 50.0,
        Ayarlar NVARCHAR(1000) NULL,  -- JSON formatında saklanabilir
        EklemeTarihi DATETIME NOT NULL DEFAULT GETDATE()
    );
    
    CREATE NONCLUSTERED INDEX IX_Sirket_SirketAdi ON Sirket(SirketAdi);
    PRINT 'Sirket tablosu oluşturuldu.';
END
GO

-- =====================================================
-- 2. Personel Bilgileri (Personel)
-- =====================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Personel')
BEGIN
    CREATE TABLE Personel (
        PersonelID INT PRIMARY KEY IDENTITY(1,1),
        Ad NVARCHAR(120) NOT NULL,
        Soyad NVARCHAR(120) NOT NULL,
        TC NVARCHAR(11) UNIQUE NULL,
        Telefon NVARCHAR(20) NULL,
        Departman NVARCHAR(120) NULL,
        NetMaas FLOAT NOT NULL DEFAULT 0.0,
        IsGirisTarihi DATE NULL,
        EklemeTarihi DATETIME NOT NULL DEFAULT GETDATE()
    );
    
    CREATE NONCLUSTERED INDEX IX_Personel_Ad ON Personel(Ad);
    CREATE NONCLUSTERED INDEX IX_Personel_Soyad ON Personel(Soyad);
    CREATE NONCLUSTERED INDEX IX_Personel_TC ON Personel(TC);
    PRINT 'Personel tablosu oluşturuldu.';
END
GO

-- =====================================================
-- 3. Finansal İşlemler (Finans)
-- =====================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Finans')
BEGIN
    CREATE TABLE Finans (
        FinansID INT PRIMARY KEY IDENTITY(1,1),
        Tarih DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE),
        Tutar FLOAT NOT NULL,
        IslemTuru NVARCHAR(20) NOT NULL,  -- 'Gelir' or 'Gider'
        Kategori NVARCHAR(80) NULL,  -- Satış, Kira, Maaş, vb.
        Aciklama NVARCHAR(500) NULL,
        EklemeTarihi DATETIME NOT NULL DEFAULT GETDATE()
    );
    
    CREATE NONCLUSTERED INDEX IX_Finans_Tarih ON Finans(Tarih);
    CREATE NONCLUSTERED INDEX IX_Finans_IslemTuru ON Finans(IslemTuru);
    CREATE NONCLUSTERED INDEX IX_Finans_Kategori ON Finans(Kategori);
    PRINT 'Finans tablosu oluşturuldu.';
END
GO

-- =====================================================
-- 4. Puantaj / Katılım Takibi (Puantaj)
-- =====================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Puantaj')
BEGIN
    CREATE TABLE Puantaj (
        PuantajID INT PRIMARY KEY IDENTITY(1,1),
        PersonelID INT NOT NULL,
        Tarih DATE NOT NULL,
        Durum NVARCHAR(20) NOT NULL,  -- Geldi, Gelmedi, İzinli
        MesaiSaati FLOAT NOT NULL DEFAULT 0.0,
        EklemeTarihi DATETIME NOT NULL DEFAULT GETDATE(),
        
        CONSTRAINT FK_Puantaj_Personel FOREIGN KEY (PersonelID) 
            REFERENCES Personel(PersonelID) ON DELETE CASCADE
    );
    
    CREATE NONCLUSTERED INDEX IX_Puantaj_PersonelID ON Puantaj(PersonelID);
    CREATE NONCLUSTERED INDEX IX_Puantaj_Tarih ON Puantaj(Tarih);
    CREATE NONCLUSTERED INDEX IX_Puantaj_Durum ON Puantaj(Durum);
    PRINT 'Puantaj tablosu oluşturuldu.';
END
GO

-- =====================================================
-- 5. Kullanıcılar (Kullanici)
-- =====================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Kullanici')
BEGIN
    CREATE TABLE Kullanici (
        KullaniciID INT PRIMARY KEY IDENTITY(1,1),
        KullaniciAdi NVARCHAR(120) NOT NULL UNIQUE,
        Email NVARCHAR(200) NULL UNIQUE,
        SifreHash NVARCHAR(255) NOT NULL,
        Rol NVARCHAR(50) NOT NULL DEFAULT 'admin',
        Aktif BIT NOT NULL DEFAULT 1,
        EklemeTarihi DATETIME NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Kullanici tablosu oluşturuldu.';
END
GO

-- =====================================================
-- 5. Başlangıç Verisi (Örnek)
-- =====================================================

-- Varsayılan Şirket Kaydı
IF NOT EXISTS (SELECT 1 FROM Sirket WHERE SirketAdi = 'Örnek Şirket')
BEGIN
    INSERT INTO Sirket (SirketAdi, VergiNo, MesaiUcreti)
    VALUES (N'Örnek Şirket', '0000000000', 50.0);
    PRINT 'Varsayılan şirket kaydı eklendi.';
END
GO

-- Örnek Personel Kayıtları
IF NOT EXISTS (SELECT 1 FROM Personel WHERE TC = '12345678901')
BEGIN
    INSERT INTO Personel (Ad, Soyad, TC, Telefon, Departman, NetMaas, IsGirisTarihi)
    VALUES 
        (N'Ahmet', N'Kaya', '12345678901', '5551234567', N'Muhasebe', 3000.0, '2023-01-15'),
        (N'Ayşe', N'Yılmaz', '12345678902', '5552345678', N'İK', 2800.0, '2023-02-10'),
        (N'Mehmet', N'Demir', '12345678903', '5553456789', N'Bilgi İşlem', 4000.0, '2022-12-01');
    PRINT 'Örnek personel kayıtları eklendi.';
END
GO

-- Örnek Finansal İşlemler
IF NOT EXISTS (SELECT 1 FROM Finans WHERE Kategori = 'Satış')
BEGIN
    INSERT INTO Finans (Tarih, Tutar, IslemTuru, Kategori, Aciklama)
    VALUES 
        ('2025-12-20', 5000.0, N'Gelir', N'Satış', N'Ürün satışı'),
        ('2025-12-21', 1200.0, N'Gider', N'Kira', N'Ofis kira ödemesi'),
        ('2025-12-22', 9000.0, N'Gider', N'Maaş', N'Aylık maaşlar');
    PRINT 'Örnek finansal işlemler eklendi.';
END
GO

-- =====================================================
-- 6. Tablo Bilgisi Kontrol
-- =====================================================
SELECT 
    TABLE_NAME AS [Tablo Adı],
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
     WHERE TABLE_NAME = t.TABLE_NAME) AS [Kolon Sayısı]
FROM INFORMATION_SCHEMA.TABLES t
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
GO

PRINT '✓ Veritabanı şeması başarıyla oluşturuldu!';
GO
