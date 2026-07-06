"""
SupplyLink — extensions.py
Shared extension instances, initialized here and bound to the app in app.py
(avoids circular imports between app.py and models.py).
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access SupplyLink."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    # Imported here, not at module top, to avoid a circular import —
    # models.py imports `db` from this same file.
    from models import User
    return User.query.get(int(user_id))