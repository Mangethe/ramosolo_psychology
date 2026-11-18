import os
import re
import secrets
from datetime import timedelta
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def settings():
    production = os.getenv('APP_ENV') == 'production'
    secret = os.getenv('FLASK_SECRET_KEY')
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
    if any(not re.fullmatch(r'\.?[A-Za-z0-9][A-Za-z0-9.:-]*|\[::1\]',host) or '*' in host for host in hosts):
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
    if production and os.getenv('FLASK_DEBUG','').lower() not in ('','0','false','no','off'):
        raise RuntimeError('FLASK_DEBUG must be disabled in production.')
    engine = {'pool_pre_ping': True}
    if url.startswith('postgresql+'):
        # Poolers may ignore startup options. The engine checkout hook applies
        # search_path on every physical connection, so don't depend on options.
        engine['connect_args'] = {'connect_timeout': 10}
        if production and parsed_url.query.get('sslmode') not in ('require','verify-ca','verify-full'):
            raise RuntimeError('Production database connections require an explicit secure sslmode.')
    return dict(SECRET_KEY=secret or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=url, SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=131072,
        AUTH_IDLE_TIMEOUT=timedelta(minutes=30),TRUSTED_HOSTS=hosts or None,
        TRUSTED_PROXY_HOPS=int(proxy),DEBUG=False,PRODUCTION=production, DB_SCHEMA=schema)
