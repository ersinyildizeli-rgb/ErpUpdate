from app import create_app
from models import db, Finance, Receivable, Debt

def search_all():
    app = create_app()
    with app.app_context():
        print("Checking Finance table...")
        recs = Finance.query.all()
        for r in recs:
            if 12000 in str(r.Tutar) or "123456" in str(r.Aciklama):
                print(f"FINANCE FOUND: ID {r.FinansID} | {r.Aciklama} | {r.Tutar}")
        
        print("\nChecking Receivable table...")
        recs = Receivable.query.all()
        for r in recs:
            if 12000 in str(r.AnaTutar) or "123456" in str(r.Alacakli):
                print(f"RECEIVABLE FOUND: ID {r.AlacakID} | {r.Alacakli} | {r.AnaTutar}")

        print("\nChecking Debt table...")
        recs = Debt.query.all()
        for r in recs:
            if 12000 in str(r.AnaTutar) or "123456" in str(r.Alacakli):
                print(f"DEBT FOUND: ID {r.BorcID} | {r.Alacakli} | {r.AnaTutar}")

if __name__ == "__main__":
    search_all()
