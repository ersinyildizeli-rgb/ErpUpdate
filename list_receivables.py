from app import create_app
from models import db, Receivable

def list_receivables():
    app = create_app()
    with app.app_context():
        recs = Receivable.query.all()
        print(f"Total Receivable records: {len(recs)}")
        for r in recs:
            print(f"ID: {r.AlacakID} | Tutar: {r.AnaTutar} | Desc: {r.Alacakli}")

if __name__ == "__main__":
    list_receivables()
