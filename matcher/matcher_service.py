"""Şartname Karşılaştırma Orkestrasyon Servisi (SOLID: SRP, DIP).

Gelen şartname metnini veya Word (.docx) dosyasını inceler,
katalogdaki tüm ürünleri değerlendirir, puanlar ve en uygun modelleri
akıllı tavsiyeler ve absürtlük analiziyle birlikte döner.
"""

from pathlib import Path

import docx

from matcher.advisor_engine import AdvisorEngine
from matcher.scoring_engine import ScoringEngine
from shared.catalog_service import ExcelCatalogService
from shared.models import MatchRequest, MatchResult


class MatcherService:
    """Şartname karşılaştırma ve en uygun ürün bulma servisi."""

    def __init__(self, catalog_service: ExcelCatalogService | None = None):
        self.catalog = catalog_service or ExcelCatalogService()

    @staticmethod
    def extract_text_from_docx(file_path: str | Path) -> str:
        """Word (.docx) şartname dosyasından metin çıkarır."""
        p = Path(file_path)
        if not p.exists() or p.suffix.lower() != ".docx":
            return ""

        doc = docx.Document(p)
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs)

    def match_specification(self, request: MatchRequest) -> list[MatchResult]:
        """Şartnameyi analiz eder, katalog modellerini puanlar ve sıralı liste döner."""
        text = request.specification_text or ""

        # Dosya yolu verilmişse dosyadan oku
        if request.specification_file:
            doc_text = self.extract_text_from_docx(request.specification_file)
            if doc_text:
                text = f"{text}\n{doc_text}".strip()

        if not text:
            return []

        # 1. Şartname kriterlerini parse et
        req = ScoringEngine.parse_requirements(text)

        # 2. Şartname genelindeki absürt talepleri tespit et
        tender_absurdities: list[str] = []
        if request.include_absurd_analysis:
            tender_absurdities = AdvisorEngine.detect_tender_absurdities(text)

        # 3. Katalogdaki tüm modelleri tara ve puanla
        specs = self.catalog.get_all_specs()
        results: list[MatchResult] = []

        for spec in specs:
            score, details, model_absurdities = ScoringEngine.evaluate_spec(req, spec)

            all_absurd = list(tender_absurdities)
            all_absurd.extend(model_absurdities)

            if score >= 90.0:
                tier = "TAM_UYUM"
            elif score >= 80.0:
                tier = "BUYUK_COGUNLUK"
            elif score >= 60.0:
                tier = "UFAK_DEGISIKLIK"
            else:
                tier = "UYUMSUZ"

            matched_cnt = sum(1 for d in details if d.tier == "TAM_UYUM")
            recommendation = AdvisorEngine.generate_recommendation(
                model_name=spec.model_name,
                score=score,
                tier=tier,
                details=details,
                absurd_items=all_absurd,
            )

            results.append(
                MatchResult(
                    model_name=spec.model_name,
                    series=spec.series,
                    overall_score=score,
                    tier=tier,
                    matched_count=matched_cnt,
                    total_evaluated=len(details),
                    details=details,
                    absurd_items=all_absurd,
                    recommendation=recommendation,
                )
            )

        # 4. Puana göre azalan sırada sırala ve top-N dön
        # Puan eşitliğinde doğrudan hedeflenen model ve tam eşleşen kriter sayısı öne geçer
        results.sort(
            key=lambda r: (
                r.overall_score,
                1 if any(d.feature == "Model Spesifikasyonu" for d in r.details) else 0,
                r.matched_count,
            ),
            reverse=True,
        )
        return results[: request.top_n]


def get_matcher_service() -> MatcherService:
    """Varsayılan yapılandırmayla MatcherService nesnesi döner."""
    return MatcherService()
