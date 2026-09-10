"""Şartname Üretim ve Denetim Modülü Testleri."""

from pathlib import Path

import pytest

from generator.audit_verifier import SpecificationAuditVerifier
from generator.clause_engine import ParametricClauseEngine
from generator.spec_service import SpecificationPipelineService
from shared.catalog_service import ExcelCatalogService
from shared.models import SpecRequest


def test_clause_engine_generates_clauses_for_fas2820():
    """FAS2820 modeli için maddelerin üretildiğini test eder."""
    catalog = ExcelCatalogService()
    spec = catalog.get_spec("FAS2820")
    assert spec is not None

    engine = ParametricClauseEngine()
    req = SpecRequest(model="FAS2820", flexibility="tekil")
    clauses = engine.generate_clauses(spec, req)

    assert len(clauses) >= 20, "FAS2820 için en az 20 madde üretilmeli"
    full_text = " ".join(c.text for c in clauses)
    assert "FAS2820" in full_text
    assert "kontrol ünitesi" in full_text


def test_audit_verifier_passes_with_full_coverage():
    """SpecificationAuditVerifier'ın geçerli şartnamede %99+ kapsama verdiğini test eder."""
    catalog = ExcelCatalogService()
    spec = catalog.get_spec("FAS2820")
    assert spec is not None

    engine = ParametricClauseEngine()
    req = SpecRequest(model="FAS2820", flexibility="tekil")
    clauses = engine.generate_clauses(spec, req)

    is_valid, cov_pct, matched_cnt, total_cnt, missed = SpecificationAuditVerifier.audit(
        spec, clauses
    )

    assert is_valid, f"Denetim testi başarısız oldu! Kaçan kolonlar: {missed}"
    assert cov_pct >= 99.0
    assert matched_cnt > 0
    assert total_cnt > 0


@pytest.mark.asyncio
async def test_spec_service_end_to_end():
    """Uçtan uca şartname üretim, docx ve audit dosyası oluşum testi."""
    service = SpecificationPipelineService()
    req = SpecRequest(model="FAS2820", flexibility="tekil")

    result = await service.generate_specification(req)

    assert result.status if hasattr(result, "status") else True
    assert result.verification_status == "VERIFIED_100_PERCENT"
    assert result.audit_coverage_pct >= 99.0
    assert result.file_path is not None
    assert Path(result.file_path).exists()
    assert Path(result.file_path).suffix == ".docx"

    # Audit JSON dosyasının oluştuğunu kontrol et
    audit_path = Path(result.file_path).with_suffix(".audit.json")
    assert audit_path.exists(), f"Audit dosyası bulunamadı: {audit_path}"


def test_generic_mode_scrubs_brand_names():
    """Jenerik modda marka/model isimlerinin temizlendiğini test eder."""
    catalog = ExcelCatalogService()
    spec = catalog.get_spec("FAS2820")
    assert spec is not None

    engine = ParametricClauseEngine()
    req = SpecRequest(model="FAS2820", flexibility="jenerik")
    clauses = engine.generate_clauses(spec, req)

    full_text = " ".join(c.text for c in clauses)
    assert "NetApp" not in full_text, "Jenerik şartnamede 'NetApp' geçmemeli!"
