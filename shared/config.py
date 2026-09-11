"""Merkezi yapılandırma modülü.

Pydantic Settings kullanılarak ortam değişkenleri (.env) üzerinden yönetilir.
Tüm modüller bu tekil yapılandırma nesnesine bağımlıdır.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama ayarları sınıfı."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Temel Dizin Yolları
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    CATALOGS_DIR: Path = DATA_DIR / "catalogs"
    TEMPLATES_DIR: Path = DATA_DIR / "templates"
    OUTPUT_DIR: Path = PROJECT_ROOT / "output"

    # Pipeline Dizinleri
    PIPELINE_INCOMING_DIR: Path = PROJECT_ROOT / "pipeline" / "1_incoming_pdfs"
    PIPELINE_PROCESSED_DIR: Path = PROJECT_ROOT / "pipeline" / "2_processed_pdfs"

    DEFAULT_TEMPLATE_FILE: str = "NetAppTaslak-Ornek-Sartname-v02_FAS2820_Calix.docx"

    # Depolama Yapılandırması
    STORAGE_BACKEND: Literal["local", "azure_blob"] = "local"
    AZURE_STORAGE_CONNECTION_STRING: str | None = None
    AZURE_STORAGE_CONTAINER_NAME: str = "sartnameler"
    SAS_TOKEN_EXPIRY_HOURS: int = 24

    # Web Arama Yapılandırması
    SEARCH_PROVIDER: Literal["ddg", "azure_search", "offline"] = "offline"
    AZURE_SEARCH_ENDPOINT: str | None = None
    AZURE_SEARCH_KEY: str | None = None
    AZURE_SEARCH_INDEX_NAME: str = "sartname-index"

    # Yapay Zeka / Azure OpenAI Yapılandırması
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4o"
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # FastMCP Sunucu Ayarları
    SERVER_HOST: str = "0.0.0.0"
    PIPELINE_PORT: int = 8001
    GENERATOR_PORT: int = 8002
    MATCHER_PORT: int = 8003
    DEBUG: bool = False

    @property
    def template_path(self) -> Path:
        """Kullanılacak varsayılan şablon dosyasının tam yolu."""
        return self.TEMPLATES_DIR / self.DEFAULT_TEMPLATE_FILE


@lru_cache
def get_settings() -> Settings:
    """Tekil (Singleton) yapılandırma nesnesi döner."""
    settings = Settings()
    # Gerekli çıktı dizinlerinin varlığını garanti et
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    settings.PIPELINE_INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    settings.PIPELINE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    settings.CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    return settings
