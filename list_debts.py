from app import create_app
from models import db, Debt

def list_debts():
    app = create_app()
    with app.app_context():
        recs = Debt.query.all()
        print(f"Total Debt records: {len(recs)}")
        for r in recs:
            print(f"ID: {r.BorcID} | Tutar: {r.AnaTutar} | Desc: {r.Alacakli}")

if __name__ == "__main__":
    list_debts()
