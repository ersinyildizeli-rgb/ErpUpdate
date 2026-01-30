from app import create_app
from models import db, Finance

def find_12000():
    app = create_app()
    with app.app_context():
        recs = Finance.query.filter(Finance.Tutar == 12000).all()
        print(f"Found {len(recs)} records with 12000 TL")
        for r in recs:
            print(f"ID: {r.FinansID} | Desc: {r.Aciklama} | Cat: {r.Kategori}")

if __name__ == "__main__":
    find_12000()
