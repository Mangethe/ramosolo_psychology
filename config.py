import os
import re
import secrets
from datetime import timedelta
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from booking_terms import approved_booking_terms


def settings():
    production = os.getenv('APP_ENV') == 'production'
    secret = os.getenv('FLASK_SECRET_KEY')
    public_institution = os.getenv('PUBLIC_INSTITUTION_ID', '').strip()
    if public_institution and not re.fullmatch(r'[1-9][0-9]{0,8}', public_institution):
        raise RuntimeError('PUBLIC_INSTITUTION_ID must be a positive institution ID.')
    public_institution_id = int(public_institution) if public_institution else None
    # Both names are documented by the protected Supabase workflow. An empty
    # DATABASE_URL must not hide a configured SUPABASE_DB_URL.
    url = (os.getenv('DATABASE_URL', '').strip()
           or os.getenv('SUPABASE_DB_URL', '').strip()
           or 'sqlite:///ramosolo.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    try:
        parsed_url=make_url(url)
    except (ArgumentError,ValueError):
        raise RuntimeError('Invalid server-side database configuration.') from None
    # The deployed private schema was intentionally renamed to ramosolo.
    # Explicit schema names still support historical/local installations.
    schema = os.getenv('DB_SCHEMA', 'ramosolo').strip()
    hosts=[host.strip() for host in os.getenv('APP_TRUSTED_HOSTS','').split(',') if host.strip()]
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*|\[::1\]', host) for host in hosts):
        raise RuntimeError('APP_TRUSTED_HOSTS must contain explicit hostnames.')
    proxy=os.getenv('APP_TRUSTED_PROXY_HOPS','0')
    if proxy not in ('0','1'):raise RuntimeError('APP_TRUSTED_PROXY_HOPS must be 0 or 1.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', schema):
        raise RuntimeError('DB_SCHEMA must be a lowercase SQL identifier.')
    if production and (not secret or len(secret) < 32 or secret.startswith('replace-')):
        raise RuntimeError('Set a random FLASK_SECRET_KEY of at least 32 characters.')
    if production and not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Production requires PostgreSQL. SQLite is for local demos.')
    if production and os.getenv('FLASK_DEBUG','').lower() not in ('','0','false','no','off'):
        raise RuntimeError('FLASK_DEBUG must be disabled in production.')
    engine = {'pool_pre_ping': True}
    if url.startswith('postgresql+'):
        # Poolers may ignore startup options. The engine sets the schema for
        # each transaction, including after a rollback on the same connection.
        engine['connect_args'] = {'connect_timeout': 10}
        if production and parsed_url.query.get('sslmode') != 'verify-full':
            raise RuntimeError('Production database connections require sslmode=verify-full.')
    return dict(SECRET_KEY=secret or secrets.token_hex(32),
        PUBLIC_INSTITUTION_ID=public_institution_id,
        BOOKING_TERMS=approved_booking_terms(os.getenv('BOOKING_TERMS_JSON'), public_institution_id,
                                            os.getenv('BOOKING_TERMS_APPROVED_SHA256')),
        SQLALCHEMY_DATABASE_URI=url, SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=int(os.getenv('AUTH_ABSOLUTE_SECONDS', '7200'))),
        MAX_CONTENT_LENGTH=131072,
        AUTH_IDLE_TIMEOUT=timedelta(seconds=int(os.getenv('AUTH_IDLE_SECONDS', '900'))),
        AUTH_WARNING_SECONDS=int(os.getenv('AUTH_WARNING_SECONDS', '120')),
        AUTH_PUBLIC_URL=os.getenv('AUTH_PUBLIC_URL', 'http://localhost:5000'),
        AUTH_SUPPORT_PHONE=os.getenv('AUTH_SUPPORT_PHONE'),
        AUTH_VERIFICATION_KEY=os.getenv('AUTH_VERIFICATION_KEY'),
        AUTH_VERIFICATION_SECONDS=int(os.getenv('AUTH_VERIFICATION_SECONDS', '3600')),
        AUTH_MFA_KEY=os.getenv('AUTH_MFA_KEY'),
        AUTH_REQUIRE_STAFF_MFA=os.getenv('AUTH_REQUIRE_STAFF_MFA', '1') == '1',
        AUTH_SSO_ENABLED=os.getenv('AUTH_SSO_ENABLED', '0') == '1',
        AUTH_OIDC_ISSUER=os.getenv('AUTH_OIDC_ISSUER'),
        AUTH_OIDC_CLIENT_ID=os.getenv('AUTH_OIDC_CLIENT_ID'),
        AUTH_OIDC_CLIENT_SECRET=os.getenv('AUTH_OIDC_CLIENT_SECRET'),
        AUTH_OIDC_REDIRECT_URI=os.getenv('AUTH_OIDC_REDIRECT_URI'),
        MAIL_PROVIDER=os.getenv('MAIL_PROVIDER', 'fake'),
        MAIL_LIVE_ENABLED=os.getenv('MAIL_LIVE_ENABLED', '0') == '1',
        MAIL_PILOT_RECIPIENTS=os.getenv('MAIL_PILOT_RECIPIENTS', ''),
        MAIL_DISPLAY_NAME=os.getenv('MAIL_DISPLAY_NAME', 'Ramosolo'),
        MAIL_REPLY_TO=os.getenv('MAIL_REPLY_TO', ''),
        GMAIL_DAILY_LIMIT=int(os.getenv('GMAIL_DAILY_LIMIT', '0')),
        GMAIL_OAUTH_CLIENT_ID=os.getenv('GMAIL_OAUTH_CLIENT_ID'),
        GMAIL_OAUTH_CLIENT_SECRET=os.getenv('GMAIL_OAUTH_CLIENT_SECRET'),
        GMAIL_OAUTH_REFRESH_TOKEN=os.getenv('GMAIL_OAUTH_REFRESH_TOKEN'),
        GMAIL_APP_PASSWORD=os.getenv('GMAIL_APP_PASSWORD'),
        APPOINTMENT_EMAIL_ENABLED=os.getenv('APPOINTMENT_EMAIL_ENABLED', '0') == '1',
        APPOINTMENT_EMAIL_REMINDER_MINUTES=int(os.getenv('APPOINTMENT_EMAIL_REMINDER_MINUTES', '0')),
        SMS_PROVIDER=os.getenv('SMS_PROVIDER', 'disabled'),
        SMS_POLICY_APPROVED=os.getenv('SMS_POLICY_APPROVED', '0') == '1',
        SMS_ELIGIBLE_ROLES=os.getenv('SMS_ELIGIBLE_ROLES', ''),
        SMS_ALLOWED_REGIONS=os.getenv('SMS_ALLOWED_REGIONS', ''),
        SMS_DAILY_MAX=int(os.getenv('SMS_DAILY_MAX', '0')),
        SMS_KEY=os.getenv('SMS_KEY'),
        SMS_LIMIT_KEY=os.getenv('SMS_LIMIT_KEY'),
        SMS_PROVIDER_VALIDITY_SECONDS=int(os.getenv('SMS_PROVIDER_VALIDITY_SECONDS', '600')),
        TWILIO_VERIFY_SERVICE_SID=os.getenv('TWILIO_VERIFY_SERVICE_SID'),
        TWILIO_ACCOUNT_SID=os.getenv('TWILIO_ACCOUNT_SID'),
        TWILIO_API_KEY=os.getenv('TWILIO_API_KEY'),
        TWILIO_API_SECRET=os.getenv('TWILIO_API_SECRET'),
        TWILIO_SECURITY_MESSAGING_SERVICE_SID=os.getenv('TWILIO_SECURITY_MESSAGING_SERVICE_SID'),
        TRUSTED_HOSTS=hosts or None,
        TRUSTED_PROXY_HOPS=int(proxy),DEBUG=False,PRODUCTION=production, DB_SCHEMA=schema)
