from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    REDIS_URL: str = "redis://localhost:6379/0"
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True
    MONNIFY_API_KEY: str
    MONNIFY_SECRET_KEY: str
    MONNIFY_CONTRACT_CODE: str
    MONNIFY_BASE_URL: str
    WALLET_ACCOUNT_NO: str
    PAYSTACK_SECRET_KEY: str
    PAYSTACK_LIVE_KEY: str
    DOMAIN: str
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    
    
    model_config= SettingsConfigDict(
        env_file= BASE_DIR / ".env",
        extra="ignore"
    )
    
Config = Settings()