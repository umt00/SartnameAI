"""Akıllı Öneri ve Absürtlük Analiz Motoru (SOLID: SRP).

Şartnamedeki teknik tutarsızlıkları, imkansız veya absürt şartları tespit eder.
Eşleşen modeller için satış ve teklif ekibine yönlendirici tavsiyeler üretir.
"""

import re

from shared.models import MatchScoreDetail


class AdvisorEngine:
    """Teklif hazırlık ve şartname itiraz/düzeltme tavsiye motoru."""

    @classmethod
    def generate_recommendation(
        cls,
        model_name: str,
        score: float,
        tier: str,
        details: list[MatchScoreDetail],
        absurd_items: list[str],
    ) -> str:
        """Kullanıcıya veya satış ekibine yönelik kurumsal tavsiye metni oluşturur."""
        notes = []

        if score >= 90.0:
            notes.append(
                f"✅ **{model_name}**, işbu teknik şartname için **en uygun üründür (%{score:.1f} Tam Uyum)**. "
                "Tüm donanım, mimari ve port kapasitesi talepleri eksiksiz karşılanmaktadır. Doğrudan teklif edilebilir."
            )
        elif score >= 80.0:
            minor_issues = [d.note for d in details if d.tier == "UFAK_FARK"]
            notes.append(
                f"🟡 **{model_name}**, şartname şartlarının büyük çoğunluğunu sağlamaktadır (%{score:.1f} Uyum)."
            )
            if minor_issues:
                notes.append("Dikkat edilmesi gereken hususlar: " + "; ".join(minor_issues[:2]))
        elif score >= 60.0:
            diffs = [f"{d.feature} ({d.actual_value} < {d.required_value})" for d in details if d.tier in ("UFAK_FARK", "ONEMLI_FARK")]
            notes.append(
                f"🟠 **{model_name}**, şartnameye **ufak bir donanım revizyonu / ek kart** ile uyarlanabilir (%{score:.1f} Uyum). "
                f"Şartnameye uymayan alanlar: {', '.join(diffs[:2])}."
            )
        else:
            notes.append(
                f"🔴 **{model_name}**, şartname gereksinimlerini karşılamamaktadır (%{score:.1f} Uyumsuz). "
                "Üst seri modellerin (AFF veya FAS kurumsal seri) değerlendirilmesi önerilir."
            )

        if absurd_items:
            notes.append(
                "⚠️ **Tespit Edilen Absürt / Tutarsız Şartname Maddeleri:**\n"
                + "\n".join(f"- {item}" for item in absurd_items)
                + "\n> _Bu maddeler için ihale makamına zeyilname / teknik soru ile itiraz edilmesi önerilir._"
            )

        return "\n\n".join(notes)

    @classmethod
    def detect_tender_absurdities(cls, tender_text: str) -> list[str]:
        """Şartname metnindeki tutarsız veya mantıksız talepleri tespit eder."""
        text_lower = tender_text.lower()
        absurdities: list[str] = []

        # 1. Aşırı RAM Talebi
        m_ram = re.search(r"(\d+)\s*gb\s*(?:ram|bellek)", text_lower)
        if m_ram and int(m_ram.group(1)) > 1024:
            absurdities.append(
                f"Şartnamede istenen {m_ram.group(1)} GB RAM talebi, bu depolama sınıfı için piyasa standartlarının "
                "çok üzerindedir (aşırı maliyet ve gereksiz donanım şişirmesi)."
            )

        # 2. Çelişkili Kontrol Ünitesi ve Yedeklilik
        if "tek kontrol" in text_lower and any(h in text_lower for h in ["aktif-aktif", "ha pair", "kesintisiz failover"]):
            absurdities.append(
                "Şartnamede hem 'tek kontrol ünitesi' hem de 'aktif-aktif / kesintisiz failover' istenmiş. "
                "Tek kontrol ünitesiyle aktif-aktif donanımsal yük devretme mimarisi teknik olarak imkânsızdır."
            )

        # 3. İmkânsız Tekilleştirme Garantisi
        m_dedup = re.search(r"(\d+)\s*:\s*1\s*(?:tekilleştirme|verimlilik|deduplication)", text_lower)
        if m_dedup and int(m_dedup.group(1)) > 10:
            absurdities.append(
                f"Şartnamede {m_dedup.group(1)}:1 oranında veri tekilleştirme garantisi talep edilmiş. "
                "Endüstri standardı 3:1 veya 4:1 olup, veri türü bilinmeden 10:1 ve üzeri garanti verilmesi risklidir."
            )

        # 4. Çelişkili Protokol Desteği
        if "yalnızca san" in text_lower and any(p in text_lower for p in ["nfs", "cifs", "smb", "nas dosya"]):
            absurdities.append(
                "Şartnamede sistemin 'yalnızca SAN' olması istenirken aynı zamanda NAS (NFS/CIFS) dosya paylaşım "
                "protokolleri zorunlu tutulmuştur. Bu durum mimari çelişki içermektedir."
            )

        # 5. Dahili İşletim Sistemi (Root Volume) Sızıntısı
        if any(w in text_lower for w in ["root volume", "root alanı", "150 gib root", "150 gb root"]):
            absurdities.append(
                "Şartnamede 'root volume' / dahili işletim sistemi bölümü talep edilmiştir. "
                "Root volume depolama kontrol ünitesi işletim sisteminin dahili bölümü olup, kurumun kullanılabilir veri "
                "alanıyla ilgisi yoktur. Şartnamede açık bir üretici mimarisi sızıntısı (marka yönlendirmesi) teşkil eder."
            )

        # 6. Spesifik Firmware / Yama (Patch) Sürümü Dayatması
        if re.search(r"(?:ontap|firmware|işletim sistemi|yazılım)\s*(?:sürümü)?\s*(?:en az\s*)?(?:9\.\d+|1[0-9]\.\d+|rc\d+|p\d+)", text_lower):
            absurdities.append(
                "Şartnamede belirli bir üreticiye ait spesifik ara firmware/yazılım sürüm kodu dayatılmıştır. "
                "Şartnamelerde marka bağımsızlığı gereği 'üretici tarafından aktif olarak desteklenen güncel ve kararlı "
                "kurumsal sürüm' talep edilmelidir; doğrudan sürüm numarası yazılması ihaleye itiraz sebebidir."
            )

        # 7. Yapay Mikro-Limit ve Bileşen Tuzakları (800 havuz, 1500 bileşen, 65.536 bağlantı)
        if any(term in text_lower for term in ["800 adet depolama havuzu", "800 havuz", "1000 bileşen", "1500 bileşen", "65.536", "65536"]):
            absurdities.append(
                "Şartnamede tek bir üreticinin mimari sınırlarına karşılık gelen suni mikro-limitler (örn: 800 havuz, "
                "1000/1500 bileşen veya 65.536 bağlantı) tespit edilmiştir. Bu talepler rekabeti kısıtlayıcı nitelikte olup "
                "ihale komisyonuna zeyilname ile düzeltme talebi iletilmelidir."
            )

        return absurdities
