from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from extensions import db
from models import Appointment, Admission, Patient

TZ = ZoneInfo('Africa/Johannesburg')
SERVICES = ['Individual therapy', 'Children and family support', 'Couples therapy',
            'Assessment enquiry', 'Inpatient coordination', 'General consultation']


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_local(value):
    return datetime.fromisoformat(value).replace(tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)


def statistics(patients, now=None, include_admissions=True):
    now = now or utcnow()
    ids = [p.id for p in patients]
    latest = dict(db.session.execute(select(Appointment.patient_id, func.max(Appointment.starts_at))
        .join(Patient, Patient.id == Appointment.patient_id).where(
        Appointment.patient_id.in_(ids), Appointment.status == 'completed',
        (Appointment.institution_id == Patient.institution_id) | Appointment.institution_id.is_(None),
        Appointment.starts_at <= now).group_by(Appointment.patient_id)).all())
    cutoff = now - timedelta(days=90)
    active = sum(seen >= cutoff for seen in latest.values())
    inactive = sum(seen < cutoff for seen in latest.values())
    admitted = set(db.session.scalars(select(Admission.patient_id).where(
        Admission.patient_id.in_(ids), Admission.discharged_at.is_(None),Admission.admitted_at<=now))) if include_admissions else set()
    return dict(total=len(ids), active=active, inactive=inactive,
                never_seen=len(ids)-len(latest), admitted=len(admitted)), latest, admitted


def doctors(institution_id):
    from models import Membership, User
    return list(db.session.scalars(select(User).join(Membership, Membership.user_id == User.id).where(
        Membership.institution_id == institution_id, Membership.role == 'dr',
        Membership.enabled.is_(True), User.enabled.is_(True)).order_by(User.name)))
