import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import Flask, render_template, g, request
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from extensions import db, login_manager, csrf
from config import settings


@event.listens_for(Engine, 'connect')
def sqlite_foreign_keys(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.update(settings())
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access your portal.'
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
        return dict(roles=ROLES, membership=getattr(g, 'membership', None),
                    memberships=getattr(g, 'memberships', []), current_year=datetime.now().year)

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        if app.config['PRODUCTION']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.path.startswith(('/med', '/auth', '/admin', '/institutions')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    for code in (400, 403, 404, 429, 500):
        app.register_error_handler(code, lambda error: (render_template('errors/error.html', error=error), error.code))
    return app
