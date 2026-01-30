# MY HOME ERP - Versiyon 1.0.97

* **Mükerrer İşlem Kaydı Düzeltmesi:** Banka üzerinden yapılan ödemelerin (avans, kesinti vb.) hem Banka sayfasında hem de Nakit Kasa sayfasında görünmesi sorunu giderildi. Artık banka üzerinden yapılan işlemler sadece Banka hareketlerinde görünecek, nakit kasayı haksız yere eksiye düşürmeyecektir.

# MY HOME ERP - Versiyon 1.0.96

* **Banka Bakiye Düzeltmesi:** Banka açılış/devir bakiyelerinin kaydedilememe ve sonradan sıfırlanma sorunu giderildi. Artık başlangıç bakiyeleri otomatik olarak bir finans hareketi olarak işleniyor.
* **Kesinti Düzenleme İyileştirmesi:** Kesinti kayıtları düzenlenirken banka seçimi ve ödeme yöntemi değişikliklerinin (Nakit->Banka vb.) doğru şekilde işlenmemesi ve bakiye yansıtmaması hatası giderildi.
* **Kasa Takibi:** Dashboard üzerindeki nakit kasa hesaplama mantığı iyileştirildi, banka hareketleri artık çok daha kesin bir yöntemle ayrıştırılıyor.

# MY HOME ERP - Versiyon 1.0.95

* **Kullanıcı Yönetimi Yenilendi:** Kullanıcı yönetimi, şirket ayarlarındaki sıkışık halinden kurtarılarak kendine özel, geniş ve modern bir sayfaya taşındı. 
* **Yeni Tasarım:** Kullanıcı listesi kart tasarımıyla güncellendi, istatistik paneli eklendi ve kullanıcı ekleme işlemi modern bir modal (pencere) üzerinden yapılacak şekilde iyileştirildi.

# MY HOME ERP - Versiyon 1.0.94

* **Kullanıcı Yönetimi Erişimi:** Sol menüde yer alan "Kullanıcı Yönetimi" bağlantısının 404 hatası vermesi sorunu giderildi. Bağlantı artık doğrudan ayarlar sayfası içindeki ilgili bölüme yönlendiriyor.

# MY HOME ERP - Versiyon 1.0.93

* **Otomatik Güncelleme İyileştirmesi:** Güncelleme dosyası indirildikten sonra başlatılırken oluşan "Invalid argument" hatası giderildi. Güncelleme işlemi artık daha kararlı bir yöntemle (subprocess) başlatılıyor.

# MY HOME ERP - Versiyon 1.0.92

* **Reçete Formu Düzeltmesi:** Reçete düzenleme ekranında mevcut verilerin (Reçete Adı, Mamul, Miktar ve İçerik Kalemleri) form üzerine gelmeme sorunu giderildi. Artık "Düzenle" dendiğinde tüm bilgiler yüklü geliyor ve güncelleme yapılabiliyor.
* **Silme Fonksiyonu:** Reçete düzenleme ekranına reçeteyi komple silme butonu eklendi.

# MY HOME ERP - Versiyon 1.0.91

* **Reçete Yönetimi Tamamlandı:** Reçete düzenleme ve silme işlemleri için eksik olan rotalar sisteme eklendi. Artık "Düzenle" butonu ile reçete detayları (mamul, bileşenler, miktarlar) değiştirilebiliyor.

# MY HOME ERP - Versiyon 1.0.90

* **Reçete Düzenleme:** Ürün reçeteleri listesinde bulunan "Düzenle" butonunun çalışmama sorunu giderildi. Artık reçete detaylarına ve güncelleme ekranına doğrudan erişilebilir.

# MY HOME ERP - Versiyon 1.0.89

* **Raporlama Düzeltmesi:** Raporlar sayfasında stok değerleme hesaplanırken, fiyat bilgisi eksik olan ürünlerin sistemsel hataya (NoneType error) neden olması engellendi. Eksik fiyatlı ürünler 0 TL değerle işlenerek raporun kesintisiz çalışması sağlandı.

# MY HOME ERP - Versiyon 1.0.88

* **Başlatma Düzeltmesi:** Uygulamanın penceresiz modda başlatılamama sorunu giderildi. Artık arka planda sessizce çalışır.
* **Otomatik Tarayıcı:** Uygulama başlatıldığında varsayılan internet tarayıcısının otomatik olarak açılması özelliği tekrar aktif edildi.
* **Performans:** Arka plan işlemleri optimize edildi.

# MY HOME ERP - Versiyon 1.0.87

* **Otomatik Sistem Sağlığı Kontrolü:** Sistem artık her sabah 05:00'te kendi kendini test ederek güvenlik, yetkilendirme ve maaş hesaplama modüllerinin doğru çalıştığını doğrulamaktadır.
* **Sistem Sağlığı Raporu:** Ayarlar sayfasında yeni eklenen "Sistem Sağlığı" kartı üzerinden son test sonuçları ve olası hatalar görüntülenebilmektedir.
* **Güvenlik İyileştirmeleri:** Yönetici (Admin) yetkisi olmayan kullanıcıların kritik ayarlara erişimi tamamen engellendi ve bu durum otomatik testlerle koruma altına alındı.

# MY HOME ERP - Versiyon 1.0.86

Bu sürüm, mesai çarpanlarının hesaplama modülleriyle tam entegrasyonunu ve kod organizasyonunu iyileştiren refaktör işlemlerini içermektedir.

## 🔧 Kritik Hata Düzeltmeleri (v1.0.86)
* **Mesai Çarpanı Entegrasyonu:** Ayarlarda belirlenen hafta sonu (Cumartesi/Pazar) ve hafta içi mesai çarpanlarının bordro, puantaj ve personel detay sayfalarına yansımama hatası giderildi. Artık tüm hesaplamalar ayarlar sayfasındaki güncel değerleri baz almaktadır.
* **Puantaj Varsayılanları:** Yeni günlere ait puantaj kayıtları oluşturulurken varsayılan çarpanların (1.5, 2.0 vb.) ayarlardan otomatik çekilmesi sağlandı.
* **Tutarlılık Güncellemesi:** Aynı gün için (örn: Pazar) farklı personellerde farklı çarpanların (2.0 vs 2.5) oluşmasına neden olan eski varsayılan değer mantığı, şirket ayarlarını zorunlu kılacak şekilde güncellendi.
* **Güvenlik (Security):** Şirket ayarları (`/ayarlar` vb.), finansal konfigürasyonlar ve kullanıcı yönetimi rotaları sadece **admin** yetkisine sahip kullanıcılar tarafından erişilebilir hale getirildi.
* **Kod Temizliği:** Mükerrer olan eski kullanıcı yönetim sayfaları (`kullanici_listesi.html`, `kullanici_form.html`) ve ilgili rotalar kaldırılarak yönetim tamamen merkezi `ayarlar.html` üzerinden sağlandı.
* **Kod Organizasyonu (Refactoring):** `app.py` içerisinde bulunan karmaşık bordro hesaplama mantığı (`get_payroll_for_person`) `services.py` dosyasına taşınarak kodun okunabilirliği ve bakımı kolaylaştırıldı.

# MY HOME ERP - Versiyon 1.0.85

Bu sürüm, Dijital Arşiv modülündeki yetkilendirme ve dosya erişim hatalarını gidermektedir.

## 🔧 Kritik Hata Düzeltmeleri (v1.0.85)
* **Yetkilendirme Hatası:** Belgelerin silinememesine neden olan "session.role" karmaşası giderildi, "admin" yetkisi düzeltildi.
* **Dosya Erişimi:** Yüklenen belgelerin açılamamasına neden olan statik dizin hatası giderildi. Artık tüm belgeler güvenli `/uploads/` rotası üzerinden servis ediliyor.
* **Dizin Yapısı:** Belge yükleme ve silme işlemleri `config.UPLOADS_DIR` üzerinden standartlaştırıldı.

# MY HOME ERP - Versiyon 1.0.84

Bu sürüm, veritabanı şema senkronizasyon hatalarının giderilmesi ve otomatik kurtarma sisteminin devreye alınmasını içermektedir.

## 🔧 Kritik Hata Düzeltmeleri (v1.0.84)
* **Veritabanı Senkronizasyonu:** `StokHareketleri` tablosundaki eksik `SeriNo` kolonu ve `Belgeler` tablosundaki eksik `Kategori` kolonu eklendi.
* **Otomatik Migration:** Uygulama artık her açılışta veritabanı şemasını otomatik olarak denetler ve eksik kolonları/tabloları kendisi ekler.
* **Raporlar Menüsü:** Yan menüdeki mükerrer bağlantılar kalıcı olarak temizlendi.


Bu sürüm, ERP sisteminin endüstriyel standartlara uyumunu sağlayan kritik hata düzeltmeleri ve üç ana modül (Barkod, BI, Dijital Arşiv) içermektedir.

## 🚀 Yenilikler

### 🔍 İş Zekası (BI) ve Gelişmiş Finans
* **Stok Değerleme:** Tüm ürünlerin son alış fiyatı üzerinden anlık stok varlık değeri hesaplaması eklendi.
* **Nakit Akışı Analizi:** Kasa, banka, bekleyen alacaklar ve borçlar arasındaki dengeyi görselleştiren likidite tablosu eklendi.
* **Net Finansal Durum:** Şirketin anlık net özkaynak benzeri varlık durumu raporlandı.

### 📦 Dijital Arşiv (Döküman Yönetimi)
* Belge yükleme sırasında otomatik dosya boyutu hesaplama ve kategorizasyon.
* Yüklenen belgelerin doğrudan **Cari Hesap**, **Fatura** veya **Personel** kayıtlarına bağlanabilmesi.

### 🏷️ Barkod Okuyucu Entegrasyonu
* Fatura ve sipariş formlarına gerçek zamanlı barkod tarama desteği eklendi.
* Otomatik ürün eşleme ve miktar artırımı ile veri giriş hatası minimize edildi.

### 🖥️ Arayüz ve Kullanılabilirlik
* **Menü Sadeleştirme:** Sidebar'daki mükerrer "Raporlar" bağlantıları kaldırıldı. Tüm raporlama ve BI özellikleri **"Raporlar & BI"** başlığı altında tekil hale getirildi.

## 🔧 İyileştirmeler & Hata Düzeltmeleri
* **Kritik Veritabanı Senkronizasyonu:** "Dijital Arşiv" ve "İşlem Logları" sekmelerinde görülen "Internal Server Error" hataları, kod ve veritabanı şeması arasındaki uyuşmazlıklar giderilerek çözüldü.
* **Otomatik Tablo Yönetimi:** Eksik olan Teklif, Siparişi ve Üretim tabloları sisteme otomatik olarak eklendi.
* **SSL Çözümü:** Windows ortamında görülen `SSL: CERTIFICATE_VERIFY_FAILED` hatası, harici API çağrılarında (GitHub, Kur, Hava Durumu) giderildi.
* **Verim Artışı:** Jinja2 ve JavaScript arasındaki veri iletimi JSON formatına çekilerek lint hataları ve performans darboğazları giderildi.
* **Gider Yönetimi:** Giderler için yeni `ExpenseCategory` modeli ile detaylı maliyet analizi altyapısı kuruldu.

## 📦 Kurulum Bilgisi
* `create_installer.bat` dosyası ile en güncel sürümün kurulum dosyasını (`.exe`) oluşturabilirsiniz.
* `erp_installer.iss` dosyası v1.0.81 sürümüne göre güncellendi.
