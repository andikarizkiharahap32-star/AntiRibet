from __future__ import annotations

import base64
import secrets
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _gen_fernet_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AAC - Auto Account Creator"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # CORS (CLI-first default)
    CORS_ALLOW_ORIGINS: str = "*"

    # CLI system user
    CLI_SYSTEM_USERNAME: str = "cli-system"
    CLI_SYSTEM_PASSWORD: str = "cli-system-change-me"
    CLI_SYSTEM_ROLE: str = "admin"

    # Database
    DATABASE_URL: str = "postgresql://aac_user:aac_password@localhost:5432/aac_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_SESSION_URL: str = "redis://localhost:6379/1"
    REDIS_CELERY_BROKER: str = "redis://localhost:6379/2"
    REDIS_CELERY_BACKEND: str = "redis://localhost:6379/3"

    # Celery
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 1800
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = 100

    # JWT Authentication
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_HOURS: int = 8
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))

    # LDAP/SSO
    LDAP_ENABLED: bool = False
    LDAP_SERVER: str = "ldap://ldap-server:389"
    LDAP_BIND_DN: str = "cn=admin,dc=company,dc=com"
    LDAP_BIND_PASSWORD: str = "ldap-password"
    LDAP_USER_SEARCH_BASE: str = "ou=users,dc=company,dc=com"
    LDAP_USER_SEARCH_FILTER: str = "(uid={username})"
    LDAP_GROUP_SEARCH_BASE: str = "ou=groups,dc=company,dc=com"
    LDAP_ALLOWED_GROUP: str = "cn=aac-users,ou=groups,dc=company,dc=com"
    LDAP_STARTTLS: bool = True
    LDAP_TIMEOUT: int = 3

    # Session
    SESSION_TIMEOUT_HOURS: int = 8
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"

    # Encryption (Fernet - AES-256)
    FERNET_KEY: str = Field(default_factory=_gen_fernet_key)
    FERNET_KEY_NEW: str = ""

    # Proxy Providers
    PROXY_PROVIDER: str = "brightdata"
    BRIGHTDATA_USERNAME: str = ""
    BRIGHTDATA_PASSWORD: str = ""
    BRIGHTDATA_ZONE: str = "residential"
    SMARTPROXY_API_KEY: str = ""
    SMARTPROXY_USERNAME: str = ""
    SMARTPROXY_PASSWORD: str = ""

    # Captcha Solvers
    CAPTCHA_PROVIDER: str = "2captcha"
    TWOCAPTCHA_API_KEY: str = ""
    ANTICAPTCHA_API_KEY: str = ""
    CAPTCHA_TIMEOUT_HCAPTCHA: int = 120
    CAPTCHA_TIMEOUT_RECAPTCHA: int = 180

    # Temp Mail Providers
    TEMP_MAIL_PROVIDER: str = "mailtm"
    MAILTM_API_URL: str = "https://api.mail.tm"
    MAILTM_DOMAINS: str = "mail.tm"
    ONESECMAIL_API_URL: str = "https://www.1secmail.com/api/v1"
    MAILSAC_API_KEY: str = ""
    MAILSAC_API_URL: str = "https://mailsac.com/api"

    # IMAP Custom Domain
    IMAP_ENABLED: bool = False
    IMAP_HOST: str = "mail.example.com"
    IMAP_PORT: int = 993
    IMAP_USERNAME: str = ""
    IMAP_PASSWORD: str = ""
    IMAP_DOMAIN: str = "example.com"

    # SMS Providers
    SMS_PROVIDER: str = "5sim"
    SIMS_API_KEY: str = ""
    SIMS_API_URL: str = "https://5sim.net/v1"
    SMSACTIVATE_API_KEY: str = ""
    SMSACTIVATE_API_URL: str = "https://sms-activate.io/stubs/handler_api.php"
    SMS_MAX_PRICE: float = 0.5
    SMS_TIMEOUT: int = 60

    # Discord
    DISCORD_REG_URL: str = "https://discord.com/register"
    DISCORD_VERIFY_URL: str = "https://discord.com/verify"
    DISCORD_HCAPTCHA_SITEKEY: str = ""

    # Gmail
    GMAIL_REG_URL: str = "https://accounts.google.com/signup"
    GMAIL_RECAPTCHA_SITEKEY: str = ""

    # Browser
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000
    BROWSER_VIEWPORT_WIDTH: int = 1366
    BROWSER_VIEWPORT_HEIGHT: int = 768
    BROWSER_USER_AGENTS_COUNT: int = 50

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 20

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_RETENTION_DAYS: int = 30

    # Cost Limits
    MONTHLY_BUDGET_USD: float = 50.0
    BUDGET_ALERT_THRESHOLD_80: float = 0.8
    BUDGET_ALERT_THRESHOLD_95: float = 0.95

    # Worker Scaling
    MIN_WORKERS: int = 2
    MAX_WORKERS: int = 50
    QUEUE_HIGH_THRESHOLD: int = 50
    QUEUE_LOW_THRESHOLD: int = 10

    # Export
    EXPORT_MAX_RECORDS: int = 10000
    EXPORT_FILE_TTL_HOURS: int = 24

    @property
    def fernet_key_bytes(self) -> bytes:
        try:
            decoded = base64.urlsafe_b64decode(self.FERNET_KEY)
        except Exception as exc:
            raise ValueError("FERNET_KEY must be valid urlsafe base64") from exc
        if len(decoded) != 32:
            raise ValueError("FERNET_KEY must decode to exactly 32 bytes")
        return self.FERNET_KEY.encode()

    @property
    def fernet_key_new_bytes(self) -> Optional[bytes]:
        if not self.FERNET_KEY_NEW:
            return None
        try:
            decoded = base64.urlsafe_b64decode(self.FERNET_KEY_NEW)
        except Exception as exc:
            raise ValueError("FERNET_KEY_NEW must be valid urlsafe base64") from exc
        if len(decoded) != 32:
            raise ValueError("FERNET_KEY_NEW must decode to exactly 32 bytes")
        return self.FERNET_KEY_NEW.encode()

    @property
    def cors_allow_origins(self) -> list[str]:
        raw = (self.CORS_ALLOW_ORIGINS or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]


settings = Settings()
