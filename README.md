# ERP Flask Backend (Local)

Bu proje, React/Stitch tasarımlarınızı kullanarak çalışacak, Flask + SQLAlchemy tabanlı bir yerel backend örneğidir.

Özellikler:
- `Personel`, `Finance`, `Puantaj`, `Company` modelleri (SQLite, kolay PostgreSQL'e geçiş)
- Dashboard, Personel CRUD, Finans yönetimi, Bordro hesaplama
- `DESIGN_DIR` değişkeni ile harici `templates`/`static` klasörleri kullanılabilir

Hızlı başlatma:

1. Ortam kurun (tercihen venv)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. (Opsiyonel) Tasarımlarınızın bulunduğu klasör yolunu ayarlayın:

```powershell
$env:DESIGN_DIR = 'C:/Proje/Tasarımlar'
```

3. Uygulamayı çalıştırın:

```powershell
python app.py
```

Uygulama `http://127.0.0.1:5000` üzerinde çalışır.

Notlar:
- `config.py` içindeki `DESIGN_DIR` değişkeni default olarak `C:/Proje/Tasarımlar`'a işaret eder. Ortam değişkeniyle kolayca değiştirilebilir.
- Tasarım klasörünüz yoksa proje içindeki `internal_templates/` fallback olarak kullanılır.
- Türkçe ve UTF-8 desteği: şablonlar UTF-8 olarak ayarlanmıştır; API JSON cevapları da Türkçe karakterleri korumak için `app.config['JSON_AS_ASCII']=False` olarak yapılandırılmıştır.
