"""Factory startup and engine isolation; no database connections required."""
from flask import current_app, has_app_context
from unittest.mock import Mock

from app import create_app
from extensions import db


def test_postgres_factory_without_context_registers_each_engine_once():
    assert not has_app_context()
    config = {'TESTING': True, 'SECRET_KEY': 'synthetic-startup',
              'SQLALCHEMY_DATABASE_URI': 'postgresql+psycopg://synthetic@invalid.example.test/postgres',
              'SQLALCHEMY_ENGINE_OPTIONS': {}, 'DB_SCHEMA': 'ramosolo'}
    engines = []
    try:
        first = create_app(config)
        assert not has_app_context()
        with first.app_context():
            engines.append(db.engine)
            second = create_app(dict(config, DB_SCHEMA='other_synthetic'))
            assert current_app._get_current_object() is first
            assert db.engine is engines[0]
        assert not has_app_context()
        with second.app_context():
            engines.append(db.engine)
        assert engines[0] is not engines[1]
        for engine, schema in zip(engines, ('ramosolo', 'other_synthetic')):
            connection = Mock()
            callbacks = list(engine.dispatch.begin)
            assert len(callbacks) == 1
            callbacks[0](connection)
            connection.exec_driver_sql.assert_called_once_with(f'SET LOCAL search_path TO "{schema}", public')
    finally:
        for engine in engines:
            engine.dispose()
    assert not has_app_context()
