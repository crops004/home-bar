import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Base application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME") or os.getenv("USERNAME")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or os.getenv("PASSWORD")
    TEMPLATES_AUTO_RELOAD = True
    FLASK_DEV = os.getenv("FLASK_DEV", "false").lower() == "true"
    AUTO_OPEN_BROWSER = os.getenv("FLASK_AUTO_OPEN_BROWSER", "false").lower() == "true"
    SHOW_VIEWPORT_DEBUG = os.getenv("SHOW_VIEWPORT_DEBUG", "false").lower() == "true"
