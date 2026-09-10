"""Pipeline Modülü Testleri."""

import tempfile
from pathlib import Path

from pipeline.pipeline_service import PipelineService


def test_pipeline_status():
    """Pipeline durum raporunun doğruluğunu test eder."""
    service = PipelineService()
    status = service.get_status()

    assert "pending_count" in status
    assert "processed_count" in status
    assert "catalog_excel_count" in status
    assert isinstance(status["catalog_excel_count"], int)
    assert status["catalog_excel_count"] >= 6


def test_normalize_value():
    """Hücre değeri normalizasyonunu test eder."""
    assert PipelineService.normalize_value("  test value \n ") == "test value"
    assert PipelineService.normalize_value(None) == ""
    assert PipelineService.normalize_value(123) == "123"


def test_process_empty_pending():
    """Bekleyen dosya olmadığında pipeline sonucunu test eder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        service = PipelineService(
            incoming_dir=tmp_path / "incoming",
            processed_dir=tmp_path / "processed",
            catalogs_dir=tmp_path / "catalogs",
        )
        res = service.process_all_pending()
        assert res.total_found == 0
        assert res.processed_count == 0
        assert res.failed_count == 0
