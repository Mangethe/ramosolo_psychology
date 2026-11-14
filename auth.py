from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user, login_user, logout_user, login_required
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db
from models import User

bp = Blueprint('auth', __name__, url_prefix='/auth')
DUMMY_HASH = generate_password_hash('not-a-real-account-password')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('med.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()[:254]
        password = request.form.get('password', '')[:512]
        user = db.session.scalar(select(User).where(User.email == email))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        valid = check_password_hash(user.password_hash if user else DUMMY_HASH, password)
        blocked = user and user.locked_until and user.locked_until > now
        if user and user.enabled and valid and not blocked:
            user.failed_logins = 0
            user.locked_until = None
            db.session.commit()
            session.clear()
            login_user(user, remember=False)
            session.permanent = True
            return redirect(url_for('med.dashboard'))
        if user and not blocked:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_logins = 0
            db.session.commit()
        flash('Unable to sign in. Check your details or try again later.', 'error')
    return render_template('auth/login.html')


@bp.post('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('med.home'))
