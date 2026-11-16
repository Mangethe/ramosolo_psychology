"""Independent synthetic acceptance probes. Known gaps are strict expected failures."""
import re
from datetime import timedelta
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import (Admission, ClinicalRecord, ExternalPractitioner, Appointment,
                    ContinuityEvent, ContinuityNotification, Patient)
from medical_services import utcnow, statistics
from test_medical import env, as_user
from test_continuity import approve, create_event, submit, event


def test_multiple_diagnoses_do_not_multiply_existing_admission_metrics(env):
    p=env[2][0];now=utcnow()
    for content in ['Confirmed synthetic A','Confirmed synthetic B','Provisional synthetic C','Amendment: synthetic A superseded']:
        db.session.add(ClinicalRecord(institution_id=p.institution_id,patient_id=p.id,
            author_id=p.doctor_id,kind='diagnoses',content=content))
    db.session.add(Admission(patient_id=p.id,facility='Synthetic historical facility',
        admitted_at=now-timedelta(days=20),discharged_at=now-timedelta(days=18)))
    db.session.commit()
    actual=db.session.scalar(select(func.count(Admission.id)).where(Admission.patient_id==p.id))
    multiplied=db.session.scalar(select(func.count(Admission.id)).join(
        ClinicalRecord, ClinicalRecord.patient_id==Admission.patient_id).where(Admission.patient_id==p.id))
    assert actual==2 and multiplied==8  # negative control: a naive join is unsafe
    assert statistics([p])[0]['admitted']==1  # this metric counts current patients, not admission episodes
    rows=list(db.session.scalars(select(ClinicalRecord).where(ClinicalRecord.patient_id==p.id)))
    assert len(rows)==4 and rows[0].content=='Confirmed synthetic A'


@pytest.mark.xfail(strict=True, reason='GAP: diagnosis status, severity and amendment linkage are unstructured free text')
def test_acceptance_structured_diagnosis_history():
    assert {'status','severity','supersedes_id'} <= set(ClinicalRecord.__table__.columns.keys())


def test_unknown_admission_date_is_rejected_and_ongoing_stay_preserved(env):
    existing=env[4]
    row=Admission(patient_id=env[2][1].id,facility='Synthetic unknown date',admitted_at=None)
    db.session.add(row)
    with pytest.raises(IntegrityError):db.session.flush()
    db.session.rollback()
    assert existing.discharged_at is None
    assert statistics([env[2][0]])[0]['admitted']==1


@pytest.mark.xfail(strict=True, reason='GAP: unknown-date and planned-admission states have no representation')
def test_acceptance_unknown_dates_and_planned_readmission():
    assert Admission.admitted_at.nullable
    assert 'status' in Admission.__table__.columns


def test_repeated_stays_facility_change_and_psychiatrist_references_preserve_prior_rows(env):
    p=env[2][0];prior=env[4];oldfacility=prior.facility
    prior.discharged_at=utcnow()
    db.session.add(Admission(patient_id=p.id,facility='Synthetic next facility',admitted_at=utcnow()))
    for name in ['Synthetic psychiatrist before','Synthetic psychiatrist after']:
        db.session.add(ExternalPractitioner(patient_id=p.id,institution_id=p.institution_id,
            author_id=p.doctor_id,name=name,email='synthetic@example.test'))
    db.session.commit()
    stays=list(db.session.scalars(select(Admission).where(Admission.patient_id==p.id).order_by(Admission.id)))
    assert len(stays)==2 and stays[0].facility==oldfacility and stays[0].discharged_at
    assert stays[1].facility=='Synthetic next facility' and stays[1].discharged_at is None
    assert statistics([p])[0]['admitted']==1
    # These are independent records, not a validated transfer or effective-dated practitioner history.
    assert db.session.scalar(select(func.count(ExternalPractitioner.id)))==2


@pytest.mark.xfail(strict=True, reason='GAP: facility/practitioner effective dates and admission-time medical-aid snapshots are absent')
def test_acceptance_effective_dated_history_and_medical_aid():
    assert {'medical_aid_provider','psychiatrist_id','transfer_from_id'} <= set(Admission.__table__.columns.keys())


def test_pending_concern_missed_appointment_failed_delivery_and_resolution(env):
    approve(env);a=env[3][0]
    a.starts_at=utcnow()-timedelta(days=1);db.session.commit()
    client=as_user(env,'dr')
    for _ in range(2):client.post(f'/med/appointments/{a.id}/status',data={'status':'no_show'})
    missed=event()
    assert missed.category=='administrative' and not missed.definition
    assert db.session.scalar(select(func.count(ClinicalRecord.id)))==0
    submit(env,reason='Synthetic concern awaiting review')
    concern=event()
    assert concern.category=='patient_reported' and concern.state=='open'
    assert db.session.scalar(select(func.count(ClinicalRecord.id)))==0
    # Use a distinct future booking as the source for an observed delivery failure.
    future=Appointment(patient_id=a.patient_id,doctor_id=a.doctor_id,
        starts_at=utcnow()+timedelta(days=5),service='General consultation',status='scheduled')
    db.session.add(future);db.session.commit()
    for _ in range(2):create_event(env,'failed_reminder',appointment_id=future.id)
    failure=event();assert failure.category=='administrative'
    client=as_user(env,'dr')
    for _ in range(2):
        assert client.post(f'/med/continuity/{failure.id}',data=dict(
            action='sandbox_notification',channel='phone',detail='Synthetic preview')).status_code==302
    assert db.session.scalar(select(func.count(ContinuityNotification.id)))==1
    assert db.session.scalar(select(func.count(ContinuityEvent.id)))==3
    client.post(f'/med/continuity/{failure.id}',data=dict(action='close',detail='Synthetic delivery issue resolved'))
    assert failure.state=='closed' and concern.state=='open'


@pytest.mark.parametrize('role,expected', [('dr',3),('nurse',3),('admin',1),('dr_assist',1),('dr2',0)])
def test_every_continuity_chart_total_and_link_matches_authorized_records(env,role,expected):
    approve(env);create_event(env);submit(env)
    a=env[3][0]
    create_event(env,'failed_reminder',appointment_id=a.id)
    body=as_user(env,role).get('/med/charts/continuity').text
    visible=[int(v) for v in re.findall(r'href="/med/continuity/(\d+)"',body)]
    assert len(visible)==expected and len(set(visible))==len(visible)
    independent=list(db.session.scalars(select(ContinuityEvent)))
    if role in ('admin','dr_assist'):independent=[e for e in independent if e.category=='administrative']
    if role=='dr2':independent=[]
    assert set(visible)=={e.id for e in independent}
    for category in ('administrative','patient_reported','clinical'):
        expected_count=sum(e.category==category for e in independent)
        pattern=rf'<h2>{category.replace("_"," ").title()}</h2><strong>(\d+)</strong>'
        assert int(re.search(pattern,body).group(1))==expected_count


def test_acceptance_assistant_cannot_infer_admission_status_from_small_cohort(env):
    client=as_user(env,'dr_assist')
    dashboard=client.get('/med').data
    directory=client.get('/med/patients').data
    assert (b'Currently admitted' in dashboard,b'class="status admitted"' in directory)==(False,False)


def test_acceptance_invalid_zero_patient_filter_does_not_export_all(env):
    response=as_user(env,'dr').post('/med/exports',data={'resource':'operational','patient_id':'0'})
    assert response.status_code in (400,404)


def test_dashboard_metric_values_match_underlying_role_filtered_visits_and_stays(env):
    now=utcnow()
    for patient,days in [(env[2][0],10),(env[2][0],30),(env[2][1],200)]:
        db.session.add(Appointment(patient_id=patient.id,doctor_id=patient.doctor_id,
            starts_at=now-timedelta(days=days),status='completed',service='General consultation'))
    db.session.commit()
    expected={'dr':(1,0,1,0),'nurse':(1,0,1,0),'dr_assist':(1,0,1,0),
              'admin':(1,1,1,0),'dr2':(0,1,0,0)}
    labels=('Active patients','Inactive patients','Currently admitted','Not yet seen')
    for role,counts in expected.items():
        body=as_user(env,role).get('/med').text
        for label,count in zip(labels,counts):
            if role=='dr_assist' and label=='Currently admitted':
                assert label not in body
                continue
            match=re.search(r'class="metric-label">'+label+r'<span[^>]*>.*?</span></div><strong>(\d+)</strong>',body)
            assert match and int(match.group(1))==count,(role,label)
    assert b'Currently admitted' not in as_user(env,'patient').get('/med').data


def test_acceptance_future_readmission_is_not_counted_as_current_stay(env):
    patient=env[2][1]
    db.session.add(Admission(patient_id=patient.id,facility='Synthetic planned facility',
        admitted_at=utcnow()+timedelta(days=7),discharged_at=None))
    db.session.commit()
    assert statistics([patient])[0]['admitted']==0
