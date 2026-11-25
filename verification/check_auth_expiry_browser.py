"""Exercise the privacy screen in an installed Chromium browser using only synthetic data."""
import argparse
import os
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.update(PYTHON_DOTENV_DISABLED='1', APP_ENV='test', DATABASE_URL='sqlite://',
                  SUPABASE_DB_URL='', AUTH_SSO_ENABLED='0', AUTH_REQUIRE_STAFF_MFA='1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyotp
from cryptography.fernet import Fernet
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

import multi_factor
from app import create_app
from extensions import db
from models import AccountVerification, Authenticator, ClinicalRecord, Institution, Membership, Patient, User

SAVED = 'Synthetic existing diagnosis for browser verification'
DRAFT = 'Synthetic unsaved clinical narrative'
PASSWORD = 'Synthetic-browser-only-password'


def synthetic_app(key):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-browser-test-only',
        'AUTH_IDLE_TIMEOUT': timedelta(seconds=13), 'AUTH_WARNING_SECONDS': 8,
        'AUTH_MFA_KEY': key, 'AUTH_REQUIRE_STAFF_MFA': True})
    seed = pyotp.random_base32()
    with app.app_context():
        db.create_all()
        institution = Institution(name='Synthetic institution', kind='medical')
        doctor = User(name='Synthetic doctor', email='browser@example.test')
        doctor.set_password(PASSWORD)
        db.session.add_all((institution, doctor))
        db.session.flush()
        db.session.add(Membership(user_id=doctor.id, institution_id=institution.id, role='dr'))
        db.session.add(AccountVerification(user_id=doctor.id, verified_email=doctor.email, verified_at=1))
        db.session.add(Authenticator(user_id=doctor.id, encrypted_secret=Fernet(key).encrypt(seed.encode()),
                                     last_counter=0))
        patient = Patient(name='Synthetic patient', doctor_id=doctor.id, institution_id=institution.id)
        db.session.add(patient)
        db.session.flush()
        db.session.add(ClinicalRecord(institution_id=institution.id, patient_id=patient.id,
                                      author_id=doctor.id, kind='diagnoses', content=SAVED))
        db.session.commit()
        path = f'/med/patients/{patient.id}/records/diagnoses'
    return app, seed, path


def csrf(response):
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text())[1]


def authenticate(context, origin, seed, counter_time, clinical_path):
    api = context.request
    login = api.get(origin + '/auth/login')
    start = api.post(origin + '/auth/login', form={'csrf_token': csrf(login),
        'email': 'browser@example.test', 'password': PASSWORD})
    assert start.url.endswith('/auth/mfa')
    assert api.get(origin + clinical_path, max_redirects=0).status == 302
    code = pyotp.TOTP(seed).at(datetime.fromtimestamp(counter_time, timezone.utc))
    result = api.post(origin + '/auth/mfa', form={'csrf_token': csrf(start), 'code': code})
    assert result.url.endswith('/med') and result.ok


def verify_cleared(page):
    expect(page.get_by_role('dialog')).to_have_accessible_name('Your session has ended', timeout=18000)
    expect(page.get_by_role('link', name='Sign in again')).to_be_focused()
    assert page.locator('main, textarea').count() == 0
    assert SAVED not in page.content() and DRAFT not in page.content()
    assert page.evaluate('async () => localStorage.length + sessionStorage.length + (await indexedDB.databases()).length') == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', required=True, help='Installed Chromium executable path')
    args = parser.parse_args()
    app, seed, path = synthetic_app(Fernet.generate_key())
    original_clock = multi_factor.clock
    now = [int(time.time())]
    multi_factor.clock = lambda: now[0]
    server = make_server('127.0.0.1', 0, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.browser,
                args=['--disable-background-networking'])
            for width, height, mobile in ((1280, 800, False), (390, 844, True)):
                context = browser.new_context(viewport={'width': width, 'height': height}, is_mobile=mobile)
                authenticate(context, origin, seed, now[0], path)
                page = context.new_page()
                page.goto(origin + path)
                expect(page.get_by_text(SAVED)).to_be_visible()
                page.get_by_role('textbox', name='Record content').fill(DRAFT)
                dialog = page.get_by_role('dialog')
                expect(dialog).to_be_visible(timeout=9500)
                bounds = dialog.bounding_box()
                assert 0 <= bounds['x'] and bounds['x'] + bounds['width'] <= width
                stay = dialog.get_by_role('button', name='Stay signed in')
                expect(stay).to_be_focused()
                page.keyboard.press('Tab')
                expect(dialog.get_by_role('button', name='Log out now')).to_be_focused()
                page.keyboard.press('Shift+Tab')
                expect(stay).to_be_focused()
                if not mobile:
                    stay.click()
                    expect(dialog).not_to_be_visible()
                    expect(page.get_by_role('textbox', name='Record content')).to_have_value(DRAFT)
                context.set_offline(True)
                verify_cleared(page)
                assert page.url == origin + '/auth/login'
                context.set_offline(False)
                assert context.request.get(origin + path, max_redirects=0).status == 302
                page.get_by_role('link', name='Sign in again').click()
                expect(page.get_by_role('heading', name='Welcome back.')).to_be_visible()
                now[0] += 30
                authenticate(context, origin, seed, now[0], path)
                page.goto(origin + path)
                expect(page.get_by_text(SAVED)).to_be_visible()
                expect(page.get_by_role('textbox', name='Record content')).to_have_value('')

                if not mobile:
                    stored = context.storage_state()
                    with browser.new_context(java_script_enabled=False, storage_state=stored) as no_scripts:
                        blocked = no_scripts.new_page()
                        blocked.goto(origin + path)
                        expect(blocked.get_by_text(SAVED)).not_to_be_visible()
                        expect(blocked.get_by_text('JavaScript is required', exact=False)).to_be_visible()
                context.close()
                now[0] += 30
                print(f'{width}×{height}: keyboard, offline expiry, storage, fresh MFA and record reload verified')
            browser.close()
    finally:
        multi_factor.clock = original_clock
        server.shutdown()


if __name__ == '__main__':
    main()
