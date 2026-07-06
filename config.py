"""
SupplyLink — config.py
Basic Flask configuration, loaded from environment variables via python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/supplylink"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie settings
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7  # 7 days