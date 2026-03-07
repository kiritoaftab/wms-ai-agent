"""
Application configuration loaded from environment variables.
"""

from typing import List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"

    # WMS MySQL (read-only)
    wms_db_host: str = "localhost"
    wms_db_port: int = 3306
    wms_db_name: str = "wms_db"
    wms_db_user: str = "wms_ai_readonly"
    wms_db_password: str = ""

    # SQLite for threads
    sqlite_db_path: str = "./threads.db"

    # App settings
    app_port: int = 8000
    app_env: str = "development"
    max_query_rows: int = 500
    query_timeout_seconds: int = 10
    cors_origins: str = "http://localhost:5173,http://localhost:3001"

    # JWT (shared with WMS ERP)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
