from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    session_version = db.Column(db.Integer, nullable=False, default=1)
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)

    @property
    def is_active(self):
        return self.enabled

    def get_id(self):
        return f'{self.id}:{self.session_version}'

    def set_password(self, password):
        self.session_version = (self.session_version or 0) + 1
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Institution(db.Model):
    __tablename__ = 'institutions'
    __table_args__ = (db.CheckConstraint("kind in ('medical', 'education')"),)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(350), default='')
