"""Browser-facing boundaries. No credentials or clinical text in diagnostics."""
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, abort, g, request, session, send_file


# Explicit release inventory, not a suffix allowlist. Add reviewed frontend assets
# here when needed; source maps, uploads and arbitrary files are never public.
PUBLIC_ASSETS = {'css/style.css': 'text/css', 'js/session-warning.js': 'text/javascript'}


class SecureFlask(Flask):
    def send_static_file(self, filename):
        if filename not in PUBLIC_ASSETS or not self.static_folder:
            abort(404)
        root=Path(self.static_folder).resolve()
        target=root.joinpath(*filename.split('/'))
        # Refuse both file and directory symlinks, including links back inside root.
        if any(part.is_symlink() for part in (target,*target.parents) if part!=root.parent):
            abort(404)
        resolved=target.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            abort(404)
        return send_file(resolved,mimetype=PUBLIC_ASSETS[filename],conditional=True,max_age=3600)

    def log_exception(self, exc_info):
        # Framework tracebacks can include exception messages, SQL or source lines.
        # Never log exception values, request bodies, query strings or opaque URLs.
        self.logger.error('Unhandled application error type=%s endpoint=%s',
            exc_info[0].__name__,request.endpoint or 'unmatched')


def configure_security(app):
    warning = app.config['AUTH_WARNING_SECONDS']
    if not 0 < warning < min(app.config['AUTH_IDLE_TIMEOUT'].total_seconds(),
                             app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()):
        raise RuntimeError('The session warning must be shorter than both session timeouts.')
    if not app.config['AUTH_REQUIRE_STAFF_MFA'] and (app.config['PRODUCTION'] or not app.testing):
        raise RuntimeError('Staff authenticator approval is mandatory outside synthetic tests.')
    if app.config['PRODUCTION']:
        if app.debug or app.config.get('TRAP_HTTP_EXCEPTIONS') or app.config.get('PROPAGATE_EXCEPTIONS'):
            raise RuntimeError('Production debugging and exception propagation must be disabled.')
        if not app.config.get('TRUSTED_HOSTS'):
            raise RuntimeError('Configure APP_TRUSTED_HOSTS before production use.')
        app.config.update(DEBUG=False,TESTING=False,PROPAGATE_EXCEPTIONS=False,
            TRAP_HTTP_EXCEPTIONS=False,SESSION_COOKIE_SECURE=True)
    app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
        SESSION_REFRESH_EACH_REQUEST=False,USE_X_SENDFILE=False)
    # Template files are trusted code, but an accidental {{ config }} dump should
    # not have a configuration/credential object available to render.
    app.jinja_env.globals.pop('config',None)

    @app.before_request
    def browser_boundary():
        # Never reuse authentication from a containing application context.
        g.pop('_login_user', None)
        g.pop('portal_session', None)
        g.pop('csrf_token', None)
        g.pop('csrf_valid', None)
        if app.config['PRODUCTION']:
            if app.debug or not request.is_secure:
                abort(400)  # the TLS edge handles HTTP redirects, before accepting bodies
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('Origin')
            if origin:
                parsed=urlsplit(origin)
                if parsed.scheme not in ('http','https') or origin.rstrip('/')!=request.host_url.rstrip('/'):
                    abort(403)
            if request.headers.get('Sec-Fetch-Site')=='cross-site':abort(403)

    @app.after_request
    def browser_headers(response):
        from flask_login import current_user
        public_asset=request.endpoint=='static' and response.status_code<400 and not current_user.is_authenticated
        if not public_asset:
            response.headers['Cache-Control']='no-store'
            response.headers['Pragma']='no-cache';response.headers['Expires']='0'
        response.vary.add('Cookie')
        # Chrome nulls the Origin on navigational form POSTs under no-referrer;
        # HTTPS CSRF also needs a same-origin referrer. Send only the origin,
        # never a patient path, query string or opaque-link token.
        response.headers['Referrer-Policy']='strict-origin'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']=("default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'none'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'")
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=(), payment=(), usb=()'
        if app.config['PRODUCTION'] and request.is_secure:
            response.headers['Strict-Transport-Security']='max-age=31536000'
        return response
