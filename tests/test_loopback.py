"""Döngüsel Doğrulama Testi: Üretilen Şartname -> Karşılaştır -> 1:1 Eşleşme Güvencesi."""

from pathlib import Path

import pytest

from generator.spec_service import get_specification_service
from matcher.matcher_service import get_matcher_service
from shared.models import MatchRequest, SpecRequest


@pytest.mark.asyncio
async def test_loopback_fas2820_matches_itself():
    """FAS2820 için üretilen şartnamenin karşılaştırmada 1. sırada %100 FAS2820 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="FAS2820", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "FAS2820" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"


@pytest.mark.asyncio
async def test_loopback_aff_a30_matches_itself():
    """AFF A30 için üretilen şartnamenin karşılaştırmada 1. sırada %100 AFF A30 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="AFF A30", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "AFF A30" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"


@pytest.mark.asyncio
async def test_loopback_ef50_matches_itself():
    """EF50 için üretilen şartnamenin karşılaştırmada 1. sırada %100 EF50 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="EF50", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "EF50" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"


@pytest.mark.asyncio
async def test_loopback_asa_a30_matches_itself():
    """ASA A30 için üretilen şartnamenin karşılaştırmada 1. sırada %100 ASA A30 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="ASA A30", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "ASA A30" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"


@pytest.mark.asyncio
async def test_loopback_aff_c30_matches_itself():
    """AFF C30 için üretilen şartnamenin karşılaştırmada 1. sırada %100 AFF C30 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="AFF C30", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "AFF C30" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"


@pytest.mark.asyncio
async def test_loopback_aff_a50_matches_itself():
    """AFF A50 için üretilen şartnamenin karşılaştırmada 1. sırada %100 AFF A50 çıkması testi."""
    spec_svc = get_specification_service()
    matcher_svc = get_matcher_service()

    gen_res = await spec_svc.generate_specification(SpecRequest(model="AFF A50", flexibility="tekil"))
    assert gen_res.audit_coverage_pct == 100.0
    assert Path(gen_res.file_path).exists()

    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=gen_res.file_path,
        top_n=5,
        include_absurd_analysis=True,
    ))

    assert len(match_res) > 0
    top_match = match_res[0]
    assert "AFF A50" in top_match.model_name
    assert top_match.overall_score == 100.0
    assert top_match.tier == "TAM_UYUM"

