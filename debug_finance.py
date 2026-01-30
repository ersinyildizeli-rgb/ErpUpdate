from app import create_app
from models import db, Finance

def list_recent():
    app = create_app()
    with app.app_context():
        records = Finance.query.order_by(Finance.Tarih.desc(), Finance.FinansID.desc()).limit(20).all()
        for r in records:
            print(f"ID: {r.FinansID} | Tarih: {r.Tarih} | Tutar: {r.Tutar}")
            print(f"Açıklama: {r.Aciklama}")
            print(f"Kategori: {r.Kategori}")
            print("-" * 30)

if __name__ == "__main__":
    list_recent()
