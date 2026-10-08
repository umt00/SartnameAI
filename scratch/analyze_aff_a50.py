import json
from pathlib import Path

from matcher.matcher_service import get_matcher_service
from shared.models import MatchRequest


def main():
    matcher_svc = get_matcher_service()
    docx_path = Path("output/Sartname_AFF_A50_tekil.docx")
    audit_path = Path("output/Sartname_AFF_A50_tekil.audit.json")

    print("=== 1. ŞARTNAME VE DENETİM DOĞRULAMA ===")
    print(f"Docx Dosyası: {docx_path.resolve()} (Mevcut: {docx_path.exists()}, Boyut: {docx_path.stat().st_size} bayt)")

    with open(audit_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)
    print(f"Hedef Model: {audit_data['model_name']}")
    print(f"Durum: {audit_data['status']}")
    print(f"Kapsama Oranı: %{audit_data['coverage_percentage']:.1f}")
    print(f"Eşleşen Kolon / Toplam: {audit_data['matched_columns']} / {audit_data['total_evaluated_columns']}")
    print(f"Kaçırılan Kolon: {audit_data['missed_columns']}")
    print(f"Toplam Madde Sayısı: {len(audit_data['clauses'])}")

    print("\n=== 2. EŞLEŞTİRME VE KARŞILAŞTIRMA MOTORU ÇALIŞTIRILIYOR ===")
    match_res = matcher_svc.match_specification(MatchRequest(
        specification_file=str(docx_path),
        top_n=10,
        include_absurd_analysis=True,
    ))

    print(f"Toplam Değerlendirilen Model Sıralaması (Top {len(match_res)}):\n")
    for rank, r in enumerate(match_res, 1):
        print(f"#{rank} | Model: {r.model_name:<36} | Skor: %{r.overall_score:5.1f} | Tier: {r.tier:<16} | Tam Eşleşen Kriter: {r.matched_count}/{r.total_evaluated}")

    print("\n=== 3. TAM EŞLEŞME (1:1) KONTROLÜ ===")
    top_1 = match_res[0]
    is_exact_match = ("AFF A50" in top_1.model_name) and (top_1.overall_score == 100.0) and (top_1.tier == "TAM_UYUM")
    print(f"1. Sıradaki Model: {top_1.model_name}")
    print(f"1. Sıradaki Skor: %{top_1.overall_score:.1f}")
    print(f"1. Sıradaki Tier: {top_1.tier}")
    print(f"Tam 1:1 Eşleşme Onayı: {'BAŞARILI (1:1 TAM EŞLEŞME)' if is_exact_match else 'BAŞARISIZ'}")

    print("\n--- 1. Sıradaki Modelin Kriter Detayları ---")
    for d in top_1.details:
        print(f"  * {d.feature}: İstenen={d.required_value} | Üründe={d.actual_value} | Skor={d.score:.0f} ({d.tier})")

    print("\n=== 4. DİĞER ALTERNATİF VE ÖNERİLERİN ANALİZİ ===")
    for rank, r in enumerate(match_res[1:6], 2):
        print(f"\n--- Alternatif #{rank}: {r.model_name} (Skor: %{r.overall_score:.1f} - {r.tier}) ---")
        diffs = [d for d in r.details if d.tier != "TAM_UYUM"]
        if diffs:
            print("  Farklılıklar / Eksikler:")
            for d in diffs:
                print(f"    - {d.feature}: İstenen={d.required_value} vs Mevcut={d.actual_value} (Skor: {d.score:.0f}) -> {d.note}")
        else:
            print("  Tüm temel kriterleri sağlıyor (fakat hedef model AFF A50 değil).")
        print(f"  Tavsiye Özeti: {r.recommendation.splitlines()[0] if r.recommendation else 'N/A'}")

if __name__ == "__main__":
    main()
