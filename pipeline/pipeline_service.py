"""ETL Pipeline Servisi (SOLID: SRP & OCP).

PDF formatındaki teknik şartname veya donanım dokümanlarını okur,
tabloları çıkarıp normalize eder, pivotlayarak Excel tablolarına dönüştürür.
Sonuçları doğrudan `data/catalogs/` ve arşiv dizinine aktarır.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber

from shared.config import get_settings


@dataclass
class PipelineRunResult:
    """Pipeline çalıştırma sonucu veri yapısı."""

    total_found: int
    processed_count: int
    failed_count: int
    processed_files: list[str]
    failed_files: list[str]
    output_excel_files: list[str]


class PipelineService:
    """PDF'ten normalize Excel'e dönüşüm sağlayan çekirdek servis."""

    def __init__(
        self,
        incoming_dir: Path | None = None,
        processed_dir: Path | None = None,
        catalogs_dir: Path | None = None,
        normalized_dir: Path | None = None,
    ):
        settings = get_settings()
        self.incoming_dir = incoming_dir or settings.PIPELINE_INCOMING_DIR
        self.processed_dir = processed_dir or settings.PIPELINE_PROCESSED_DIR
        self.catalogs_dir = catalogs_dir or settings.CATALOGS_DIR
        self.normalized_dir = normalized_dir or settings.NORMALIZED_EXCELS_DIR

        # Dizinlerin varlığını garantiye al
        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.catalogs_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def normalize_value(val: Any) -> str:
        """Tablodaki hücre metnini temizler."""
        if val is None:
            return ""
        return str(val).strip()

    def extract_from_pdf(self, pdf_path: Path) -> list[dict[str, str]]:
        """PDF dosyasından tablo verilerini model-özellik eşleşmesi olarak çıkarır."""
        extracted_data: list[dict[str, str]] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    headers = table[0]
                    if not headers:
                        continue
                    headers = [
                        str(h).replace("\n", " ").strip() if h else f"Col_{i}"
                        for i, h in enumerate(headers)
                    ]

                    for row in table[1:]:
                        if not row:
                            continue
                        feature = (
                            str(row[0]).replace("\n", " ").strip() if row[0] else ""
                        )
                        if not feature:
                            continue

                        for i, val in enumerate(row[1:], start=1):
                            if i < len(headers):
                                model_name = headers[i]
                                if not model_name or model_name.startswith("Col_"):
                                    continue

                                raw_val = (
                                    str(val).replace("\n", " ").strip() if val else ""
                                )
                                if not raw_val:
                                    continue

                                norm_val = self.normalize_value(raw_val)

                                extracted_data.append(
                                    {
                                        "Model": model_name,
                                        "Feature": feature,
                                        "Normalized_Value": norm_val,
                                        "Raw_Value": raw_val,
                                    }
                                )

        return extracted_data

    def process_single_pdf(self, pdf_path: Path) -> Path | None:
        """Tek bir PDF dosyasını işleyip Excel'e dönüştürür ve arşive taşır."""
        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            return None

        data = self.extract_from_pdf(pdf_path)
        if not data:
            return None

        df = pd.DataFrame(data)

        # Pivot: Satırlar Model, Sütunlar Feature
        pivot_df = df.pivot_table(
            index="Model",
            columns="Feature",
            values="Normalized_Value",
            aggfunc="first",
        ).reset_index()

        base_name = pdf_path.stem
        out_filename = f"{base_name}_excel.xlsx"
        catalog_out_path = self.catalogs_dir / out_filename

        # Excel'i data/catalogs ve 3_normalized_excels altına kaydet
        pivot_df.to_excel(catalog_out_path, index=False)
        if self.normalized_dir:
            norm_out_path = self.normalized_dir / out_filename
            pivot_df.to_excel(norm_out_path, index=False)

        # PDF'i işlenmişler arşivine taşı
        processed_pdf_path = self.processed_dir / pdf_path.name
        # Aynı isimde dosya varsa üzerine yaz
        if processed_pdf_path.exists():
            processed_pdf_path.unlink()
        shutil.move(str(pdf_path), str(processed_pdf_path))

        return catalog_out_path

    def process_all_pending(self) -> PipelineRunResult:
        """Gelenler klasöründeki tüm PDF'leri dönüştürür."""
        pdf_files = sorted(self.incoming_dir.glob("*.pdf"))

        processed_files: list[str] = []
        failed_files: list[str] = []
        output_excels: list[str] = []

        for pdf in pdf_files:
            try:
                out_excel = self.process_single_pdf(pdf)
                if out_excel:
                    processed_files.append(pdf.name)
                    output_excels.append(out_excel.name)
                else:
                    failed_files.append(pdf.name)
            except Exception:  # noqa: BLE001
                failed_files.append(pdf.name)

        return PipelineRunResult(
            total_found=len(pdf_files),
            processed_count=len(processed_files),
            failed_count=len(failed_files),
            processed_files=processed_files,
            failed_files=failed_files,
            output_excel_files=output_excels,
        )

    def get_status(self) -> dict[str, Any]:
        """Pipeline dizinlerinin ve dosyalarının anlık durumunu raporlar."""
        pending = [f.name for f in self.incoming_dir.glob("*.pdf")]
        processed = [f.name for f in self.processed_dir.glob("*.pdf")]
        catalogs = [f.name for f in self.catalogs_dir.glob("*.xlsx")]
        normalized = [f.name for f in self.normalized_dir.glob("*.xlsx")] if self.normalized_dir else []

        return {
            "incoming_dir": str(self.incoming_dir),
            "processed_dir": str(self.processed_dir),
            "catalogs_dir": str(self.catalogs_dir),
            "normalized_dir": str(self.normalized_dir) if self.normalized_dir else "",
            "pending_count": len(pending),
            "processed_count": len(processed),
            "catalog_excel_count": len(catalogs),
            "normalized_excel_count": len(normalized),
            "pending_files": pending,
            "processed_files": processed,
            "catalog_files": catalogs,
            "normalized_files": normalized,
        }
