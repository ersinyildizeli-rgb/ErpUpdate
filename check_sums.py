from app import create_app
from models import db, Finance
from sqlalchemy import func

def check_sums():
    app = create_app()
    with app.app_context():
        # Sum of all income
        total_inc = db.session.query(func.sum(Finance.Tutar)).filter(Finance.IslemTuru == 'Gelir').scalar() or 0
        print(f"Total Database Income: {total_inc}")
        
        # Sum of all income EXCLUDING checks
        clean_inc = db.session.query(func.sum(Finance.Tutar)).filter(
            Finance.IslemTuru == 'Gelir',
            ~Finance.Aciklama.ilike('%çek%'),
            ~Finance.Aciklama.ilike('%ÇEK%'),
            ~Finance.Aciklama.ilike('%cek%'),
            ~Finance.Aciklama.ilike('%CEK%'),
            ~Finance.Kategori.ilike('%çek%'),
            ~Finance.Kategori.ilike('%ÇEK%'),
            ~Finance.Kategori.ilike('%cek%'),
            ~Finance.Kategori.ilike('%CEK%')
        ).scalar() or 0
        print(f"Clean Income (No Checks): {clean_inc}")
        
        # List ALL records again to be absolutely sure
        recs = Finance.query.all()
        for r in recs:
            print(f"ID: {r.FinansID} | Tutar: {r.Tutar} | Desc: {r.Aciklama} | Cat: {r.Kategori}")

if __name__ == "__main__":
    check_sums()
