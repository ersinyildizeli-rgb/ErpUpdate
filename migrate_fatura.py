from app import create_app, db
from sqlalchemy import text
from models import Fatura, FaturaKalemi, StokHareketi

app = create_app()
with app.app_context():
    # Yeni tabloları oluştur
    db.create_all()
    
    # Mevcut StokHareketleri tablosuna FaturaID kolonu eklemek için SQLite ALT command
    try:
        db.session.execute(text("ALTER TABLE StokHareketleri ADD COLUMN FaturaID INTEGER REFERENCES Faturalar(FaturaID)"))
        db.session.commit()
        print("FaturaID kolonu StokHareketleri tablosuna eklendi.")
    except Exception as e:
        # Eğer kolon zaten varsa hata verecektir, yoksayabiliriz
        print(f"Bilgi: {e}")

    print("Fatura ve Fatura Kalemleri tabloları başarıyla oluşturuldu.")
