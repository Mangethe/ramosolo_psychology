import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort
from sqlalchemy import select
from extensions import db
from models import Institution, BookingRequest
from medical_services import SERVICES, parse_local, utcnow
from policy_info import POLICY, OFFICIAL_LINKS, CARD
from . import bp


def public_institution():
    selected = os.getenv('PUBLIC_INSTITUTION_ID')
    query = select(Institution).where(Institution.kind == 'medical')
    if selected:
        query = query.where(Institution.id == int(selected))
    return db.session.scalar(query.order_by(Institution.id))


@bp.get('/')
def home():
    return render_template('index.html')


@bp.get('/governance')
def governance():
    return render_template('governance.html', policy=POLICY, official=OFFICIAL_LINKS)


@bp.get('/privacy-notice')
def privacy_notice():
    return render_template('privacy_notice.html',policy=POLICY,official=OFFICIAL_LINKS)


@bp.get('/data-management')
def data_management():
    return render_template('data_management.html',policy=POLICY,official=OFFICIAL_LINKS)


@bp.get('/professional-information')
def professional_information():
    return render_template('professional_information.html',policy=POLICY,official=OFFICIAL_LINKS,card=CARD)


@bp.get('/inpatient')
def inpatient():
    return render_template('inpatient.html')


@bp.route('/book', methods=['GET', 'POST'])
def book():
    institution = public_institution()
    if request.method == 'POST':
        if not institution:
            flash('Online requests are not configured yet. Please contact the practice directly.', 'error')
            return redirect(url_for('med.book'))
        name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        service = request.form.get('service_type', '')
        try:
            preferred = parse_local(request.form.get('preferred_at', ''))
            if not 2 <= len(name) <= 120 or not 3 <= len(phone) <= 40:
                raise ValueError()
            if len(email) > 254 or '@' not in email or '.' not in email.split('@')[-1]:
                raise ValueError()
            if service not in SERVICES or preferred <= utcnow() or not request.form.get('consent'):
                raise ValueError()
        except (ValueError, TypeError):
            flash('Check your contact details, service, future date and consent.', 'error')
            return render_template('book.html', services=SERVICES, values=request.form), 400
        db.session.add(BookingRequest(institution_id=institution.id, name=name, email=email,
            phone=phone, service=service, preferred_at=preferred, consent_at=utcnow()))
        db.session.commit()
        flash('Request received. This is not a confirmed appointment; the practice will contact you.', 'success')
        return redirect(url_for('med.book'))
    return render_template('book.html', services=SERVICES, values={})
