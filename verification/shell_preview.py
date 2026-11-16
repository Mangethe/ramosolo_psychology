"""Disposable loopback preview. Synthetic records, in-memory DB, no delivery."""
import os
import sys
from pathlib import Path
os.environ.update(PYTHON_DOTENV_DISABLED='1',APP_ENV='test',DATABASE_URL='sqlite://',
    FLASK_SECRET_KEY='synthetic-shell-preview-only')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import timedelta
import json
from werkzeug.serving import make_server,WSGIRequestHandler
from app import create_app
from extensions import db
from models import User,Institution,Membership,Patient,CareAssignment,Appointment,ClinicalRecord
from medical_services import utcnow


class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):pass


app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite://',
    'SQLALCHEMY_ENGINE_OPTIONS':{},'SECRET_KEY':'synthetic-shell-preview-only',
    'PRIVATE_CANARY':'SYNTHETIC_BROWSER_SECRET_8a73'})
with app.app_context():
    db.create_all()
    institution=Institution(name='Synthetic preview practice',kind='medical')
    db.session.add(institution);db.session.flush();users={}
    for role in ('dr','dr_assist','nurse','admin','patient'):
        user=User(name='Preview '+role,email=role+'@example.test')
        user.set_password('Synthetic-preview-123!');db.session.add(user);db.session.flush();users[role]=user
        db.session.add(Membership(institution_id=institution.id,user_id=user.id,role=role,
            supervising_doctor_id=users['dr'].id if role=='dr_assist' else None))
    p=Patient(institution_id=institution.id,doctor_id=users['dr'].id,
        user_id=users['patient'].id,name='Synthetic preview patient')
    db.session.add(p);db.session.flush()
    db.session.add(CareAssignment(patient_id=p.id,nurse_id=users['nurse'].id))
    db.session.add(Appointment(patient_id=p.id,doctor_id=p.doctor_id,starts_at=utcnow()+timedelta(days=3),
        service='General consultation',status='scheduled'))
    foreign=Institution(name='Synthetic other institution',kind='medical')
    db.session.add(foreign);db.session.flush()
    foreign_patient=Patient(institution_id=foreign.id,doctor_id=users['dr'].id,
        name='SYNTHETIC_BROWSER_FOREIGN_PATIENT_2b19')
    db.session.add(foreign_patient);db.session.flush()
    db.session.add(ClinicalRecord(institution_id=foreign.id,patient_id=foreign_patient.id,
        author_id=users['dr'].id,kind='diagnoses',content='SYNTHETIC_BROWSER_CLINICAL_743a'))
    db.session.commit()

if __name__=='__main__':
    server=make_server('127.0.0.1',0,app,request_handler=QuietHandler)
    print(json.dumps({'port':server.server_port}),flush=True)
    server.serve_forever()
