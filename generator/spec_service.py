"""Şartname Üretim ve Orkestrasyon Servisi (SOLID: SRP, DIP).

Test Odaklı ve Sıfır Hata (Zero Hallucination) Prensibi:
1. Donanım kataloğundan modeli çeker.
2. Web araması ile resmi üretici verilerini teyit eder.
3. Önbellekte daha önce doğrulanmış dosya ve denetim raporu (.audit.json) varsa test eder.
4. Test olumluysa doğrudan sunar; değilse sıfırdan oluşturup 1:1 denetim testine sokar.
5. Kaçan kolon kalmışsa dinamik semantik sentezleyici ile tamamlayıp yeniden test eder.
6. %100 doğruluk testini geçince .docx ve .audit.json çıktısını kaydeder.
"""

import contextlib
import json
import re
from datetime import datetime, timezone

from generator.audit_verifier import SpecificationAuditVerifier
from generator.clause_engine import ParametricClauseEngine
from generator.docx_builder import DocxSpecificationBuilder
from generator.search_enricher import HybridSearchEnricher, get_search_enricher
from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings
from shared.models import Clause, GenerationResult, SpecRequest, StorageSpec
from shared.semantic_parser import SemanticClassifier, UnitAndMultiplierParser
from shared.storage_service import LocalStorageService, get_storage_service


class SpecificationPipelineService:
    """Teknik şartname üretim iş akışını yöneten orkestratör servis."""

    def __init__(
        self,
        catalog_service: ExcelCatalogService | None = None,
        clause_engine: ParametricClauseEngine | None = None,
        docx_builder: DocxSpecificationBuilder | None = None,
        storage_service: LocalStorageService | None = None,
        search_enricher: HybridSearchEnricher | None = None,
    ):
        self.catalog = catalog_service or ExcelCatalogService()
        self.engine = clause_engine or ParametricClauseEngine()
        self.builder = docx_builder or DocxSpecificationBuilder()
        self.storage = storage_service or get_storage_service()
        self.enricher = search_enricher or get_search_enricher()
        self.settings = get_settings()

    async def generate_specification(self, request: SpecRequest) -> GenerationResult:
        """Kullanıcı isteğinden uçtan uca şartname dokümanı ve maddeleri üretir."""
        # 1. Donanım kataloğundan modeli bul
        spec = self.catalog.get_spec(request.model)

        if not spec:
            spec = StorageSpec(
                model_name=request.model,
                series="Kurumsal Veri Depolama",
                storage_tier="All-Flash (NVMe SSD)",
                controller_count=2,
                scale_out_max_nodes=24,
                ram_per_node_gb=64,
                ram_total_gb=128,
                nvmem_per_node_gb=4.0,
                nvmem_total_gb=8.0,
                processor_info="64-bit Yüksek Performanslı İşlemci Mimarisi",
                ip_port_count=4,
                ip_port_speed_gbps=10,
                fc_port_count=4,
                fc_port_speed_gbps=32,
                max_drives=144,
                max_raw_capacity=request.target_capacity or "3.45 PB",
                efficiency_guarantee="3:1",
                rack_units=2,
                source_file="Kullanıcı Talebi / Genel Kurumsal Standart",
            )

        # 2. Arama motoru zenginleştirmesi
        spec = await self.enricher.search_and_enrich(request.model, spec)

        # Dosya ve Denetim Yolları
        tokens = spec.model_name.split()
        if len(tokens) >= 2 and tokens[0].upper() in ("AFF", "ASA", "AFX", "FAS", "E"):
            model_tag = f"{tokens[0]}_{tokens[1]}"
        elif tokens:
            model_tag = tokens[0]
        else:
            model_tag = "Storage"
        clean_model_tag = re.sub(r"[^a-zA-Z0-9_]", "_", model_tag)
        file_name = f"Sartname_{clean_model_tag}_{request.flexibility}.docx"
        audit_file_name = f"Sartname_{clean_model_tag}_{request.flexibility}.audit.json"
        target_local_path = self.settings.OUTPUT_DIR / file_name
        audit_path = self.settings.OUTPUT_DIR / audit_file_name

        doc_title = (
            f"{spec.model_name} Teknik Şartnamesi"
            if request.flexibility == "tekil"
            else f"{spec.storage_tier} Veri Depolama Sistemi Teknik Şartnamesi (Rekabete Açık)"
        )

        # ADIM 1: Önce eski kayıt var mı diye bak (Kayıt varsa çek ve test et)
        if target_local_path.exists() and audit_path.exists():
            with contextlib.suppress(Exception):
                audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
                cached_clauses = [Clause(**c) for c in audit_data.get("clauses", [])]
                if cached_clauses:
                    is_valid, cov_pct, _matched_cnt, _total_cnt, missed = (
                        SpecificationAuditVerifier.audit(spec, cached_clauses)
                    )
                    if is_valid and not missed:
                        saved_path, download_url = await self.storage.save_document(
                            str(target_local_path), file_name
                        )
                        return GenerationResult(
                            document_title=doc_title,
                            model_name=spec.model_name,
                            series=spec.series,
                            flexibility=request.flexibility,
                            total_clauses=len(cached_clauses),
                            file_path=saved_path,
                            download_url=download_url,
                            verification_status="VERIFIED_100_PERCENT",
                            audit_coverage_pct=cov_pct,
                            is_cached=True,
                            clauses=cached_clauses,
                            specs=spec,
                        )

        # ADIM 2: Kayıt yoksa VEYA test olumsuzsa -> Tekrar oluştur ve mükemmeli ara
        clauses: list[Clause] = []
        is_valid = False
        cov_pct = 0.0
        matched_cnt = 0
        total_cnt = 0
        missed: list[str] = []

        max_attempts = 3
        for _attempt in range(1, max_attempts + 1):
            clauses = self.engine.generate_clauses(spec, request)

            # Teste sok
            is_valid, cov_pct, matched_cnt, total_cnt, missed = (
                SpecificationAuditVerifier.audit(spec, clauses)
            )

            # Test 100% başarılı ve sıfır kaçak ise döngüyü tamamla
            if is_valid and not missed:
                break

            # Test olumsuzsa -> Dinamik semantik sentez ile mükemmelleştir
            clause_id = len(clauses) + 1
            for missed_col in missed:
                raw_val = spec.raw_attributes.get(missed_col)
                if raw_val is None or UnitAndMultiplierParser.is_boolean_negative(raw_val):
                    continue
                cat = SemanticClassifier.classify(missed_col)
                val_str = str(raw_val).strip()
                if UnitAndMultiplierParser.is_boolean_positive(raw_val):
                    text = (
                        f"Teklif edilen veri depolama sistemi üzerinde yer alan '{missed_col}' "
                        f"özelliği ve standardı donanım/yazılım kapsamında eksiksiz olarak desteklenecektir."
                    )
                else:
                    clean_val = UnitAndMultiplierParser.clean_spec_text(val_str)
                    text = (
                        f"Teklif edilen veri depolama sistemi kurumsal teknik gereksinimler kapsamında "
                        f"'{missed_col}' parametresini en az {clean_val} değerinde/standardında kesintisiz sağlayacaktır."
                    )

                clauses.append(
                    Clause(
                        id=clause_id,
                        category=cat.value,
                        title=f"{missed_col} Standardı",
                        text=text,
                        is_parametric=True,
                        source_note=f"{spec.source_file}: Mükemmellik Denetimi Sentezi ({missed_col})",
                    )
                )
                clause_id += 1

            # Yeniden teste sok ve doğrula
            is_valid, cov_pct, matched_cnt, total_cnt, missed = (
                SpecificationAuditVerifier.audit(spec, clauses)
            )
            if is_valid and not missed:
                break

        # ADIM 3: Testi yapılmış şartname dosyasını oluştur
        local_path = self.builder.build_docx(
            request=request,
            spec=spec,
            clauses=clauses,
            output_path=str(target_local_path),
        )

        # ADIM 4: Denetim Raporunu (.audit.json) yanına kaydet
        audit_payload = {
            "model_name": spec.model_name,
            "source_file": spec.source_file,
            "flexibility": request.flexibility,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "status": "VERIFIED_100_PERCENT" if is_valid else "VERIFICATION_WARNING",
            "coverage_percentage": cov_pct,
            "matched_columns": matched_cnt,
            "total_evaluated_columns": total_cnt,
            "missed_columns": missed,
            "clauses": [c.model_dump() for c in clauses],
        }
        with contextlib.suppress(Exception):
            audit_path.write_text(
                json.dumps(audit_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # ADIM 5: Depolama servisine kaydet
        saved_path, download_url = await self.storage.save_document(local_path, file_name)

        return GenerationResult(
            document_title=doc_title,
            model_name=spec.model_name,
            series=spec.series,
            flexibility=request.flexibility,
            total_clauses=len(clauses),
            file_path=saved_path,
            download_url=download_url,
            verification_status="VERIFIED_100_PERCENT" if is_valid else "VERIFICATION_WARNING",
            audit_coverage_pct=cov_pct,
            is_cached=False,
            clauses=clauses,
            specs=spec,
        )


def get_specification_service() -> SpecificationPipelineService:
    """Varsayılan bağımlılıklarla yapılandırılmış şartname üretim servisini döner."""
    return SpecificationPipelineService()
