from flask import Blueprint
bp = Blueprint('med', __name__, template_folder='../templates')
from . import public, portal, continuity, permissions, coordination, calendar
