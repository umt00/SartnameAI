"""Doğrulama ve metin filtreleme araçları.

SOLID: SRP — Jenerik modda marka/model sızıntılarını temizler ve doğrular.
"""

import re

# Temizlenecek marka ve tescilli ürün adları listesi
PROPRIETARY_TERMS = [
    r"\bnetapp\b",
    r"\bontap\b",
    r"\bfas\b",
    r"\bfas2820\b",
    r"\bfas70\b",
    r"\bfas90\b",
    r"\bfas50\b",
    r"\baff\b",
    r"\basa\b",
    r"\bafx\b",
    r"\bfabricpool\b",
    r"\bflexgroup\b",
    r"\bmetrocluster\b",
    r"\bsnapmirror\b",
    r"\bsnaprestore\b",
    r"\bwafl\b",
]


def scrub_brand_and_model(text: str, brand_name: str = "NetApp", model_name: str = "") -> str:
    """Metin içerisindeki marka ve modele özgü ifadeleri jenerik karşılıklarla değiştirir."""
    result = text

    if brand_name:
        result = re.sub(rf"\b{re.escape(brand_name)}\b", "üretici", result, flags=re.IGNORECASE)

    if model_name:
        clean_model = model_name.split()[0]
        result = re.sub(
            rf"\b{re.escape(clean_model)}\b", "teklif edilen sistem", result, flags=re.IGNORECASE
        )

    replacements = {
        r"\bONTAP\b": "Depolama İşletim Sistemi",
        r"\bFabricPool\b": "Otomatik Bulut/Katmanlama Teknolojisi",
        r"\bFlexGroup\b": "Genişletilmiş Dosya Sistemi",
        r"\bSnapMirror\b": "Depolama Tabanlı Uzak Replikasyon",
        r"\bSnapRestore\b": "Anlık Kopyadan Hızlı Geri Dönüş",
    }

    for pattern, repl in replacements.items():
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)

    return result


def validate_no_brand_leakage(text: str) -> tuple[bool, list[str]]:
    """Metinde marka/model sızıntısı olup olmadığını denetler."""
    leaks = []
    for pattern in PROPRIETARY_TERMS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            leaks.extend(set(matches))

    return (len(leaks) == 0, leaks)
