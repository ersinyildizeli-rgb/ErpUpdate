from app import create_app
from models import db, Finance
import sys

def find_check():
    app = create_app()
    with app.app_context():
        # Tìm bản ghi có số séc 123456
        # SQLite comparison might be case sensitive or not depending on context,
        # but the screenshot clearly shows "Çek No: 123456"
        records = Finance.query.filter(Finance.Aciklama.ilike('%123456%')).all()
        if not records:
            # Try searching by amount if description search fails
            records = Finance.query.filter(Finance.Tutar == 12000.0).all()
            if not records:
                print("Kayıt bulunamadı.")
                return
        
        print(f"{len(records)} kayıt bulundu.")
        for r in records:
            print(f"ID: {r.FinansID}")
            print(f"Açıklama: {r.Aciklama}")
            print(f"Kategori: {r.Kategori}")
            print(f"Tutar: {r.Tutar}")
            print("-" * 20)

        # Silme işlemi
        for r in records:
            # We want to delete THIS specific check (ID 123456)
            if "123456" in str(r.Aciklama):
                db.session.delete(r)
                print(f"ID: {r.FinansID} siliniyor...")
        
        db.session.commit()
        print("İşlem tamamlandı.")

if __name__ == "__main__":
    find_check()
