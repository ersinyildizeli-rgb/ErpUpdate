from app import create_app
from models import db, Finance

def list_all_finance():
    app = create_app()
    with app.app_context():
        records = Finance.query.all()
        print(f"Total Finance records: {len(records)}")
        for r in records:
            print(f"ID: {r.FinansID} | Tarih: {r.Tarih} | Tutar: {r.Tutar} | Tur: {r.IslemTuru}")
            print(f"Açıklama: {r.Aciklama}")
            print(f"Kategori: {r.Kategori}")
            print("-" * 30)

if __name__ == "__main__":
    list_all_finance()
