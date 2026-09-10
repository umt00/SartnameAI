"""Şartname Karşılaştırma ve Puanlama Motoru (SOLID: SRP & OCP).

Çok katmanlı kurumsal puanlama:
- Tier 1: Tam Eşleşme (Skor 90-100) — Şartnamedeki tüm talepleri karşılar
- Tier 2: Büyük Çoğunluk Eşleşme (Skor 80-89) — Kritik taleplerin çoğunu sağlar
- Tier 3: Ufak Değişiklikle Uyacak (Skor 60-79) — Küçük donanım güncellemeleriyle şartnameye uyar
- Tier 4: Absürt Talep Tespiti — Sektör standartlarına aykırı, tutarsız talepleri filtreler
"""

import re
from typing import ClassVar

from shared.models import MatchScoreDetail, StorageSpec


class TenderRequirement:
    """Şartname metninden çıkarılan teknik gereksinimler."""

    def __init__(self):
        self.storage_tier: str | None = None  # "All-Flash", "Hibrit"
        self.min_controllers: int = 2
        self.min_ram_total_gb: int | None = None
        self.min_ram_per_node_gb: int | None = None
        self.min_nvram_total_gb: float | None = None
        self.min_drives: int | None = None
        self.min_ip_ports: int | None = None
        self.min_fc_ports: int | None = None
        self.max_rack_units: int | None = None
        self.min_cores: int | None = None
        self.scale_out_required: bool = False
        self.encryption_required: bool = False
        self.raw_demands: list[str] = []


class ScoringEngine:
    """Teknik şartname gereksinimlerini katalog modelleriyle kıyaslayan puanlama motoru."""

    WEIGHTS: ClassVar[dict[str, float]] = {
        "tier_arch": 0.20,
        "controllers": 0.15,
        "ram": 0.20,
        "drives": 0.15,
        "networking": 0.15,
        "chassis": 0.10,
        "processor": 0.05,
    }

    @classmethod
    def parse_requirements(cls, tender_text: str) -> TenderRequirement:
        """Şartname metnini analiz ederek parametrik gereksinimleri çıkarır."""
        req = TenderRequirement()
        text_lower = tender_text.lower()

        # 1. Depolama Ortamı (Tier)
        if any(t in text_lower for t in ["all-flash", "all flash", "nvme ssd", "yalnızca ssd"]):
            req.storage_tier = "All-Flash"
        elif any(t in text_lower for t in ["hibrit", "hybrid", "nl-sas"]):
            req.storage_tier = "Hibrit"

        # 2. Kontrol Ünitesi
        m_ctrl = re.search(r"(\d+)\s*(?:adet|tane)?\s*kontrol\s*ünite", text_lower)
        if m_ctrl:
            req.min_controllers = int(m_ctrl.group(1))
        elif "ha pair" in text_lower or "aktif-aktif" in text_lower:
            req.min_controllers = 2

        # 3. Sistem Belleği (RAM)
        m_ram_tot = re.search(
            r"(?:toplam(?:da)?|sistem(?:de)?)[^.]+?(\d+)\s*gb\s*(?:[^\n\.,;]*?)(?:ram|bellek|dram)",
            text_lower,
        )
        if m_ram_tot:
            req.min_ram_total_gb = int(m_ram_tot.group(1))
        else:
            m_ram_gen = re.search(
                r"(\d+)\s*gb\s*(?:[^\n\.,;]*?)(?:ram|bellek|dram)", text_lower
            )
            if m_ram_gen:
                req.min_ram_total_gb = int(m_ram_gen.group(1))

        # Kontrol ünitesi başı RAM: "her bir kontrol ünitesi üzerinde en az 64 GB"
        m_ram_node = re.search(
            r"(?:her bir|düğüm|kontrol ünitesi)\s*[^.]+?(\d+)\s*gb\s*(?:[^\n\.,;]*?)(?:ram|bellek)",
            text_lower,
        )
        if m_ram_node:
            req.min_ram_per_node_gb = int(m_ram_node.group(1))

        # 4. NVRAM / NVMEM
        m_nv = re.search(r"(\d+(?:\.\d+)?)\s*gb\s*(?:nvram|nvmem|kalıcı yazma belleği)", text_lower)
        if m_nv:
            req.min_nvram_total_gb = float(m_nv.group(1))

        # 5. Disk Sürücü Sayısı
        m_drives = re.search(r"(\d+)\s*(?:adet)?\s*(?:disk|sürücü)", text_lower)
        if m_drives:
            req.min_drives = int(m_drives.group(1))

        # 6. Ağ ve Portlar
        m_ip = re.search(r"(\d+)\s*(?:adet)?\s*(?:ethernet|10g|25g|ip)\s*port", text_lower)
        if m_ip:
            req.min_ip_ports = int(m_ip.group(1))

        m_fc = re.search(r"(\d+)\s*(?:adet)?\s*(?:fc|fibre channel|16g|32g)\s*port", text_lower)
        if m_fc:
            req.min_fc_ports = int(m_fc.group(1))

        # 7. Şasi Yüksekliği (U)
        m_u = re.search(r"(\d+)\s*u\s*(?:kabin|şasi|yükseklik)", text_lower)
        if m_u:
            req.max_rack_units = int(m_u.group(1))

        # 8. Çekirdek Sayısı
        m_cores = re.search(r"(\d+)\s*(?:fiziksel)?\s*çekirdek", text_lower)
        if m_cores:
            req.min_cores = int(m_cores.group(1))

        # 9. Scale-Out & Şifreleme
        req.scale_out_required = any(
            t in text_lower for t in ["scale-out", "yatayda büyüme", "kümeleme", "cluster"]
        )
        req.encryption_required = any(
            t in text_lower for t in ["şifreleme", "fde", "sed", "volume encryption"]
        )

        return req

    @classmethod
    def evaluate_spec(
        cls, req: TenderRequirement, spec: StorageSpec
    ) -> tuple[float, list[MatchScoreDetail], list[str]]:
        """Bir StorageSpec modelini şartname gereksinimlerine göre puanlar."""
        details: list[MatchScoreDetail] = []
        absurd_flags: list[str] = []

        scores: dict[str, float] = {}

        # 1. Depolama Mimarisi / Türü
        if req.storage_tier:
            if req.storage_tier.lower() in spec.storage_tier.lower():
                scores["tier_arch"] = 100.0
                details.append(
                    MatchScoreDetail(
                        feature="Depolama Türü (Tier)",
                        required_value=req.storage_tier,
                        actual_value=spec.storage_tier,
                        score=100.0,
                        tier="TAM_UYUM",
                        note="Depolama mimarisi şartnameyle tam uyumlu.",
                    )
                )
            else:
                scores["tier_arch"] = 40.0
                details.append(
                    MatchScoreDetail(
                        feature="Depolama Türü (Tier)",
                        required_value=req.storage_tier,
                        actual_value=spec.storage_tier,
                        score=40.0,
                        tier="ONEMLI_FARK",
                        note=f"İstenen tür '{req.storage_tier}', üründeki tür '{spec.storage_tier}'.",
                    )
                )
        else:
            scores["tier_arch"] = 100.0

        # 2. Kontrol Ünitesi
        if spec.controller_count >= req.min_controllers:
            scores["controllers"] = 100.0
            details.append(
                MatchScoreDetail(
                    feature="Kontrol Ünitesi Sayısı",
                    required_value=f"En az {req.min_controllers}",
                    actual_value=f"{spec.controller_count} adet",
                    score=100.0,
                    tier="TAM_UYUM",
                    note="Kontrol ünitesi yedekliliği (HA Pair) şartı sağlandı.",
                )
            )
        else:
            scores["controllers"] = 30.0
            details.append(
                MatchScoreDetail(
                    feature="Kontrol Ünitesi Sayısı",
                    required_value=f"En az {req.min_controllers}",
                    actual_value=f"{spec.controller_count} adet",
                    score=30.0,
                    tier="ONEMLI_FARK",
                    note="İstenen kontrol ünitesi sayısının altında.",
                )
            )

        # 3. Sistem Belleği (RAM)
        if req.min_ram_total_gb:
            # Absürt Talep Kontrolü: 2U veya giriş-orta seviye sisteme 1024 GB+ RAM istenmişse
            if req.min_ram_total_gb > 512 and spec.rack_units <= 2 and "FAS" in spec.series:
                absurd_flags.append(
                    f"İstenen {req.min_ram_total_gb} GB RAM talebi {spec.series} için aşırı/absürttür. "
                    f"Bu sistem sınıfında optimum kapasite {spec.ram_total_gb} GB'dir."
                )

            if spec.ram_total_gb >= req.min_ram_total_gb:
                scores["ram"] = 100.0
                details.append(
                    MatchScoreDetail(
                        feature="Toplam Sistem Belleği (RAM)",
                        required_value=f"En az {req.min_ram_total_gb} GB",
                        actual_value=f"{spec.ram_total_gb} GB",
                        score=100.0,
                        tier="TAM_UYUM",
                        note="Sistem belleği şartname talebini karşılıyor.",
                    )
                )
            elif spec.ram_total_gb >= req.min_ram_total_gb * 0.75:
                scores["ram"] = 75.0
                details.append(
                    MatchScoreDetail(
                        feature="Toplam Sistem Belleği (RAM)",
                        required_value=f"En az {req.min_ram_total_gb} GB",
                        actual_value=f"{spec.ram_total_gb} GB",
                        score=75.0,
                        tier="UFAK_FARK",
                        note=f"Ufak fark ({req.min_ram_total_gb - spec.ram_total_gb} GB eksik), opsiyonel yükseltmeyle sağlanabilir.",
                    )
                )
            else:
                scores["ram"] = 40.0
                details.append(
                    MatchScoreDetail(
                        feature="Toplam Sistem Belleği (RAM)",
                        required_value=f"En az {req.min_ram_total_gb} GB",
                        actual_value=f"{spec.ram_total_gb} GB",
                        score=40.0,
                        tier="ONEMLI_FARK",
                        note=f"Önemli RAM farkı mevcut ({spec.ram_total_gb} GB < {req.min_ram_total_gb} GB).",
                    )
                )
        else:
            scores["ram"] = 100.0

        # 4. Disk ve Sürücü Kapasitesi
        if req.min_drives:
            if spec.max_drives >= req.min_drives:
                scores["drives"] = 100.0
                details.append(
                    MatchScoreDetail(
                        feature="Azami Sürücü Kapasitesi",
                        required_value=f"En az {req.min_drives} disk",
                        actual_value=f"{spec.max_drives} disk desteği",
                        score=100.0,
                        tier="TAM_UYUM",
                        note="Sürücü genişleme sınırı talebi karşılıyor.",
                    )
                )
            elif spec.max_drives >= req.min_drives * 0.8:
                scores["drives"] = 75.0
                details.append(
                    MatchScoreDetail(
                        feature="Azami Sürücü Kapasitesi",
                        required_value=f"En az {req.min_drives} disk",
                        actual_value=f"{spec.max_drives} disk",
                        score=75.0,
                        tier="UFAK_FARK",
                        note="İstenen disk sayısına yakın seviyede.",
                    )
                )
            else:
                scores["drives"] = 40.0
                details.append(
                    MatchScoreDetail(
                        feature="Azami Sürücü Kapasitesi",
                        required_value=f"En az {req.min_drives} disk",
                        actual_value=f"{spec.max_drives} disk",
                        score=40.0,
                        tier="ONEMLI_FARK",
                        note=f"Maksimum sürücü desteği yetersiz ({spec.max_drives} < {req.min_drives}).",
                    )
                )
        else:
            scores["drives"] = 100.0

        # 5. Ağ ve Port Bağlantıları
        net_score = 100.0
        if req.min_ip_ports and spec.ip_port_count < req.min_ip_ports:
            net_score -= 20.0
        if req.min_fc_ports and spec.fc_port_count < req.min_fc_ports:
            net_score -= 25.0
        scores["networking"] = max(20.0, net_score)

        details.append(
            MatchScoreDetail(
                feature="Ağ ve Bağlantı Portları",
                required_value=(
                    f"IP: {req.min_ip_ports or '-'}, FC: {req.min_fc_ports or '-'}"
                ),
                actual_value=(
                    f"IP: {spec.ip_port_count}x {spec.ip_port_speed_gbps}GbE, "
                    f"FC: {spec.fc_port_count}x {spec.fc_port_speed_gbps}G"
                ),
                score=scores["networking"],
                tier="TAM_UYUM" if scores["networking"] >= 90 else "UFAK_FARK",
                note="Port yapılandırması PCIe veya dahili kartlarla genişletilebilir.",
            )
        )

        # 6. Şasi Boyutu
        if req.max_rack_units:
            if spec.rack_units <= req.max_rack_units:
                scores["chassis"] = 100.0
                details.append(
                    MatchScoreDetail(
                        feature="Şasi Kabin Yüksekliği",
                        required_value=f"En fazla {req.max_rack_units}U",
                        actual_value=f"{spec.rack_units}U",
                        score=100.0,
                        tier="TAM_UYUM",
                        note="Kabin alanı sınırı karşılandı.",
                    )
                )
            else:
                scores["chassis"] = 50.0
                details.append(
                    MatchScoreDetail(
                        feature="Şasi Kabin Yüksekliği",
                        required_value=f"En fazla {req.max_rack_units}U",
                        actual_value=f"{spec.rack_units}U",
                        score=50.0,
                        tier="ONEMLI_FARK",
                        note=f"Şasi kabinde daha fazla yer kaplıyor ({spec.rack_units}U > {req.max_rack_units}U).",
                    )
                )
        else:
            scores["chassis"] = 100.0

        # 7. İşlemci
        scores["processor"] = 100.0

        # Ağırlıklı Toplam Puan Hesaplama
        overall_score = sum(scores[cat] * cls.WEIGHTS[cat] for cat in cls.WEIGHTS)

        return round(overall_score, 1), details, absurd_flags
