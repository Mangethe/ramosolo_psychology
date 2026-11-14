import os
import re
import secrets
from datetime import timedelta


def settings():
    production = os.getenv('APP_ENV') == 'production'
    secret = os.getenv('FLASK_SECRET_KEY')
    url = os.getenv('DATABASE_URL', 'sqlite:///lesonto.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    schema = os.getenv('DB_SCHEMA', 'lesonto')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', schema):
        raise RuntimeError('DB_SCHEMA must be a lowercase SQL identifier.')
    if production and (not secret or len(secret) < 32 or secret.startswith('replace-')):
        raise RuntimeError('Set a random FLASK_SECRET_KEY of at least 32 characters.')
    if production and not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Production requires PostgreSQL. SQLite is for local demos.')
    engine = {'pool_pre_ping': True}
    if url.startswith('postgresql+'):
        engine['connect_args'] = {'options': f'-csearch_path={schema},public'}
        if production and 'sslmode=' not in url:
            raise RuntimeError('Configure SSL in DATABASE_URL before production use.')
    return dict(SECRET_KEY=secret or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=url, SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=engine, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2), MAX_CONTENT_LENGTH=131072,
        PRODUCTION=production, DB_SCHEMA=schema)




