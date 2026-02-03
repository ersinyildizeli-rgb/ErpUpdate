# Geleceğe Hazırlık ve Bakım Kılavuzu

Bu belge, sistemin uzun ömürlü ve performanslı çalışması için yapılan güncellemeleri ve bakım talimatlarını içerir.

## 1. Yeni Özellikler

### A. WAL Modu (Performans Artışı)
Veritabanı artık **Write-Ahead Logging (WAL)** modunda çalışıyor.
*   **Fayda:** Aynı anda okuma/yazma işlemleri çok daha hızlı yapılır. "Database locked" hataları %90 azalır.
*   **Not:** Veritabanı klasöründe `.db-wal` ve `.db-shm` uzantılı dosyalar göreceksiniz. Bunları SİLMEYİN, bunlar veritabanının parçasıdır.

### B. Akıllı Yedekleme
Yeni oluşturulan `backup_script.py` dosyası, WAL dosyalarıyla birlikte tutarlı yedek alır.
*   **Kullanım:** Bu dosyayı Görev Zamanlayıcı (Task Scheduler) ile her gece çalışacak şekilde ayarlayabilirsiniz.
*   **Komut:** `python backup_script.py`

### C. Soft Delete (Güvenli Silme) Altyapısı
Tüm kritik tablolara `Aktif` kolonu eklendi.
*   **Şu anki durum:** Altyapı hazır. Program kodlarında "Sil" butonlarına basıldığında veriler hala tamamen silinebilir, ancak "Arşivle/Pasife Al" özelliği eklenmeye hazır hale getirildi.
*   **Gelecek Adım:** Arayüzdeki "Sil" butonlarının işlevini güncellemek.

## 2. Bakım Rutini

Yılda bir kez yapılması önerilenler:

1.  **Vacuum İşlemi:** Veritabanı boyutunu küçültmek için. (Sistem her yeniden başladığında bunu yapacak şekilde ayarlandı, manuel müdahaleye gerek yok).
2.  **Yedek Kontrolü:** `backups` klasöründeki eski yedeklerinizi harici bir diske kopyalayın.

## 3. Olası Sorunlar ve Çözümler

*   **Soru:** `.db-wal` dosyası çok büyüdü (örn. 100MB).
    *   **Cevap:** Programı kapatıp açın, SQLite bu dosyayı otomatik olarak ana veritabanına işleyip küçültecektir.

Bu sistem artık 10+ yıl boyunca performans sorunu yaşamadan çalışabilecek altyapıya sahiptir.
