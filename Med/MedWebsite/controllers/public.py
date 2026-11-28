from flask import Response, current_app, render_template, request, redirect, url_for, flash
from sqlalchemy import select
from extensions import db
from models import Institution, BookingRequest
from medical_services import SERVICES, parse_local, utcnow
from policy_info import POLICY, OFFICIAL_LINKS, CARD
from security_email import trusted_origin
from . import bp


PUBLIC_SITE_PAGES = (
    ('med.home', 'Home'),
    ('med.inpatient', 'Inpatient enquiries'),
    ('med.book', 'Request an appointment'),
    ('med.governance', 'Privacy and practice information'),
    ('med.sitemap', 'Sitemap'),
)
POLICY_DRAFT_PAGES = (
    ('med.privacy_notice', 'POPIA / Privacy Notice'),
    ('med.cookies_policy', 'Cookies policy'),
    ('med.data_management', 'Data Management Declaration'),
    ('med.professional_information', 'Professional Information'),
)


def public_institution():
    selected = current_app.config['PUBLIC_INSTITUTION_ID']
    query = select(Institution).where(Institution.kind == 'medical')
    if selected:
        query = query.where(Institution.id == selected)
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


@bp.get('/cookies-policy')
def cookies_policy():
    return render_template('cookies_policy.html', policy=POLICY)


@bp.get('/sitemap')
def sitemap():
    return render_template('sitemap.html', pages=PUBLIC_SITE_PAGES, drafts=POLICY_DRAFT_PAGES)


@bp.get('/sitemap.xml')
def sitemap_xml():
    origin = trusted_origin(current_app.config['AUTH_PUBLIC_URL'], https_only=current_app.config['PRODUCTION'])
    locations = [origin + url_for(endpoint) for endpoint, _ in PUBLIC_SITE_PAGES]
    return Response(render_template('sitemap.xml', locations=locations), mimetype='application/xml')


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
    terms = current_app.config['BOOKING_TERMS']
    if request.method == 'POST':
        # Rendering a public enquiry form does not require a database. Resolve
        # the destination only when accepting a request.
        institution = public_institution()
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
            return render_template('book.html', services=SERVICES, values=request.form, terms=terms), 400
        db.session.add(BookingRequest(institution_id=institution.id, name=name, email=email,
            phone=phone, service=service, preferred_at=preferred, consent_at=utcnow()))
        db.session.commit()
        flash('Request received. This is not a confirmed appointment; the practice will contact you.', 'success')
        return redirect(url_for('med.book'))
    return render_template('book.html', services=SERVICES, values={}, terms=terms)
