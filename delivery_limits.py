"""Atomic reservations shared by the outbound providers."""
from sqlalchemy import case, or_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from extensions import db
from models import DeliveryLimit


def reserve(now, *buckets):
    """Reserve all (key, lifetime, maximum) buckets together or reserve none."""
    statement = postgres_insert if db.session.get_bind().dialect.name == 'postgresql' else sqlite_insert
    with db.session.begin_nested() as savepoint:
        for key, lifetime, maximum in sorted(buckets):
            if maximum <= 0:
                savepoint.rollback()
                return False
            expired = DeliveryLimit.expires_at <= now
            insert = statement(DeliveryLimit).values(key=key, expires_at=now + lifetime, count=1)
            claimed = db.session.execute(insert.on_conflict_do_update(index_elements=[DeliveryLimit.key],
                set_={'count': case((expired, 1), else_=DeliveryLimit.count + 1),
                      'expires_at': case((expired, now + lifetime), else_=DeliveryLimit.expires_at)},
                where=or_(expired, DeliveryLimit.count < maximum))).rowcount
            if claimed != 1:
                savepoint.rollback()
                return False
    return True
