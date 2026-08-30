from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 通过环境变量集中管理虚拟机、邮箱、AI 和安全配置，避免凭据进入代码。
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "油品发货核销平台"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./categoryb.db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = Field(default="development-only-change-me-please", min_length=24)
    access_token_minutes: int = 480
    cookie_secure: bool = False
    seed_demo_data: bool = False
    initial_admin_email: str = "admin@example.com"
    initial_admin_password: str = ""
    storage_path: Path = Path("storage")
    max_attachment_bytes: int = 5 * 1024 * 1024

    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    ai_api_url: str = ""
    ai_api_key: str = ""
    ai_model: str = ""


# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 缓存不可变配置，避免每次请求重复解析环境文件。
@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

