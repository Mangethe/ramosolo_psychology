import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import render_template, g, request, redirect, url_for, session
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from extensions import db, login_manager, csrf
from config import settings
from security import SecureFlask, configure_security


@event.listens_for(Engine, 'connect')
def sqlite_foreign_keys(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


def postgres_schema_on_checkout(dbapi_connection, connection_record, connection_proxy):
    """Reset pooled PostgreSQL connections to this app's validated schema."""
    schema = connection_record.info.get('ramosolo_schema')
    if not schema:
        return
    cursor = dbapi_connection.cursor()
    try:
        # Identifier was validated as lowercase [a-z][a-z0-9_]* in config.
        cursor.execute(f'SET SESSION search_path TO "{schema}", public')
    finally:
        cursor.close()


def create_app(test_config=None):
    load_dotenv()
    app = SecureFlask(__name__)
    app.config.update(settings())
    if test_config:
        app.config.update(test_config)
    # SQL exceptions and debug logging must not disclose bound clinical values.
    engine_options = dict(app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {}))
    engine_options.update(hide_parameters=True, echo=False)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options
    app.config['SQLALCHEMY_ECHO'] = False
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith('postgresql+'):
        schema = app.config.get('DB_SCHEMA', '')
        import re
        if not re.fullmatch(r'[a-z][a-z0-9_]*', schema):
            raise RuntimeError('DB_SCHEMA must be a lowercase SQL identifier.')
        with app.app_context():
            engine = db.engine
            @event.listens_for(engine, 'connect')
            def tag_postgres_connection(dbapi_connection, connection_record):
                connection_record.info['ramosolo_schema'] = schema
            event.listen(engine, 'checkout', postgres_schema_on_checkout)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access your portal.'
    configure_security(app)
    # Forwarded headers are trusted only when the operator explicitly configures
    # the exact proxy count AND prevents direct access to the backend listener.
    if app.config['TRUSTED_PROXY_HOPS']:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app=ProxyFix(app.wsgi_app,x_proto=app.config['TRUSTED_PROXY_HOPS'],
            x_for=0,x_host=0,x_port=0,x_prefix=0)

    @login_manager.unauthorized_handler
    def unauthorized():
        # Do not copy arbitrary patient-related query strings into login URLs.
        return redirect(url_for('auth.login'))
    from models import User, ROLES
    from access import membership_for_request
    from auth import bp as auth_bp
    from Med.MedWebsite.controllers import bp as med_bp
    from administration import bp as admin_bp
    from cli import register_commands
    app.register_blueprint(auth_bp)
    app.register_blueprint(med_bp)
    app.register_blueprint(admin_bp)
    app.before_request(membership_for_request)
    register_commands(app)

    @login_manager.user_loader
    def load_user(user_id):
        if getattr(g, 'database_unavailable', False):
            return None
        from security import valid_login_clock
        if not valid_login_clock(app):
            # Flask-Login can otherwise restore an old remember cookie after
            # before_request has rejected an expired or missing login session.
            session['_remember']='clear'
            return None
        try:
            identity, version = user_id.split(':')
            user = db.session.get(User, int(identity))
            return user if user and user.enabled and user.session_version == int(version) else None
        except (ValueError, TypeError):
            return None

    @app.template_filter('localtime')
    def localtime(value, fmt='%d %b %Y · %H:%M'):
        if not value:
            return '—'
        return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Africa/Johannesburg')).strftime(fmt)

    @app.context_processor
    def shared_context():
        from access import can_patient, capability
        from policy_info import OFFICIAL_LINKS
        return dict(roles=ROLES, membership=getattr(g, 'membership', None),
                    memberships=getattr(g, 'memberships', []), current_year=datetime.now().year,
                    can_patient=can_patient, capability=capability, official=OFFICIAL_LINKS)

    @app.after_request
    def response_headers(response):
        if response.status_code >= 400:
            try:
                db.session.rollback()
            except SQLAlchemyError:
                # A broken connection must not turn an error response into a
                # second database exception.
                db.session.remove()
        return response

    @app.errorhandler(SQLAlchemyError)
    def database_unavailable(error):
        g.database_unavailable = True
        db.session.remove()
        # No SQL, parameters, connection strings or exception messages in logs.
        app.logger.error('Database unavailable type=%s endpoint=%s',
                         type(error).__name__, request.endpoint or 'unmatched')
        # Do not render the shared shell: its authentication context may try to
        # load the same unavailable database while displaying this error.
        body = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Temporarily unavailable · Ramosolo</title></head><body>'
                '<main><h1>Temporarily unavailable</h1>'
                '<p>We cannot reach the practice records right now. '
                'Please try again later or contact the practice directly.</p>'
                '<p>If you were submitting a request, do not assume it was saved. '
                'Confirm with the practice before submitting again.</p>'
                '<p><a href="/">Return to the practice website</a></p></main></body></html>')
        return body, 503, {'Content-Type': 'text/html; charset=utf-8', 'Retry-After': '60'}

    def portal_error(error):
        from werkzeug.exceptions import SecurityError
        if isinstance(error,SecurityError):
            # Invalid hosts have no URL adapter. Do not call url_for or reflect
            # the supplied hostname while handling that routing rejection.
            return 'Request not available.',400,{'Content-Type':'text/plain; charset=utf-8'}
        return render_template('errors/error.html',error=error),error.code

    for code in (400, 401, 403, 404, 405, 409, 410, 413, 415, 422, 429, 500):
        app.register_error_handler(code,portal_error)
    return app
