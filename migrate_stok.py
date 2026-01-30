from app import create_app, db
from models import Urun, StokHareketi

app = create_app()
with app.app_context():
    db.create_all()
    print("Stok ve Depo tabloları başarıyla oluşturuldu.")
