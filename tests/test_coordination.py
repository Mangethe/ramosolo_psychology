from datetime import timedelta
from html import unescape
import io
import re
import uuid
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import (DischargeFollowup,Referral,ReferralClinical,CommunicationDecision,CareReview,
    CareReviewSignoff,CoordinationPolicy,CoordinationHistory,Admission,CarePlan,User,Membership,
    CareAssignment,ContinuityNotification,AuditEvent)
from models import CoordinationCoverage
from medical_services import utcnow
from coordination_services import communication_allowed
from test_medical import env,as_user
from test_continuity import approve,plan_form,local,consent,create_event,event


def policy(env,kind='discharge'):
    return as_user(env,'dr').post('/med/coordination/policies',data=dict(kind=kind,
        deadline_hours='48',due_soon_days='3',instructions='Synthetic approved steps',approved='on'))


def discharged(env):
    assert as_user(env,'dr').post(f'/med/admissions/{env[4].id}/discharge').status_code==302
    return db.session.scalar(select(DischargeFollowup))


def plan_discharge(env,row,**extra):
    data=dict(action='approve_planning',version=row.version,owner_id=env[1]['nurse'].id,
        due_at=local(utcnow()+timedelta(days=1)),team='Synthetic care team')
    data.update(extra)
    return as_user(env,'dr').post(f'/med/admissions/{env[4].id}/follow-up',data=data)


def new_referral(env,direction='outgoing',**extra):
    data=dict(patient_id=env[2][0].id,direction=direction,other_party='Synthetic receiving service',
        referred_at=local(utcnow()-timedelta(days=2)),requested_action='Arrange agreed appointment',
        owner_id=env[1]['dr'].id,due_at=local(utcnow()+timedelta(days=1)),submission_key=uuid.uuid4().hex)
    data.update(extra)
    response=as_user(env,'dr').post('/med/referrals',data=data)
    return response,db.session.scalar(select(Referral).order_by(Referral.id.desc())),data


def referral_action(env,row,role='dr',**data):
    return as_user(env,role).post(f'/med/referrals/{row.id}',data=dict(version=row.version,**data))


def test_actual_discharge_without_planning_remains_possible_and_actionable(env):
    row=discharged(env)
    assert env[4].discharged_at and not row.planning_complete and row.owner_id is None and row.due_at is None
    page=as_user(env,'admin').get('/med/actions')
    assert page.status_code==200 and b'Planning incomplete' in page.data and b'Unassigned' in page.data
    assert f'admission:{env[4].id}'.encode() in page.data
    before=db.session.scalar(select(func.count(DischargeFollowup.id)))
    as_user(env,'dr').post(f'/med/admissions/{env[4].id}/discharge')
    assert db.session.scalar(select(func.count(DischargeFollowup.id)))==before==1


def test_discharge_requires_approved_policy_owner_and_due_before_signoff(env):
    row=discharged(env)
    assert plan_discharge(env,row).status_code==400
    policy(env)
    assert plan_discharge(env,row,owner_id='').status_code==400
    assert plan_discharge(env,row).status_code==302
    assert row.planning_complete and row.policy_id and row.status=='open'
    assert row.admission_id==env[4].id and row.patient_id==env[2][0].id
    assert as_user(env,'admin').post(f'/med/admissions/{env[4].id}/follow-up',data=dict(
        action='approve_planning',version=row.version,owner_id=env[1]['nurse'].id)).status_code==403


def test_attempt_contact_success_and_completion_are_distinct(env):
    policy(env);row=discharged(env);plan_discharge(env,row)
    path=f'/med/admissions/{env[4].id}/follow-up'
    assert as_user(env,'nurse').post(path,data=dict(version=row.version,action='contact_attempt',contact_outcome='no_answer')).status_code==302
    assert row.status=='open'
    assert as_user(env,'dr').post(path,data=dict(version=row.version,action='complete',
        outcome='followup_completed',closure_reason='Synthetic resolved')).status_code==400
    assert as_user(env,'nurse').post(path,data=dict(version=row.version,action='contact_attempt',contact_outcome='successful_contact')).status_code==302
    assert row.status=='contacted'
    assert as_user(env,'nurse').post(path,data=dict(version=row.version,action='complete',outcome='followup_completed',closure_reason='Synthetic')).status_code==403
    assert as_user(env,'dr').post(path,data=dict(version=row.version,action='complete',outcome='followup_completed',closure_reason='Agreed follow-up completed')).status_code==302
    assert row.status=='completed' and row.closure_reason
    assert b'admission:1' not in as_user(env,'dr').get('/med/actions').data
    assert b'admission:1' in as_user(env,'dr').get('/med/actions?status=completed').data


def test_cover_reassignment_history_and_stale_updates(env):
    from models import AccountVerification
    policy(env);row=discharged(env);plan_discharge(env,row)
    cover=User(name='Synthetic cover',email='cover@example.test',password_hash='not-a-login',session_version=1)
    db.session.add(cover);db.session.flush();env[1]['cover']=cover
    db.session.add(AccountVerification(user_id=cover.id, verified_email=cover.email, verified_at=1))
    db.session.add(Membership(user_id=cover.id,institution_id=env[2][0].institution_id,role='nurse'))
    db.session.add(CareAssignment(patient_id=env[2][0].id,nurse_id=cover.id));db.session.commit()
    path=f'/med/admissions/{env[4].id}/follow-up';old=row.version
    assert as_user(env,'admin').post(path,data=dict(version=old,action='assign',owner_id=env[1]['nurse'].id,
        cover_id=cover.id,owner_unavailable='on',due_at=local(utcnow()-timedelta(hours=1)),team='Cover team')).status_code==302
    assert row.owner_unavailable and row.cover_id==cover.id
    assert as_user(env,'admin').post(path,data=dict(version=old,action='assign',owner_id=env[1]['dr'].id)).status_code==409
    assert b'Owner unavailable' in as_user(env,'cover').get('/med/actions').data
    assert as_user(env,'cover').post(path,data=dict(version=row.version,action='escalate')).status_code==302
    entries=list(db.session.scalars(select(CoordinationHistory).where(CoordinationHistory.source_type=='discharge_followup')))
    assert any(h.cover_id==cover.id for h in entries) and row.escalated
    assert as_user(env,'admin').post(path,data=dict(version=row.version,action='assign',owner_id=env[1]['foreign'].id)).status_code==400


def test_episode_patient_mismatch_is_rejected_by_database(env):
    row=DischargeFollowup(institution_id=env[2][0].institution_id,patient_id=env[2][1].id,admission_id=env[4].id)
    db.session.add(row)
    with pytest.raises(IntegrityError):db.session.flush()
    db.session.rollback()


@pytest.mark.parametrize('direction',['incoming','outgoing'])
def test_referral_transitions_not_completed_when_sent(env,direction):
    response,row,_=new_referral(env,direction)
    assert response.status_code==302 and row.status=='draft'
    assert referral_action(env,row,action='transition',status='completed').status_code==400
    if direction=='outgoing':
        assert referral_action(env,row,action='transition',status='sent',consent_channel='phone').status_code==400
        consent(env,'referral_sharing','phone',row.other_party)
        assert referral_action(env,row,action='transition',status='sent',consent_channel='phone').status_code==302
        assert row.status=='sent' and row.completed_at is None
    assert referral_action(env,row,action='transition',status='acknowledged',response_at=local(utcnow()-timedelta(days=1))).status_code==302
    assert referral_action(env,row,action='transition',status='accepted',response_at=local(utcnow()-timedelta(hours=4))).status_code==302
    assert referral_action(env,row,action='transition',status='appointment_arranged',appointment_id=env[3][1].id).status_code==400
    assert referral_action(env,row,action='transition',status='appointment_arranged',appointment_at=local(utcnow()-timedelta(hours=1))).status_code==302
    assert referral_action(env,row,role='admin',action='transition',status='completed',completed_at=local(utcnow()),closure_reason='Synthetic').status_code==403
    assert referral_action(env,row,action='transition',status='completed',completed_at=local(utcnow()-timedelta(minutes=1)),closure_reason='Clinician confirmed agreed completion').status_code==302
    assert row.status=='completed'
    assert referral_action(env,row,action='transition',status='sent').status_code==409


def test_referral_duplicate_and_private_information_boundaries(env):
    _,row,data=new_referral(env)
    assert as_user(env,'dr').post('/med/referrals',data=data).status_code==302
    assert db.session.scalar(select(func.count(Referral.id)))==1
    assert as_user(env,'dr').post('/med/referrals',data=dict(data,requested_action='Changed payload')).status_code==409
    assert referral_action(env,row,action='clinical_note',clinical_content='SYNTHETIC PRIVATE REFERRAL').status_code==302
    assert db.session.scalar(select(func.count(ReferralClinical.id)))==1
    for role in ('admin','dr_assist'):
        body=as_user(env,role).get(f'/med/referrals/{row.id}').data
        assert b'SYNTHETIC PRIVATE REFERRAL' not in body
        assert referral_action(env,row,role=role,action='clinical_note',clinical_content='FORGED').status_code==403
    before=db.session.scalar(select(func.count(User.id)))
    assert before==len(env[1])  # external service names never provision accounts


def test_referral_declined_cancelled_and_outstanding_information(env):
    _,row,_=new_referral(env,'incoming')
    assert referral_action(env,row,role='dr_assist',action='update',next_action='Await response',outstanding_information='Appointment availability').status_code==302
    assert row.next_action=='Await response'
    assert referral_action(env,row,action='transition',status='cancelled',closure_reason='Duplicate request resolved').status_code==302
    assert referral_action(env,row,action='update',next_action='Reopen').status_code==409
    _,second,_=new_referral(env,'incoming')
    referral_action(env,second,action='transition',status='acknowledged',response_at=local(utcnow()-timedelta(hours=2)))
    assert referral_action(env,second,action='transition',status='declined',response_at=local(utcnow()),closure_reason='Receiving service declined').status_code==302


def test_consent_withdrawal_suppresses_existing_sandbox_queue_and_preserves_history(env):
    approve(env);create_event(env);e=event()
    response=as_user(env,'dr').post(f'/med/continuity/{e.id}',data=dict(action='sandbox_notification',detail='Preview',channel='phone'))
    assert response.status_code==302
    notice=db.session.scalar(select(ContinuityNotification));assert notice.state=='queued'
    consent(env,'administrative_contact','phone',status='withdrawn')
    assert notice.state=='suppressed' and 'withdrawn' in notice.result_code
    decisions=list(db.session.scalars(select(CommunicationDecision).where(CommunicationDecision.channel=='phone')))
    assert [d.status for d in decisions]==['granted','withdrawn']
    assert as_user(env,'dr').post(f'/med/continuity/{e.id}',data=dict(action='sandbox_notification',detail='Retry',channel='phone')).status_code==400
    assert e.state=='open'  # suppression does not complete care


def test_purpose_channel_scope_and_unverified_destination(env):
    approve(env);create_event(env);e=event()
    consent(env,'referral_sharing','phone','Specific service')
    assert as_user(env,'dr').post('/med/coordination/consent',data=dict(patient_id=env[2][0].id,
        purpose='administrative_contact',channel='phone',scope='practice',status='granted',destination='unverified',
        timezone='Africa/Johannesburg',method='patient-entered',notice_version='Synthetic v2')).status_code==302
    assert as_user(env,'dr').post(f'/med/continuity/{e.id}',data=dict(action='sandbox_notification',detail='Preview',channel='phone')).status_code==400
    assert db.session.scalar(select(func.count(CommunicationDecision.id)))==3
    assert consent(env,'referral_sharing','phone','Other service',status='withdrawn').status_code==302
    assert db.session.scalar(select(CommunicationDecision).where(CommunicationDecision.scope=='Specific service')).status=='granted'
    assert as_user(env,'patient').post('/med/coordination/consent',data=dict(patient_id=env[2][1].id,
        purpose='reminders',channel='portal',scope='practice',status='withdrawn')).status_code==404


def test_contact_window_and_timezone_validation(env,monkeypatch):
    from datetime import datetime
    approve(env);create_event(env);e=event()
    data=dict(patient_id=env[2][0].id,purpose='administrative_contact',channel='phone',scope='practice',
        status='granted',destination='Synthetic verified',verified='on',timezone='Africa/Johannesburg',
        method='in-person synthetic',notice_version='Synthetic-v2',contact_start='13:00',contact_end='14:00')
    assert as_user(env,'dr').post('/med/coordination/consent',data=data).status_code==302
    monkeypatch.setattr('coordination_services.utcnow',lambda:datetime(2026,11,16,10,0))
    assert as_user(env,'dr').post(f'/med/continuity/{e.id}',data=dict(action='sandbox_notification',detail='Preview',channel='phone')).status_code==400
    assert as_user(env,'dr').post('/med/coordination/consent',data=dict(data,timezone='not-a-zone')).status_code==400
    assert as_user(env,'dr').post('/med/coordination/consent',data=dict(data,contact_end='')).status_code==400


def test_care_plan_review_versions_actual_signoff_next_date_and_sharing(env):
    plan=approve(env);review=db.session.scalar(select(CareReview))
    path=f'/med/care-plans/{plan.id}/review'
    before=db.session.scalar(select(func.count(CareReviewSignoff.id)))
    assert as_user(env,'dr').get(path).status_code==200
    assert db.session.scalar(select(func.count(CareReviewSignoff.id)))==before==0
    assert as_user(env,'dr').post(path,data=dict(version=review.version,review_id=review.id,action='complete',
        reviewed_at=local(utcnow()-timedelta(minutes=1)),next_review_at=local(utcnow()+timedelta(days=10)),outcome='SYNTHETIC PRIVATE REVIEW')).status_code==302
    assert review.status=='completed' and review.reviewer_id==env[1]['dr'].id
    pending=db.session.scalar(select(CareReview).where(CareReview.status=='pending'))
    assert pending.sequence==2
    assert as_user(env,'dr').post(path,data=dict(version=pending.version,review_id=review.id,action='complete',
        reviewed_at=local(utcnow()),next_review_at=local(utcnow()+timedelta(days=12)),outcome='duplicate')).status_code==409
    form=plan_form(env);form['goals']='New agreed version';form['share_with_patient']='on'
    as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/care-plan',data=form)
    assert review.status=='completed' and pending.status=='superseded'
    assert db.session.scalar(select(func.count(CarePlan.id)))==2
    assert b'New agreed version' not in as_user(env,'patient').get('/med/my-care-plan').data
    consent(env,'care_plan_sharing','portal')
    body=as_user(env,'patient').get('/med/my-care-plan').data
    assert b'New agreed version' in body and b'SYNTHETIC PRIVATE REVIEW' not in body
    consent(env,'care_plan_sharing','portal',status='withdrawn')
    assert b'New agreed version' not in as_user(env,'patient').get('/med/my-care-plan').data


def test_review_unassigned_missing_dates_and_admin_read_only(env):
    plan=approve(env);review=db.session.scalar(select(CareReview));path=f'/med/care-plans/{plan.id}/review'
    assert as_user(env,'admin').post(path,data=dict(version=review.version,action='assign',owner_id='',due_at='')).status_code==302
    assert review.owner_id is None and review.due_at is None
    body=as_user(env,'admin').get('/med/actions?type=review').data
    assert b'Unassigned' in body and b'Missing due date' in body
    assert as_user(env,'admin').post(path,data=dict(version=review.version,action='complete')).status_code==403


@pytest.mark.parametrize('role',['dr','nurse','dr_assist','admin','patient'])
def test_roles_cross_patient_cross_institution_and_reassignment(env,role):
    row=discharged(env);_,ref,_=new_referral(env);plan=approve(env)
    client=as_user(env,role)
    assert client.get('/med/actions').status_code==(403 if role=='patient' else 200)
    expected=403 if role=='patient' else 404 if role=='nurse' else 200
    assert client.get(f'/med/referrals/{ref.id}').status_code==expected
    assert client.post('/med/referrals',data=dict(patient_id=env[2][2].id)).status_code==(403 if role=='patient' else 404)
    assert client.post('/med/coordination/consent',data=dict(patient_id=env[2][2].id)).status_code==404
    assert client.get(f'/med/admissions/{env[4].id}/follow-up').status_code==(
        403 if role in ('patient','dr_assist') else 404 if role=='nurse' else 200)
    assert client.get('/med/actions?institution='+str(env[2][2].institution_id)).status_code==(403)
    assert client.get(f'/med/care-plans/{plan.id}/review').status_code==(
        403 if role in ('patient','dr_assist') else 404 if role=='nurse' else 200)


def test_my_actions_counts_drilldowns_filters_and_exports_match(env):
    policy(env);policy(env,'review');row=discharged(env);_,ref,_=new_referral(env);plan=approve(env)
    ref.owner_id=None;ref.due_at=utcnow()-timedelta(days=1);db.session.commit()
    client=as_user(env,'admin');response=client.get('/med/actions?status=active')
    assert response.status_code==200
    body=response.text
    keys=re.findall('data-action-key="([^"]+)"',body)
    assert len(keys)==len(set(keys))==3
    for href,label,count in re.findall(r'<a class="metric" href="([^"]+)"><span>([^<]+)</span><strong>(\d+)</strong>',body):
        detail=client.get(unescape(href))
        assert len(re.findall('data-action-key="([^"]+)"',detail.text))==int(count),(label,detail.text)
    assert len(re.findall('data-action-key="([^"]+)"',client.get('/med/actions?type=referral&due=overdue').text))==1
    assert client.post('/med/actions/export?type=referral').status_code==404


def test_csrf_files_and_operational_export_no_clinical_text(env):
    _,ref,_=new_referral(env)
    referral_action(env,ref,action='clinical_note',clinical_content='DO NOT EXPORT THIS CLINICAL TEXT')
    response=as_user(env,'dr').post('/med/actions/export?type=referral')
    assert response.status_code==200 and b'DO NOT EXPORT' not in response.data
    assert as_user(env,'dr').post(f'/med/referrals/{ref.id}',data=dict(version=ref.version,action='update',
        upload=(io.BytesIO(b'SYNTHETIC ONLY'),'referral.txt')),content_type='multipart/form-data').status_code==400
    env[0].config['WTF_CSRF_ENABLED']=True
    client=as_user(env,'dr')
    for path in ['/med/referrals','/med/coordination/consent','/med/coordination/policies','/med/actions/export',
                 f'/med/referrals/{ref.id}']:
        assert client.post(path,data={}).status_code==400
    logs=list(db.session.scalars(select(AuditEvent)))
    assert all('DO NOT EXPORT' not in str((log.action,log.resource_type,log.resource_id)) for log in logs)


def test_existing_in_app_outbox_opt_in_preserved_then_withdrawn_by_purpose(env):
    # Synthetic metadata-compatible legacy infrastructure; no transport adapter is called.
    db.session.execute(text('''CREATE TABLE communication_preferences (
        id INTEGER PRIMARY KEY, institution_id INTEGER NOT NULL, patient_id INTEGER,
        in_app_enabled BOOLEAN NOT NULL, in_app_consent_at TIMESTAMP, version INTEGER NOT NULL,
        changed_by INTEGER, changed_at TIMESTAMP)'''))
    db.session.execute(text('''CREATE TABLE notification_outbox (
        id INTEGER PRIMARY KEY, institution_id INTEGER NOT NULL, appointment_id INTEGER NOT NULL,
        channel TEXT NOT NULL, state TEXT NOT NULL, sent_at TIMESTAMP, invalidated_at TIMESTAMP,result_code TEXT)'''))
    patient=env[2][0]
    db.session.execute(text('INSERT INTO communication_preferences VALUES (1,:inst,:patient,TRUE,:now,1,NULL,:now)'),
        dict(inst=patient.institution_id,patient=patient.id,now=utcnow()))
    db.session.execute(text("INSERT INTO notification_outbox VALUES(1,:inst,:appt,'in_app','pending',NULL,NULL,''),(2,:inst,:appt,'in_app','sent',:now,NULL,'')"),
        dict(inst=patient.institution_id,appt=env[3][0].id,now=utcnow()))
    db.session.commit()
    assert as_user(env,'dr').post('/med/coordination/recheck-notifications',data={'patient_id':patient.id}).status_code==302
    assert db.session.execute(text('SELECT state FROM notification_outbox WHERE id=1')).scalar()=='pending'
    consent(env,'referral_sharing','phone','Synthetic service',status='withdrawn')
    assert db.session.execute(text('SELECT state FROM notification_outbox WHERE id=1')).scalar()=='pending'
    consent(env,'reminders','portal',status='withdrawn')
    assert db.session.execute(text('SELECT state FROM notification_outbox WHERE id=1')).scalar()=='cancelled'
    assert db.session.execute(text('SELECT state FROM notification_outbox WHERE id=2')).scalar()=='sent'
    assert not db.session.execute(text('SELECT in_app_enabled FROM communication_preferences')).scalar()


def test_existing_scheduling_followup_is_not_duplicated_in_my_actions(env):
    approve(env);create_event(env,'failed_reminder',appointment_id=env[3][0].id)
    db.session.execute(text('''CREATE TABLE attendance_followups (
      id INTEGER PRIMARY KEY,institution_id INTEGER,appointment_id INTEGER,rule TEXT,state TEXT,
      checked_at TIMESTAMP,revision INTEGER,owner_id INTEGER,due_at TIMESTAMP,escalated BOOLEAN)'''))
    db.session.execute(text("INSERT INTO attendance_followups VALUES (42,:inst,:appt,'delivery_failed','open',:now,1,:owner,:now,FALSE)"),
        dict(inst=env[2][0].institution_id,appt=env[3][0].id,now=utcnow(),owner=env[1]['dr'].id))
    db.session.commit()
    response=as_user(env,'dr').get('/med/actions?type=continuity')
    assert response.status_code==200
    assert b'attendance:42' in response.data and b'continuity:1' not in response.data
    assert as_user(env,'dr').post('/med/actions/scheduling/42',data={'version':1,'status':'acknowledged'}).status_code==302
    assert db.session.execute(text('SELECT state FROM attendance_followups')).scalar()=='acknowledged'


def test_patient_only_explicitly_shared_actions_and_private_review_excluded(env):
    row=discharged(env);_,ref,_=new_referral(env)
    assert b'admission' not in as_user(env,'patient').get('/med/my-agreed-actions').data.lower()
    policy(env)
    plan_discharge(env,row,patient_visible='on',agreed_action='Call the agreed team')
    referral_action(env,ref,action='update',next_action='Contact receiving service',patient_visible='on')
    response=as_user(env,'patient').get('/med/my-agreed-actions')
    assert response.status_code==200 and b'Call the agreed team' in response.data
    assert b'Arrange agreed appointment' in response.data


def cover(env,kind='review',status='granted'):
    return as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/coordination-cover',data=dict(
        user_id=env[1]['dr2'].id,kind=kind,status=status,valid_until=local(utcnow()+timedelta(days=2))))


def test_covering_clinician_has_explicit_workflow_only_access(env):
    plan=approve(env);review=db.session.scalar(select(CareReview));path=f'/med/care-plans/{plan.id}/review'
    assert as_user(env,'dr2').get(path).status_code==404
    assert cover(env).status_code==302
    assert as_user(env,'admin').post(path,data=dict(action='assign',version=review.version,
        owner_id=env[1]['dr2'].id,due_at=local(review.due_at),owner_unavailable='on')).status_code==302
    client=as_user(env,'dr2');response=client.get(path)
    assert response.status_code==200 and b'Agreed synthetic goal' in response.data
    assert b'Synthetic practice definitions' not in response.data
    assert client.get(f'/med/patients/{env[2][0].id}/records/diagnoses').status_code==404
    assert client.get(f'/med/patients/{env[2][0].id}/care-plan').status_code==404
    assert client.get(f'/med/admissions/{env[4].id}/follow-up').status_code==404
    assert client.get(f'/med/patients/{env[2][0].id}/coordination-cover').status_code==404
    assert client.post(path,data=dict(action='complete',version=review.version,review_id=review.id,
        reviewed_at=local(utcnow()-timedelta(minutes=1)),next_review_at=local(utcnow()+timedelta(days=7)),
        outcome='Synthetic covering clinician review')).status_code==302
    assert review.reviewer_id==env[1]['dr2'].id


def test_cover_revocation_expiry_and_admin_cannot_grant_clinical_coverage(env):
    plan=approve(env);review=db.session.scalar(select(CareReview));path=f'/med/care-plans/{plan.id}/review'
    for role in ('admin','nurse','dr_assist','patient'):
        assert as_user(env,role).post(f'/med/patients/{env[2][0].id}/coordination-cover',data={}).status_code==403
    cover(env)
    assert as_user(env,'admin').post(path,data=dict(action='assign',version=review.version,
        owner_id=env[1]['dr2'].id,due_at=local(review.due_at))).status_code==302
    cover(env,status='withdrawn')
    assert as_user(env,'dr2').get(path).status_code==404
    assert b'Owner unavailable' in as_user(env,'admin').get('/med/actions?type=review').data
    cover(env)
    decision=db.session.scalar(select(CoordinationCoverage).order_by(CoordinationCoverage.id.desc()))
    decision.valid_until=utcnow()-timedelta(minutes=1);db.session.commit()
    assert as_user(env,'dr2').get(path).status_code==404
    assert review.status=='pending'
    assert db.session.scalar(select(func.count(CoordinationCoverage.id)))==3


def test_coverage_isolation_and_foreign_clinician_cannot_be_assigned(env):
    approve(env)
    assert as_user(env,'dr').post(f'/med/patients/{env[2][1].id}/coordination-cover',data={}).status_code==404
    assert as_user(env,'dr').post(f'/med/patients/{env[2][0].id}/coordination-cover',data=dict(
        user_id=env[1]['foreign'].id,kind='review',status='granted',valid_until=local(utcnow()+timedelta(days=1)))).status_code==400
    assert db.session.scalar(select(func.count(CoordinationCoverage.id)))==0
