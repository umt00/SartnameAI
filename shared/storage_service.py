"""Depolama Servisleri (SOLID: LSP & DIP).

Yerel dosya depolama ve Azure Blob Storage (SAS URL) uygulamaları.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared.config import get_settings


class LocalStorageService:
    """Yerel disk üzerinde dosya saklama servisi."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or get_settings().OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def save_document(self, file_path: str, file_name: str) -> tuple[str, str | None]:
        """Yerel dosyayı doğrular ve yerel yolunu döndürür."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Kaydedilecek dosya bulunamadı: {file_path}")
        return (str(p.resolve()), str(p.resolve()))


class AzureBlobStorageService:
    """Azure Blob Storage'a yükleme ve SAS URL üretme servisi."""

    def __init__(
        self,
        connection_string: str | None = None,
        container_name: str | None = None,
        expiry_hours: int | None = None,
    ):
        settings = get_settings()
        self.connection_string = connection_string or settings.AZURE_STORAGE_CONNECTION_STRING
        self.container_name = container_name or settings.AZURE_STORAGE_CONTAINER_NAME
        self.expiry_hours = expiry_hours or settings.SAS_TOKEN_EXPIRY_HOURS

        if not self.connection_string:
            raise ValueError("Azure Storage Connection String yapılandırılmamış!")

    async def save_document(self, file_path: str, file_name: str) -> tuple[str, str | None]:
        """Dosyayı Azure Blob'a yükler ve geçerli bir SAS URL döndürür."""
        from azure.storage.blob import (
            BlobSasPermissions,
            BlobServiceClient,
            generate_blob_sas,
        )

        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Yüklenecek dosya bulunamadı: {file_path}")

        blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        container_client = blob_service_client.get_container_client(self.container_name)

        import contextlib

        with contextlib.suppress(Exception):
            container_client.create_container()

        blob_client = container_client.get_blob_client(file_name)
        blob_client.upload_blob(p.read_bytes(), overwrite=True)

        account_name = blob_service_client.account_name
        account_key = blob_service_client.credential.account_key

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.container_name,
            blob_name=file_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=self.expiry_hours),
        )

        sas_url = f"{blob_client.url}?{sas_token}"
        return (str(p.resolve()), sas_url)


def get_storage_service():
    """Aktif yapılandırmaya göre uygun depolama servisini döner."""
    settings = get_settings()
    if settings.STORAGE_BACKEND == "azure_blob" and settings.AZURE_STORAGE_CONNECTION_STRING:
        try:
            return AzureBlobStorageService()
        except Exception as e:  # noqa: BLE001
            print(f"[Uyarı] Azure Blob başlatılamadı, yerel depolamaya dönülüyor: {e}")
            return LocalStorageService()
    return LocalStorageService()
