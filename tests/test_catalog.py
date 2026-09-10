"""Excel Katalog Servisi Testleri (Birim & Entegrasyon)."""

from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings


def test_catalog_loads_models():
    """Kataloğun en az 1 Excel dosyasından modelleri başarıyla yüklediğini test eder."""
    settings = get_settings()
    service = ExcelCatalogService(catalogs_dir=settings.CATALOGS_DIR)

    models = service.get_available_models()
    assert len(models) > 0, "Katalogda en az 1 model bulunmalı!"


def test_fas2820_model_spec():
    """FAS2820 modelinin teknik parametrelerinin doğru okunduğunu test eder."""
    service = ExcelCatalogService()
    spec = service.find_model("FAS2820")

    assert spec is not None, "FAS2820 modeli bulunamadı!"
    assert "FAS2820" in spec.model_name
    assert spec.ram_total_gb > 0
    assert len(spec.raw_attributes) > 0


def test_fuzzy_model_search():
    """Fuzzy model arama mekanizmasının çalıştığını test eder."""
    service = ExcelCatalogService()

    # Boşluklu veya küçük harfli arama
    spec = service.find_model("fas 2820")
    assert spec is not None, "'fas 2820' fuzzy araması başarılı olmalı"

    # AFF serisinden arama
    spec_aff = service.find_model("A30")
    assert spec_aff is not None, "'A30' modeli bulunabilmeli"


def test_unknown_model_returns_none():
    """Olmayan bir model arandığında None döndüğünü test eder."""
    service = ExcelCatalogService()
    spec = service.find_model("BilinmeyenOlmayanModel999")
    assert spec is None
