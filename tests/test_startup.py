"""Factory startup and engine isolation; no database connections required."""
from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.pool import Pool

from app import create_app, postgres_schema_on_checkout
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
        assert not event.contains(Pool, 'checkout', postgres_schema_on_checkout)
        for engine, schema in zip(engines, ('ramosolo', 'other_synthetic')):
            assert list(engine.pool.dispatch.checkout) == [postgres_schema_on_checkout]
            # Run the registered connect callbacks against a synthetic record.
            class Record:
                info = {}
            record = Record()
            list(engine.pool.dispatch.connect)[-1](object(), record)
            assert record.info['ramosolo_schema'] == schema
    finally:
        for engine in engines:
            engine.dispose()
    assert not has_app_context()
