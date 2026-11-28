"""Synthetic leak canaries only; never load real credentials or patient files."""
import csv
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import time
import pytest
from flask import g, Flask
from sqlalchemy import select,func
from app import create_app
from config import settings
from extensions import db
from models import ClinicalRecord,Patient,Appointment
from test_medical import env,as_user

SECRET='SYNTHETIC_SECRET_CANARY_53e4978c'
CLINICAL='SYNTHETIC_UNAUTHORIZED_CLINICAL_31bf8'


def seed_canaries(env):
    app,users,patients,*_=env
    app.config.update(GITHUB_PAT_TOKEN=SECRET,SUPABASE_SERVICE_ROLE_KEY=SECRET,
        DATABASE_URL='postgresql://synthetic:'+SECRET+'@invalid.example.test/no_connection',PRIVATE_SETTING=SECRET)
    for p in patients:
        db.session.add(ClinicalRecord(institution_id=p.institution_id,patient_id=p.id,author_id=p.doctor_id,
            kind='diagnoses',content=CLINICAL+'_'+str(p.id)))
    db.session.commit()


@pytest.mark.parametrize('role',[None,'patient','dr_assist','nurse','dr','admin'])
def test_direct_urls_response_source_and_exports_do_not_leak(env,role):
    seed_canaries(env);app=env[0]
    client=as_user(env,role) if role else app.test_client()
    foreign=env[2][2]
    paths=['/','/book','/auth/login','/med','/med/appointments','/med/patients','/med/calendar',
        '/med/my-care-plan','/med/check-in','/med/coordination/consent','/med/my-actions','/med/charts/continuity',
        '/admin/users','/admin/requests','/admin/audit',
        f'/med/patients/{foreign.id}',f'/med/patients/{foreign.id}/records/diagnoses',
        f'/med/patients/{foreign.id}/care-plan']
    for path in paths:
        r=client.get(path)
        assert r.status_code<500,path
        assert SECRET.encode() not in r.data,path
        assert CLINICAL.encode() not in r.data,path
        assert b'FOREIGN PRIVATE PATIENT' not in r.data,path
        assert r.headers['Cache-Control']=='no-store'
        assert 'Cookie' in r.headers['Vary']
        assert 'Access-Control-Allow-Origin' not in r.headers
    r=client.post('/med/exports',data={'resource':'diagnoses','patient_id':foreign.id})
    assert r.status_code in (302,403,404) and CLINICAL.encode() not in r.data
    if role == 'dr':
        patient = env[2][0]
        contents = ('\tSynthetic content', '  ＝1+1', '\ufeff=1+1', 'Ordinary synthetic content')
        db.session.add_all(ClinicalRecord(institution_id=patient.institution_id, patient_id=patient.id,
            author_id=env[1]['dr'].id, kind='diagnoses', content=content) for content in contents)
        db.session.commit()
        export = client.post('/med/exports', data={'resource': 'diagnoses', 'patient_id': patient.id})
        assert export.status_code == 200 and export.headers['Cache-Control'] == 'no-store'
        cells = {row['clinician_authored_content'] for row in csv.DictReader(export.get_data(as_text=True).splitlines())}
        assert {"'" + content for content in contents[:3]} | {contents[3]} <= cells
    if role:
        with client.session_transaction() as s:
            assert SECRET not in repr(dict(s)) and CLINICAL not in repr(dict(s))
            assert not any(key in s for key in ('diagnoses','notes','patient_records','care_plan'))


@pytest.mark.parametrize('role',[None,'patient','dr_assist','nurse','dr','admin'])
def test_crafted_mutations_ignore_client_role_and_institution(env,role):
    seed_canaries(env);client=as_user(env,role) if role else env[0].test_client()
    foreign=env[2][2];before=db.session.scalar(select(func.count(ClinicalRecord.id)))
    r=client.post(f'/med/patients/{foreign.id}/records/diagnoses',data={
        'role':'dr','institution_id':foreign.institution_id,'doctor_id':foreign.doctor_id,
        'patient_id':foreign.id,'content':CLINICAL,'clinician_confirmed':'on'})
    assert r.status_code in (302,403,404)
    assert db.session.scalar(select(func.count(ClinicalRecord.id)))==before
    r=client.post('/institutions',data={'institution_id':foreign.institution_id,'role':'admin'})
    assert r.status_code==(302 if role is None else 403)


@pytest.mark.parametrize('role', ['dr', 'dr_assist'])
def test_appointment_reads_require_the_staff_schedule_assignment(env, role, monkeypatch):
    from datetime import datetime
    from Med.MedWebsite.controllers import portal

    patient = env[2][0]
    now = datetime(2032, 11, 4, 8)
    monkeypatch.setattr(portal, 'utcnow', lambda: now)
    appointment = Appointment(patient_id=patient.id, doctor_id=env[1]['dr2'].id,
        starts_at=now + timedelta(hours=1), service='Synthetic other clinician service',
        institution_id=patient.institution_id, status='scheduled')
    db.session.add(appointment)
    db.session.commit()
    client = as_user(env, role)
    for path in ('/med', '/med/appointments', '/med/calendar', f'/med/patients/{patient.id}'):
        response = client.get(path)
        assert response.status_code == 200
        assert b'Synthetic other clinician service' not in response.data
    assert client.get('/med/calendar/availability', query_string={
        'patient_id': patient.id, 'appointment_id': appointment.id, 'day': '2032-11-04'}).status_code == 404
    assert client.post(f'/med/appointments/{appointment.id}/status',
        data={'status': 'cancelled', 'version': 1}).status_code == 404
    assert b'Synthetic other clinician service' in as_user(env, 'patient').get('/med/appointments').data


def test_static_asset_inventory_and_source_download_probes(env,tmp_path):
    app=env[0];root=tmp_path/'public';root.mkdir();(root/'css').mkdir()
    (root/'css/style.css').write_text('body { color: black; }',encoding='utf-8')
    # Deliberately place fake sensitive files UNDER the public directory. Flask's
    # default static handler would serve them; the reviewed asset inventory must not.
    forbidden=['.env','.git/config','app.py','database.sql','backup.zip','handoff.md','debug.log',
        'uploads/private.html','css/style.css.map','css/style.css.bak','private.css','config.json']
    for filename in forbidden:
        path=root/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(SECRET,encoding='utf-8')
    baseline=Flask('synthetic_baseline',static_folder=str(root),static_url_path='/static')
    assert baseline.test_client().get('/static/.env').data==SECRET.encode()
    app.static_folder=str(root);client=app.test_client()
    css=client.get('/static/css/style.css')
    assert css.status_code==200 and css.mimetype=='text/css'
    assert css.headers['X-Content-Type-Options']=='nosniff'
    for name in forbidden:
        for method in ('get','head'):
            r=getattr(client,method)('/static/'+name)
            assert r.status_code==404 and SECRET.encode() not in r.data
    for path in ['/.env','/.git/config','/app.py','/config.py','/migrations/009_assistant_calendar.sql',
        '/verification/calendar-review.md','/instance/lesonto.db','/docs/assistant-calendar.md','/static/',
        '/static/../config.py','/static/%2e%2e/config.py','/static/%252e%252e/config.py',
        '/static/css%5c..%5c.env','/download?path=../.env','/uploads/private.html','/console','/?__debugger__=yes&cmd=resource&f=debugger.js']:
        r=client.get(path)
        assert SECRET.encode() not in r.data
        if not path.startswith('/?'):assert r.status_code in (400,404)
        assert b'Werkzeug Debugger' not in r.data
    r=as_user(env,'patient').get('/static/css/style.css')
    assert r.status_code==200 and r.headers['Cache-Control']=='no-store'


def test_static_symlink_cannot_escape_public_root(env,tmp_path):
    root=tmp_path/'public';(root/'css').mkdir(parents=True)
    private=tmp_path/'synthetic-private.txt';private.write_text(SECRET,encoding='utf-8')
    try:(root/'css/style.css').symlink_to(private)
    except OSError:
        pytest.skip('OS does not permit synthetic symlink creation; deployment check remains required')
    env[0].static_folder=str(root)
    r=env[0].test_client().get('/static/css/style.css')
    assert r.status_code==404 and SECRET.encode() not in r.data
    (root/'css/style.css').unlink()
    (root/'css/style.css').write_text(SECRET, encoding='utf-8')
    linked_root = tmp_path/'linked-public'
    linked_root.symlink_to(root, target_is_directory=True)
    env[0].static_folder = str(linked_root)
    r = env[0].test_client().get('/static/css/style.css')
    assert r.status_code == 404 and SECRET.encode() not in r.data


def test_generic_errors_do_not_render_or_log_canary_exception(env,caplog):
    from flask import request
    app=env[0];app.config.update(PROPAGATE_EXCEPTIONS=False)
    @app.post('/synthetic-error-probe/<opaque>')
    def synthetic_error(opaque):
        raise RuntimeError([opaque, request.args['q'], request.cookies['test_cookie'],
                            request.headers['Authorization'], *request.form.values()])
    client=app.test_client()
    client.set_cookie('test_cookie', 'synthetic-cookie-canary')
    values = {'password': SECRET, 'otp': 'synthetic-otp-canary', 'clinical': CLINICAL}
    canaries = (*values.values(), 'synthetic-path-canary', 'synthetic-query-canary',
                'synthetic-cookie-canary', 'synthetic-auth-canary')
    r=client.post('/synthetic-error-probe/synthetic-path-canary?q=synthetic-query-canary',
                  data=values, headers={'Authorization': 'Bearer synthetic-auth-canary'})
    assert r.status_code==500
    assert all(value not in caplog.text and value.encode() not in r.data for value in canaries)
    assert 'Unhandled application error type=RuntimeError endpoint=synthetic_error' in caplog.text
    for path,method,data,code in [('/auth/logout','get',None,405),('/book','post',{'x':'x'*140000},413),('/not-a-route','get',None,404)]:
        r=getattr(client,method)(path,data=data)
        assert r.status_code==code and r.headers['Cache-Control']=='no-store'
        assert b'Traceback' not in r.data and SECRET.encode() not in r.data


def test_escape_html_and_do_not_redirect_sensitive_queries(env):
    patient=env[2][0];patient.name='<script>'+CLINICAL+'</script>';db.session.commit()
    r=as_user(env,'dr_assist').get('/med/patients')
    assert b'<script>' not in r.data and b'&lt;script&gt;' in r.data
    g.pop('_login_user',None)
    r=env[0].test_client().get('/med?reason='+CLINICAL)
    assert r.headers['Location'].endswith('/auth/login') and CLINICAL not in r.headers['Location']
    assert 'config' not in env[0].jinja_env.globals


def test_real_login_expiry_idle_absolute_and_cookie_payload(env):
    import portal_sessions
    from models import PortalSession

    app=env[0];client=app.test_client()
    assert client.post('/auth/login',data={'email':'dr@example.test','password':'Testing-password-123'}).status_code==302
    assert client.get('/med').status_code==200
    with client.session_transaction() as s:
        assert '_user_id' in s and not any('clinical' in key for key in s)
        row = db.session.get(PortalSession, portal_sessions.digest(s['portal_token']))
    row.absolute_expires_at = portal_sessions.clock()
    db.session.commit()
    assert client.get('/med').status_code==302
    client=as_user(env,'dr')
    with client.session_transaction() as s:
        row = db.session.get(PortalSession, portal_sessions.digest(s['portal_token']))
    row.idle_expires_at = portal_sessions.clock()
    db.session.commit()
    assert client.get('/med').status_code==302
    client=as_user(env,'dr')
    with client.session_transaction() as s:s.pop('portal_token')
    assert client.get('/med').status_code==302


def production_env(monkeypatch,sslmode='verify-full'):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('FLASK_SECRET_KEY','synthetic-only-32-character-signing-key')
    monkeypatch.setenv('DATABASE_URL','postgresql://synthetic_runtime@localhost/synthetic?sslmode='+sslmode)
    monkeypatch.setenv('APP_TRUSTED_HOSTS','portal.example.test');monkeypatch.setenv('FLASK_DEBUG','0')
    monkeypatch.setenv('AUTH_PUBLIC_URL', 'https://portal.example.test')
    monkeypatch.setenv('APP_TRUSTED_PROXY_HOPS','0')


@pytest.mark.parametrize('mode',['disable','allow','prefer','require','verify-ca',''])
def test_production_rejects_weak_database_tls(monkeypatch,mode):
    production_env(monkeypatch,mode)
    with pytest.raises(RuntimeError,match='sslmode=verify-full'):settings()


@pytest.mark.parametrize('origin', ['http://portal.example.test', 'https://other.example.test',
    'https://portal.example.test:invalid', 'https://portal.example.test/#', 'https://@portal.example.test'])
def test_production_rejects_misconfigured_portal_origin(monkeypatch, origin):
    production_env(monkeypatch)
    monkeypatch.setenv('AUTH_PUBLIC_URL', origin)
    with pytest.raises(RuntimeError, match='AUTH_PUBLIC_URL'):
        create_app()


def test_production_host_https_debug_and_proxy_boundaries(monkeypatch):
    production_env(monkeypatch)
    app=create_app();client=app.test_client()
    assert client.get('/',base_url='https://portal.example.test').status_code==200
    assert client.get('/',base_url='https://evil.example.test').status_code==400
    assert client.get('/',base_url='http://portal.example.test',headers={'X-Forwarded-Proto':'https'}).status_code==400
    assert client.get('/',base_url='http://portal.example.test').status_code==400
    r=client.get('/',base_url='https://portal.example.test')
    assert 'max-age=' in r.headers['Strict-Transport-Security']
    assert app.config['SESSION_COOKIE_SECURE'] and app.config['SESSION_COOKIE_HTTPONLY']
    assert not app.debug and not app.config['PROPAGATE_EXCEPTIONS']
    monkeypatch.setenv('APP_TRUSTED_PROXY_HOPS','1')
    proxy_app = create_app()
    from flask import request

    @proxy_app.get('/synthetic-proxy-test')
    def proxy_test():
        return {'address': request.remote_addr}

    r = proxy_app.test_client().get('/synthetic-proxy-test', base_url='http://portal.example.test',
        headers={'X-Forwarded-Proto': 'http, https', 'X-Forwarded-For': '192.0.2.80, 192.0.2.1'})
    assert r.status_code == 200 and r.json == {'address': '192.0.2.1'}
    monkeypatch.setenv('FLASK_DEBUG','1')
    with pytest.raises(RuntimeError,match='FLASK_DEBUG'):create_app()
    monkeypatch.setenv('FLASK_DEBUG','0');monkeypatch.delenv('APP_TRUSTED_HOSTS')
    with pytest.raises(RuntimeError,match='TRUSTED_HOSTS'):create_app()


def test_csrf_normal_forms_cors_and_cross_origin_posts(env):
    app=env[0];app.config['WTF_CSRF_ENABLED']=True
    client=app.test_client();response=client.get('/auth/login')
    token=re.search(rb'name="csrf_token" value="([^"]+)"',response.data).group(1).decode()
    assert client.post('/auth/login',data={'email':'dr@example.test','password':'Testing-password-123'}).status_code==400
    # Valid CSRF is preserved for legitimate same-origin forms.
    response=client.post('/auth/login',data={'csrf_token':token,'email':'dr@example.test','password':'Testing-password-123'},headers={'Origin':'http://localhost'})
    assert response.status_code==302
    # The parent fixture retains an app context across requests. Real HTTP
    # requests have a new g; discard the previous login form's cached CSRF token.
    g.pop('csrf_token',None)
    body=client.get('/med/appointments').data
    token=re.search(rb'name="csrf_token" value="([^"]+)"',body).group(1).decode()
    response=client.post('/auth/logout',data={'csrf_token':token},headers={'Origin':'https://attacker.example.test'})
    assert response.status_code==403 and 'Access-Control-Allow-Origin' not in response.headers
    assert client.get('/med').status_code==200
    assert client.get('/med',headers={'Origin':'https://attacker.example.test'}).headers.get('Access-Control-Allow-Origin') is None
    assert response.headers['Referrer-Policy']=='strict-origin'


def test_waitress_accepts_forwarding_only_from_the_configured_peer(monkeypatch):
    from flask import request
    from waitress.proxy_headers import proxy_headers_middleware

    production_env(monkeypatch)
    app = create_app()

    @app.get('/synthetic-proxy-test')
    def proxy_test():
        return {'address': request.remote_addr}

    app.wsgi_app = proxy_headers_middleware(app.wsgi_app, trusted_proxy='127.0.0.1',
        trusted_proxy_count=1, trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'})
    client = app.test_client()
    headers = {'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '192.0.2.1',
               'X-Forwarded-Host': 'untrusted.example.test'}
    port = 'http://portal.example.test'
    trusted = client.get('/synthetic-proxy-test', base_url=port, headers=headers,
                         environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
    assert trusted.status_code == 200 and trusted.json == {'address': '192.0.2.1'}
    assert 'Strict-Transport-Security' in trusted.headers
    assert client.get('/synthetic-proxy-test', base_url=port, headers=headers,
                      environ_overrides={'REMOTE_ADDR': '192.0.2.2'}).status_code == 400


def test_clinical_submission_stays_out_of_cookies_redirects_and_logs(env,caplog):
    from test_continuity import approve
    from models import ContinuityEvent
    approve(env);client=as_user(env,'patient')
    r=client.post('/med/check-in',data={'patient_id':env[2][0].id,'kind':'check_in',
        'reason':CLINICAL,'monitoring_understood':'on'})
    assert r.status_code==302 and CLINICAL not in r.headers['Location']
    assert CLINICAL not in caplog.text
    cookie=client.get_cookie(env[0].config['SESSION_COOKIE_NAME'])
    payload=env[0].session_interface.get_signing_serializer(env[0]).loads(cookie.value)
    assert CLINICAL not in repr(payload)
    assert db.session.scalar(select(ContinuityEvent.reason))==CLINICAL


def test_old_remember_cookie_and_tampered_session_do_not_restore_access(env):
    from flask_login.utils import encode_cookie
    app=env[0];client=app.test_client()
    # Reproduce a correctly signed legacy persistent cookie using SYNTHETIC key.
    client.set_cookie('remember_token',encode_cookie(env[1]['dr'].get_id()))
    assert client.get('/med').status_code==302
    g.pop('_login_user',None)
    client=as_user(env,'dr')
    cookie=client.get_cookie(app.config['SESSION_COOKIE_NAME']).value
    client.set_cookie(app.config['SESSION_COOKIE_NAME'],cookie+'tampered')
    g.pop('_login_user',None)
    assert client.get('/med').status_code==302


def test_login_rejects_oversized_values_without_truncation(env):
    client=env[0].test_client()
    r=client.post('/auth/login',data={'email':'dr@example.test','password':'Testing-password-123'+'x'*600})
    assert r.status_code==200 and b'Unable to sign in' in r.data
    r=client.post('/auth/login',data={'email':'x'*260+'@example.test','password':'Testing-password-123'})
    assert r.status_code==200 and b'Unable to sign in' in r.data


def test_auth_throttle_is_shared_private_and_precedes_password_hashing(env, monkeypatch):
    import auth
    from models import DeliveryLimit

    app = env[0]
    clock = [100_000]
    hashes = []
    monkeypatch.setattr(auth.portal_sessions, 'clock', lambda: clock[0])

    def failed_password(*args):
        hashes.append(None)
        return False

    monkeypatch.setattr(auth, 'check_password_hash', failed_password)
    form = {'email': 'missing@example.test', 'password': 'synthetic-invalid'}
    for index in range(60):
        response = app.test_client().post('/auth/login', data=form,
            environ_overrides={'REMOTE_ADDR': f'2001:db8::1:{index}'})
        assert response.status_code == 200
    client = app.test_client()
    response = client.post('/auth/login', data=form, environ_overrides={'REMOTE_ADDR': '2001:db8::2'},
                           headers={'X-Forwarded-For': '192.0.2.2'})
    assert response.status_code == 429 and response.headers['Retry-After'] == '900'
    assert response.headers['Cache-Control'] == 'no-store' and len(hashes) == 60
    for _ in range(10):
        assert client.post('/auth/verification', data=form,
            environ_overrides={'REMOTE_ADDR': '2001:db8::2'}).status_code == 302
    assert client.post('/auth/verification', data=form,
        environ_overrides={'REMOTE_ADDR': '2001:db8::2'}).status_code == 429
    keys = db.session.scalars(select(DeliveryLimit.key)).all()
    assert len(keys) == 2 and all(re.fullmatch(r'auth:[0-9a-f]{64}', key) for key in keys)
    clock[0] += 900
    assert client.post('/auth/login', data=form,
        environ_overrides={'REMOTE_ADDR': '2001:db8::2'}).status_code == 200


def test_invalid_origin_fails_without_parsing_or_reserving_auth_limit(env):
    from models import DeliveryLimit

    response = env[0].test_client().post('/auth/login', headers={'Origin': 'https://['})
    assert response.status_code == 403
    assert db.session.scalar(select(func.count()).select_from(DeliveryLimit)) == 0


def test_every_registered_post_rejects_missing_csrf(env):
    app = env[0]
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    for rule in app.url_map.iter_rules():
        if 'POST' in rule.methods:
            _, path = rule.build(dict.fromkeys(rule.arguments, 1))
            assert client.post(path).status_code == 400, rule.endpoint


def test_release_scan_reads_public_zip_members_and_skips_private_members(tmp_path, monkeypatch):
    from stat import S_IFLNK
    from zipfile import ZipFile, ZipInfo
    from verification.check_release_secrets import artifact_inventory

    release = tmp_path / 'synthetic-release.zip'
    with ZipFile(release, 'w') as archive:
        archive.writestr('release/.env', b'Excluded synthetic fixture')
        archive.writestr('release/.env/private.py', b'Excluded synthetic fixture')
        archive.writestr('release/.flaskenv', b'Excluded synthetic fixture')
        archive.writestr('release/.env. /private.py', b'Excluded synthetic fixture')
        archive.writestr('release/static/style.css:private.txt', b'Excluded synthetic fixture')
        archive.writestr('release/.env.example', b'AUTH_OIDC_CLIENT_SECRET=replace-with-injected-secret')
        archive.writestr('release/static/app.css', '/*\nGMAIL_APP_PASSWORD=' + 'abcd ' * 3 + 'abcd\n*/')
        archive.writestr('release/Caddyfile', 'AUTH_MFA_KEY=' + '0' * 32)
        archive.writestr('release/deploy.json', '{\n"GMAIL_OAUTH_CLIENT_SECRET": "' + '0' * 20 + '"\n}')
        linked = ZipInfo('release/static/linked.css')
        linked.create_system = 3
        linked.external_attr = (S_IFLNK | 0o777) << 16
        archive.writestr(linked, '../private.css')
    original = ZipFile.read

    def public_read(self, entry, *args, **kwargs):
        assert entry.filename in ('release/.env.example', 'release/static/app.css',
                                  'release/Caddyfile', 'release/deploy.json')
        return original(self, entry, *args, **kwargs)

    monkeypatch.setattr(ZipFile, 'read', public_read)
    assert artifact_inventory(release) == {('release/.env', 'excluded path'),
        ('release/.flaskenv', 'excluded path'),
        ('release/.env/private.py', 'excluded path'), ('release/static/linked.css', 'excluded path'),
        ('release/.env. /private.py', 'excluded path'), ('release/static/style.css:private.txt', 'excluded path'),
        ('release/Caddyfile', 'literal environment signing key'),
        ('release/deploy.json', 'literal provider or SMS credential'),
        ('release/static/app.css', 'literal provider or SMS credential')}
