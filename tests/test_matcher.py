"""Şartname Karşılaştırma ve Öneri Modülü Testleri."""

from matcher.advisor_engine import AdvisorEngine
from matcher.matcher_service import MatcherService
from matcher.scoring_engine import ScoringEngine
from shared.models import MatchRequest


def test_scoring_fas2820_match():
    """FAS2820 özelliklerini içeren bir şartnamede FAS2820'nin en yüksek puanı aldığını test eder."""
    tender_text = (
        "Teklif edilen veri depolama sistemi Hibrit tipinde ve Unified mimaride olmalıdır. "
        "Sistem 2U şasi yapısında ve en az 2 adet kontrol ünitesine (HA Pair) sahip olacaktır. "
        "Sistemde toplamda en az 128 GB sistem belleği (RAM) bulunacaktır. "
        "En az 4 adet 10G Ethernet ve 4 adet 32G FC port bulunmalıdır. "
        "En az 144 disk genişleme kapasitesini desteklemelidir."
    )

    service = MatcherService()
    req = MatchRequest(specification_text=tender_text, top_n=5)
    results = service.match_specification(req)

    assert len(results) > 0
    top_model = results[0]
    assert "FAS2820" in top_model.model_name
    assert top_model.overall_score >= 90.0
    assert top_model.tier == "TAM_UYUM"
    assert "uygun" in top_model.recommendation.lower()


def test_scoring_all_flash_preference():
    """All-Flash şartnamesinde AFF serisi modellerin öne çıktığını test eder."""
    tender_text = (
        "Teklif edilen sistem All-Flash NVMe SSD mimarisinde olmalı, "
        "en az 2 kontrol ünitesi ve en az 64 GB RAM barındırmalıdır."
    )

    service = MatcherService()
    req = MatchRequest(specification_text=tender_text, top_n=3)
    results = service.match_specification(req)

    assert len(results) > 0
    top_model = results[0]
    assert any(prefix in top_model.model_name for prefix in ["AFF", "ASA", "AFX"])


def test_absurdity_detection():
    """Çelişkili ve mantıksız şartname maddelerinin tespit edildiğini test eder."""
    absurd_tender = (
        "Teklif edilen sistem tek kontrol ünitesine sahip olmalı ancak aynı zamanda "
        "kesintisiz failover ve aktif-aktif HA Pair mimarisini desteklemelidir. "
        "Sistemde en az 2048 GB RAM bulunmalıdır. "
        "Sistem yalnızca SAN çalışmalı ancak NFS ve CIFS dosya paylaşımı zorunlu olmalıdır."
    )

    absurdities = AdvisorEngine.detect_tender_absurdities(absurd_tender)
    assert len(absurdities) >= 2, f"En az 2 absürt madde bulunmalıydı: {absurdities}"
    full_str = " ".join(absurdities)
    assert "RAM" in full_str
    assert "kontrol" in full_str


def test_scoring_engine_parser():
    """ScoringEngine parser'ının sayısal alanları doğru çıkardığını test eder."""
    sample = "En az 2 adet kontrol ünitesi ve toplamda en az 256 GB RAM ile 2U şasi olmalıdır."
    req = ScoringEngine.parse_requirements(sample)

    assert req.min_controllers == 2
    assert req.min_ram_total_gb == 256
    assert req.max_rack_units == 2
