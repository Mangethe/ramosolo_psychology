"""Production entry point: waitress-serve --call wsgi:create_production_app.

Run behind the reviewed TLS proxy on a private/loopback listener. No debugger.
"""
import os
from app import create_app


def create_production_app():
    if os.getenv('APP_ENV')!='production':
        raise RuntimeError('The production entry point requires APP_ENV=production.')
    return create_app()
