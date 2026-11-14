from extensions import db

ROLES = {'dr': 'Doctor', 'nurse': 'Nurse', 'admin': 'Administrator',
         'dr_assist': 'Doctor assistant', 'patient': 'Patient'}


class Membership(db.Model):
    __tablename__ = 'memberships'
    __table_args__ = (db.UniqueConstraint('user_id', 'institution_id'),
        db.CheckConstraint("role in ('dr','nurse','admin','dr_assist','patient')"))
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    institution_id = db.Column(db.Integer, db.ForeignKey('institutions.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    supervising_doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    institution = db.relationship('Institution')
    doctor = db.relationship('User', foreign_keys=[supervising_doctor_id])
