"""Regression coverage for database-backed public entry points; synthetic only."""
from unittest.mock import patch
import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError
from app import create_app
from config import settings
from extensions import db
from test_medical import env


@pytest.fixture
def uninitialized_app():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-route-tests',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'SQLALCHEMY_ENGINE_OPTIONS': {},
        'WTF_CSRF_ENABLED': False})
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


def test_supabase_url_alias_prevents_silent_sqlite_fallback(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('SUPABASE_DB_URL', 'postgresql://synthetic:fake@invalid.example.test/postgres?sslmode=require')
    monkeypatch.delenv('DB_SCHEMA', raising=False)
    config = settings()
    assert config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql+psycopg://')
    assert config['DB_SCHEMA'] == 'ramosolo'
    assert config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] == {
        'options': '-csearch_path=ramosolo,public', 'connect_timeout': 10}
    # Constructing the correctly configured engine must not open a live connection.
    app = create_app()
    with app.app_context():
        assert db.engine.dialect.name == 'postgresql'
        db.engine.dispose()


@pytest.mark.parametrize('database_url', ['', '   '])
def test_empty_primary_url_does_not_hide_supabase_alias(monkeypatch, database_url):
    monkeypatch.setenv('DATABASE_URL', database_url)
    monkeypatch.setenv('SUPABASE_DB_URL', 'postgres://test:fake@invalid.example.test/postgres')
    assert settings()['SQLALCHEMY_DATABASE_URI'].startswith('postgresql+psycopg://')


def test_explicit_database_and_legacy_schema_still_take_precedence(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')
    monkeypatch.setenv('SUPABASE_DB_URL', 'postgresql://fake@invalid.example.test/postgres')
    monkeypatch.setenv('DB_SCHEMA', 'lesonto')
    config = settings()
    assert config['SQLALCHEMY_DATABASE_URI'] == 'sqlite://'
    assert config['DB_SCHEMA'] == 'lesonto'


def test_local_default_remains_explicitly_local(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_DB_URL', raising=False)
    assert settings()['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///lesonto.db'


def test_appointment_links_and_login_form_open_without_database(uninitialized_app):
    client = uninitialized_app.test_client()
    with patch('Med.MedWebsite.controllers.public.public_institution', side_effect=AssertionError('Unexpected database lookup')):
        for path in ('/', '/book', '/auth/login'):
            response = client.get(path)
            assert response.status_code == 200, path
    assert b'action="' not in client.get('/book').data or b'csrf_token' in client.get('/book').data


@pytest.mark.parametrize('path', ['/book', '/auth/login'])
def test_missing_database_tables_return_safe_retryable_response(uninitialized_app, path, caplog):
    data = {'email': 'synthetic@example.test', 'password': 'synthetic-test-password'}
    response = uninitialized_app.test_client().post(path, data=data)
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '60'
    assert response.headers['Cache-Control'] == 'no-store'
    assert b'Temporarily unavailable' in response.data
    assert b'no such table' not in response.data
    assert b'Traceback' not in response.data
    assert 'Database unavailable type=OperationalError' in caplog.text
    assert 'synthetic@example.test' not in caplog.text
    assert 'synthetic-test-password' not in caplog.text


@pytest.mark.parametrize('exception_type', [OperationalError, ProgrammingError])
def test_unavailable_database_never_exposes_exception_or_credentials(uninitialized_app, exception_type, caplog):
    canary = 'SYNTHETIC_PRIVATE_DATABASE_CANARY'
    error = exception_type('SELECT ' + canary, {'password': canary}, Exception(canary))
    with patch('auth.db.session.scalar', side_effect=error):
        response = uninitialized_app.test_client().post('/auth/login', data={
            'email': 'synthetic@example.test', 'password': 'synthetic-password'})
    assert response.status_code == 503
    assert canary.encode() not in response.data
    assert canary not in caplog.text


def test_database_failure_while_loading_existing_login_has_no_recursive_500(env, caplog):
    from flask import g
    from test_medical import as_user
    client = as_user(env, 'dr')
    g.pop('_login_user', None)
    error = OperationalError('synthetic SQL', {}, Exception('SYNTHETIC_PRIVATE_DATABASE_CANARY'))
    with patch('app.db.session.get', side_effect=error):
        response = client.get('/book')
    assert response.status_code == 503
    assert b'SYNTHETIC_PRIVATE_DATABASE_CANARY' not in response.data
    assert 'SYNTHETIC_PRIVATE_DATABASE_CANARY' not in caplog.text


def test_database_check_reports_missing_objects_without_creating_tables(uninitialized_app):
    runner = uninitialized_app.test_cli_runner()
    result = runner.invoke(args=['check-connections', '--only', 'database'])
    assert result.exit_code != 0
    assert 'institutions (table)' in result.output
    assert 'users (table)' in result.output
    from sqlalchemy import inspect
    assert inspect(db.engine).get_table_names() == []


def test_database_check_identifies_populated_local_database(env):
    result = env[0].test_cli_runner().invoke(args=['check-connections', '--only', 'database'])
    assert result.exit_code == 0
    assert 'Local SQLite' in result.output
    assert 'Supabase is not selected' in result.output


def test_real_login_still_reaches_dashboard_with_correct_csrf(env):
    import re
    from flask import g
    env[0].config['WTF_CSRF_ENABLED'] = True
    client = env[0].test_client()
    token = re.search(rb'name="csrf_token" value="([^"]+)"', client.get('/auth/login').data).group(1).decode()
    response = client.post('/auth/login', data={'email': 'dr@example.test',
        'password': 'Testing-password-123', 'csrf_token': token})
    assert response.status_code == 302
    g.pop('_login_user', None)
    assert client.get(response.headers['Location']).status_code == 200
