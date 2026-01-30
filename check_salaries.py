from app import create_app
from models import db, Personel
from sqlalchemy import func

def check_salaries():
    app = create_app()
    with app.app_context():
        s = db.session.query(func.sum(Personel.NetMaas)).scalar() or 0
        print(f"Total Salaries: {s}")

if __name__ == "__main__":
    check_salaries()
