from app import create_app
from models import db, Document

app = create_app()
with app.app_context():
    try:
        # Simulate /belgeler logic
        query = Document.query
        belgeler = query.order_by(Document.EklemeTarihi.desc()).all()
        print(f"Successfully fetched {len(belgeler)} documents.")
        
        # Check attributes
        if len(belgeler) > 0:
            doc = belgeler[0]
            print(f"Doc Kategori: {getattr(doc, 'Kategori', 'MISSING')}")
            print(f"Doc RelationType: {getattr(doc, 'RelationType', 'MISSING')}")
    except Exception as e:
        import traceback
        traceback.print_exc()
