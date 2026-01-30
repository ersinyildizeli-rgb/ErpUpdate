import pytest
import sys
import os

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from models import User, Company

@pytest.fixture
def app():
    # Use a separate test database
    test_db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test.db')
    
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{test_db_path}",
        "WTF_CSRF_ENABLED": False  # Disable CSRF for easier testing
    })

    # Create tables
    with app.app_context():
        db.create_all()
        
        # app.py creates a default admin if none exists.
        # So we check if admin exists before adding.
        if not User.query.filter_by(KullaniciAdi='admin').first():
            admin = User(KullaniciAdi='admin', Rol='admin', Aktif=True)
            admin.set_password('admin123')
            db.session.add(admin)
        
        # Create a user with limited role
        if not User.query.filter_by(KullaniciAdi='user').first():
            user = User(KullaniciAdi='user', Rol='personel', Aktif=True)
            user.set_password('user123')
            db.session.add(user)

        # Create default company settings
        if not Company.query.first():
            company = Company(SirketAdi='Test Corp', MesaiUcreti=100.0)
            company.set_settings({
                'currency': 'TRY',
                'monthly_working_hours': 225,
                'weekly_schedule': {
                    'sunday': {'multiplier': 2.0}
                }
            })
            db.session.add(company)
        
        db.session.commit()

    yield app

    # Cleanup
    with app.app_context():
        db.session.remove()
        db.drop_all()
    
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()
