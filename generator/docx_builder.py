 """Word Dokümanı (.docx) Üretim Servisi (SOLID: SRP & OCP).

Örnek şartname belgesinin (.docx) stillerini, başlık hiyerarşisini ve madde düzenini
koruyarak yeni şartname dokümanı üretir.
"""

from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from shared.config import get_settings
from shared.models import Clause, SpecRequest, StorageSpec


class DocxSpecificationBuilder:
    """Örnek şartname formatında .docx dosyası oluşturan motor."""

    def __init__(self, template_path: Path | None = None):
        self.template_path = template_path or get_settings().template_path

    def build_docx(
        self,
        request: SpecRequest,
        spec: StorageSpec,
        clauses: list[Clause],
        output_path: str,
    ) -> str:
        """Şartnameyi .docx olarak üretir ve dosya yolunu döndürür."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # Şablonu açarak stilleri ve sayfa yapısını miras al
        if self.template_path.exists():
            doc = docx.Document(self.template_path)
            # Mevcut paragrafları temizle (şablon stilleri korunur)
            for p in list(doc.paragraphs):
                p._element.getparent().remove(p._element)
        else:
            doc = docx.Document()

        # 1. Başlık: TEKNİK ŞARTNAME
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_title.paragraph_format.space_before = Pt(12)
        p_title.paragraph_format.space_after = Pt(12)
        r_title = p_title.add_run("TEKNİK ŞARTNAME")
        r_title.bold = True
        r_title.font.size = Pt(16)
        r_title.font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)  # Kurumsal Koyu Mavi

        # 2. Bölüm Başlığı: ÜRÜN TEKNİK ÖZELLİKLERİ
        p_sec = doc.add_paragraph()
        p_sec.paragraph_format.space_before = Pt(6)
        p_sec.paragraph_format.space_after = Pt(4)
        r_sec = p_sec.add_run("ÜRÜN TEKNİK ÖZELLİKLERİ")
        r_sec.bold = True
        r_sec.font.size = Pt(12)

        # 3. Alt Başlık: Depolama Sistemi Türü ve Miktarı
        p_sub = doc.add_paragraph()
        p_sub.paragraph_format.space_before = Pt(2)
        p_sub.paragraph_format.space_after = Pt(10)

        system_type_name = "All-Flash" if "All-Flash" in spec.storage_tier else "Hibrit"
        if request.flexibility == "tekil":
            sub_title_text = (
                f"{system_type_name} Veri Depolama Sistemi ({spec.model_name}) (1 Adet)"
            )
        else:
            sub_title_text = f"{system_type_name} Veri Depolama Sistemi (1 Adet)"

        r_sub = p_sub.add_run(sub_title_text)
        r_sub.bold = True
        r_sub.font.size = Pt(11)

        # 4. Şartname Maddeleri
        for i, c in enumerate(clauses, start=1):
            p_clause = doc.add_paragraph()
            p_clause.paragraph_format.space_before = Pt(2)
            p_clause.paragraph_format.space_after = Pt(4)
            p_clause.paragraph_format.line_spacing = 1.15

            # Madde numarası ve metni
            r_text = p_clause.add_run(f"1.{i}. {c.text}")
            r_text.font.size = Pt(10.5)

        # 5. Ayırıcı Çizgi ve Son Kontrol Notu (Disclaimer)
        doc.add_paragraph()
        p_disc = doc.add_paragraph()
        p_disc.paragraph_format.space_before = Pt(18)
        p_disc.paragraph_format.space_after = Pt(6)
        r_disc = p_disc.add_run(
            "ÖNEMLİ NOT: İşbu teknik şartname taslağı, ilgili donanım matrisleri ve kurumsal ihale standartları "
            "temel alınarak otomatik olarak oluşturulmuştur. İhale ve satın alma öncesinde teknik heyet tarafından "
            "madde madde kontrol edilmeli ve kurum ihtiyaçlarına göre nihai hale getirilmelidir."
        )
        r_disc.italic = True
        r_disc.font.size = Pt(9)
        r_disc.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)

        doc.save(str(out_file))
        return str(out_file)
