"""Alan modelleri ve veri transfer nesneleri (DTO).

SOLID: Tek Sorumluluk Prensibi (SRP) — Yalnızca sistemin veri şemalarını ve
doğrulama kurallarını tanımlar.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class StorageSpec(BaseModel):
    """Veri depolama sisteminin teknik donanım özelliklerini temsil eden çekirdek model."""

    model_name: str = Field(
        ..., description="Donanım model adı (Örn: FAS2820 Single Chassis HA Pair)"
    )
    series: str = Field(
        ..., description="Ürün ailesi/serisi (Örn: FAS, AFF A, AFF C, ASA, AFX, E-Series)"
    )
    architecture: str = Field(
        default="Unified (SAN, NAS ve Nesne)", description="Desteklenen depolama mimarisi"
    )
    storage_tier: str = Field(
        default="Hibrit (NVMe SSD ve NL-SAS)",
        description="Depolama ortamı türü (All-Flash, Hibrit vb.)",
    )
    controller_count: int = Field(default=2, description="Kontrol ünitesi sayısı")
    scale_out_max_nodes: int = Field(
        default=24, description="Yatayda desteklenen maksimum kontrol ünitesi sayısı"
    )
    scale_out_nas_nodes: str = Field(default="", description="NAS küme azami düğüm sayısı")
    scale_out_san_nodes: str = Field(default="", description="SAN küme azami düğüm sayısı")

    # Bellek Alanları (RAM & Multipliers)
    ram_per_node_gb: int = Field(
        default=64, description="Her kontrol ünitesindeki sistem belleği (GB)"
    )
    ram_total_gb: int = Field(default=128, description="Toplam sistem belleği (GB)")
    ram_raw_text: str = Field(default="", description="Tablodaki ham RAM metni (Örn: 64 GB DDR4)")

    # NVMEM / NVRAM / NVMe Cache Alanları
    nvmem_per_node_gb: float = Field(
        default=0.0, description="Her kontrol ünitesindeki NVMEM kapasitesi (GB)"
    )
    nvmem_total_gb: float = Field(default=0.0, description="Toplam NVMEM kapasitesi (GB)")
    nvram_per_node_gb: float = Field(
        default=0.0, description="Her kontrol ünitesindeki NVRAM kapasitesi (GB)"
    )
    nvram_total_gb: float = Field(default=0.0, description="Toplam NVRAM kapasitesi (GB)")
    nvme_cache_per_node_gb: int = Field(
        default=0, description="Düğüm başı dahili NVMe Flash önbellek (GB)"
    )
    nvme_cache_total_gb: int = Field(
        default=0, description="Toplam dahili NVMe Flash önbellek (GB)"
    )
    flash_read_cache_raw: str = Field(
        default="", description="Flash Read Cache (GB) (Min/Max)"
    )
    max_destaging_cache_raw: str = Field(
        default="", description="Max Destaging Cache-to-Flash Size (GB)"
    )

    # İşlemci Detayları
    processor_info: str = Field(default="", description="İşlemci modeli ve açıklaması")
    processor_arch: str = Field(default="64 bit", description="İşlemci mimarisi")
    processor_speed: str = Field(default="", description="İşlemci saat hızı")
    processor_cores_per_node: int = Field(default=0, description="Kontrol ünitesi başı çekirdek")
    processor_cores_total: int = Field(default=0, description="Sistem toplamı çekirdek")
    processor_count_per_node: int = Field(default=0, description="Kontrol ünitesi başı CPU adedi")
    processor_count_total: int = Field(default=0, description="Sistem toplamı CPU adedi")

    # Portlar ve Genişleme Yuvaları
    ethernet_ports_raw: str = Field(default="", description="Tablodaki Ethernet Port metni")
    fc_ports_raw: str = Field(default="", description="Tablodaki FC Port metni")
    sas_ports_raw: str = Field(default="", description="Tablodaki SAS Port metni")
    uta2_ports_raw: str = Field(default="", description="Tablodaki UTA2 Port metni")
    expansion_slots_raw: str = Field(default="", description="Genişleme slotları (PCIe / IO Module)")
    pci_interface_raw: str = Field(default="", description="PCI arayüzü (PCIe4, PCIe5 vb.)")
    oob_mgmt_port_raw: str = Field(default="", description="OOB yönetim portu")
    ip_port_count: int = Field(default=4, description="Toplam IP bağlantı portu sayısı")
    ip_port_speed_gbps: int = Field(default=10, description="IP portlarının asgari hızı (Gbps)")
    fc_port_count: int = Field(default=4, description="Toplam Fiber Channel (FC) port sayısı")
    fc_port_speed_gbps: int = Field(default=32, description="FC portlarının asgari hızı (Gbps)")

    # Sürücüler, Raflar ve Kapasite
    internal_drives_count: str = Field(default="", description="Dahili sürücü adedi")
    max_drives: int = Field(default=144, description="Desteklenen maksimum disk sürücü adedi")
    max_nlsas_drives: str = Field(default="", description="Maksimum NL-SAS disk adedi")
    max_sas_drives: str = Field(default="", description="Maksimum SAS disk adedi")
    max_ssd_drives: str = Field(default="", description="Maksimum SSD disk adedi")
    max_nvme_ssd_drives: str = Field(default="", description="Maksimum NVMe SSD disk adedi")
    max_capacity_flash_drives: str = Field(default="", description="Maksimum Capacity Flash NVMe SSD")
    shelves_supported: dict[str, str] = Field(
        default_factory=dict, description="Desteklenen disk raf modelleri ve adetleri"
    )
    max_raw_capacity: str = Field(
        default="3.45 PB", description="Genişleyebilir azami ham kapasite"
    )
    efficiency_guarantee: str = Field(
        default="3:1", description="Üretici veri tekilleştirme/verimlilik oranı"
    )

    # Şasi ve Fiziksel Boyutlar
    rack_units: int = Field(default=2, description="Şasi kabin yüksekliği (U)")
    chassis_height: str = Field(default="", description="Şasi yüksekliği")
    chassis_width: str = Field(default="", description="Şasi genişliği (genel)")
    chassis_width_with_flanges: str = Field(default="", description="Montaj kulakları dahil genişlik")
    chassis_width_without_flanges: str = Field(default="", description="Montaj kulakları hariç genişlik")
    chassis_depth: str = Field(default="", description="Şasi derinliği")
    chassis_weight: str = Field(default="", description="Şasi ağırlığı (kg / lb)")
    clearance_front: str = Field(default="", description="Ön bakım/soğutma boşluğu")
    clearance_rear: str = Field(default="", description="Arka bakım/soğutma boşluğu")

    # Çevresel Koşullar, Güç ve Akustik
    input_voltage: str = Field(default="", description="Giriş voltaj aralığı")
    acoustic_sound_power: str = Field(default="", description="Akustik ses gücü (Bels)")
    acoustic_sound_pressure: str = Field(default="", description="Akustik ses basıncı (dBA)")
    operating_temp: str = Field(default="", description="Çalışma sıcaklık aralığı")
    operating_humidity: str = Field(default="", description="Çalışma bağıl nem aralığı")
    operating_altitude: str = Field(default="", description="Çalışma irtifa aralığı")
    storage_temp: str = Field(default="", description="Depolama sıcaklık aralığı")
    storage_altitude: str = Field(default="", description="Depolama irtifa aralığı")
    transit_altitude: str = Field(default="", description="Nakliye ve taşıma irtifa aralığı")

    # Standartlar ve Sertifikalar
    certifications_emc: str = Field(default="", description="EMC/EMI Sertifikaları")
    certifications_safety: str = Field(default="", description="Güvenlik Sertifikaları")
    standards_emc: str = Field(default="", description="EMC/EMI Standartları")
    standards_safety: str = Field(default="", description="Güvenlik Standartları")

    # Firmware, İşletim Sistemi ve Limitler
    os_minimum: str = Field(default="", description="Asgari işletim sistemi sürümü")
    os_maximum: str = Field(default="", description="Azami işletim sistemi sürümü")
    os_recommended: str = Field(default="", description="Önerilen işletim sistemi sürümü")
    min_root_volume_size: str = Field(default="", description="Asgari kök birim alanı (Root Volume)")
    bios_version: str = Field(default="", description="BIOS sürümü")
    bmc_version: str = Field(default="", description="BMC sürümü")
    encryption_info: str = Field(default="", description="Şifreleme desteği (NVE, Dual-layer vb.)")
    full_disk_encryption_support: bool = Field(default=False, description="Donanımsal FDE disk şifreleme desteği")
    limits_aggregate: str = Field(default="", description="Maksimum Aggregate sınırı")
    limits_volume: str = Field(default="", description="Maksimum Volume sınırı")
    limits_flexgroup: str = Field(default="", description="Maksimum FlexGroup sınırı")
    limits_flexgroup_constituent: str = Field(default="", description="Maksimum FlexGroup bileşen sayısı")
    limits_lun: str = Field(default="", description="Maksimum LUN sınırı")
    limits_snapshot: str = Field(default="", description="Maksimum Snapshot sınırı")
    limits_svm: str = Field(default="", description="Maksimum SVM / Vserver sınırı")
    limits_connections: str = Field(default="", description="Maksimum eşzamanlı bağlantı sınırı")
    limits_consistency_group: str = Field(default="", description="Maksimum tutarlılık grubu sınırı")
    limits_igroup: str = Field(default="", description="Maksimum igroup sınırı")
    limits_max_files_node: str = Field(default="", description="Düğüm başı maksimum dosya / inode sayısı")
    limits_max_files_pair: str = Field(default="", description="HA çifti başı maksimum dosya / inode sayısı")
    limits_bucket: str = Field(default="", description="Maksimum S3/Nesne bucket sınırı")
    sector_bytes: str = Field(default="", description="Sektör / blok formatı (512 / 4096 bayt)")
    ddp_support: bool = Field(default=False, description="Dinamik Disk Havuzu (DDP) desteği")
    t10_pi_support: bool = Field(default=False, description="T10-PI Veri Güvencesi desteği")
    ssd_in_disk_pool_support: bool = Field(default=False, description="Disk havuzunda SSD desteği")

    source_file: str = Field(default="", description="Verinin çekildiği kaynak dosya veya URL")
    raw_attributes: dict[str, Any] = Field(
        default_factory=dict, description="Excel tablosundaki tüm ham sütunlar"
    )


class Clause(BaseModel):
    """Şartname içindeki tek bir teknik veya sözleşmesel madde."""

    id: int = Field(..., description="Madde numarası / sırası (1'den başlar)")
    category: str = Field(
        ..., description="Maddenin ait olduğu kategori (Örn: Mimari, Bellek, Güvenlik)"
    )
    title: str = Field(default="", description="Maddenin kısa başlığı veya konusu")
    text: str = Field(..., description="Şartname metnindeki nihai madde cümlesi")
    is_mandatory: bool = Field(default=True, description="Maddenin zorunlu olup olmadığı")
    is_parametric: bool = Field(
        default=False, description="Maddenin model parametrelerine bağlı olup olmadığı"
    )
    source_note: str = Field(default="", description="Maddenin dayandığı teknik dayanak veya kural")


class SpecRequest(BaseModel):
    """Şartname oluşturma isteği parametreleri."""

    model: str = Field(
        ..., description="Şartnamesi hazırlanacak donanım modeli (Örn: 'FAS2820', 'AFF A30')"
    )
    brand: str = Field(default="NetApp", description="Üretici marka adı")
    flexibility: Literal["tekil", "jenerik"] = Field(
        default="tekil",
        description="Esneklik modu: 'tekil' (markaya özgü) veya 'jenerik' (rekabete açık)",
    )
    disk_configuration: str | None = Field(
        default=None,
        description="İstenen özel disk yapılandırması (Örn: '8x 4TB NL-SAS + 28x 960GB SSD')",
    )
    target_capacity: str | None = Field(
        default=None, description="İstenen net veya ham kapasite eşiği (Örn: '150 TB')"
    )
    warranty_years: int = Field(default=5, description="Garanti süresi (yıl)")
    support_type: str = Field(default="9x5", description="Destek seviyesi (Örn: '9x5', '7x24')")


class MatchRequest(BaseModel):
    """Şartname karşılaştırma isteği parametreleri."""

    specification_text: str = Field(
        default="",
        description="Madde madde şartname metni (serbest metin veya docx parse edilmiş)",
    )
    specification_file: str | None = Field(
        default=None, description="Karşılaştırılacak şartname .docx dosya yolu"
    )
    top_n: int = Field(default=5, description="En fazla kaç ürün önerilsin")
    include_absurd_analysis: bool = Field(
        default=True, description="Absürt madde analizi yapılsın mı"
    )


class MatchScoreDetail(BaseModel):
    """Tek bir karşılaştırma maddesi için skor detayı."""

    feature: str = Field(..., description="Karşılaştırılan özellik/madde adı")
    required_value: str = Field(..., description="Şartnamede istenen değer")
    actual_value: str = Field(..., description="Üründe bulunan değer")
    score: float = Field(default=0.0, description="Bu madde için uyum puanı (0-100)")
    tier: str = Field(default="", description="Eşleşme seviyesi (TAM_UYUM, UFAK_FARK, ONEMLI_FARK, ABSURT)")
    note: str = Field(default="", description="Açıklama veya öneri")


class MatchResult(BaseModel):
    """Tek bir ürün için karşılaştırma sonucu."""

    model_name: str = Field(..., description="Ürün model adı")
    series: str = Field(default="", description="Ürün serisi")
    overall_score: float = Field(default=0.0, description="Genel uyum puanı (0-100)")
    tier: str = Field(
        default="",
        description="Genel seviye: TAM_UYUM, BUYUK_COGUNLUK, UFAK_DEGISIKLIK, UYUMSUZ",
    )
    matched_count: int = Field(default=0, description="Tam eşleşen madde sayısı")
    total_evaluated: int = Field(default=0, description="Değerlendirilen toplam madde sayısı")
    details: list[MatchScoreDetail] = Field(default_factory=list)
    absurd_items: list[str] = Field(
        default_factory=list, description="Tespit edilen absürt talepler"
    )
    recommendation: str = Field(default="", description="Genel tavsiye metni")


class CatalogModelSummary(BaseModel):
    """Katalogda kayıtlı bir donanım modelinin özet bilgisi."""

    model_name: str
    series: str
    file_name: str
    ram_total_gb: int
    max_drives: int
    max_raw_capacity: str


class GenerationResult(BaseModel):
    """Şartname oluşturma işleminin nihai sonucu."""

    document_title: str
    model_name: str
    series: str
    flexibility: str
    total_clauses: int
    file_path: str | None = None
    download_url: str | None = None
    verification_status: str = Field(
        default="VERIFIED_100_PERCENT", description="1:1 Doğrulama ve denetim durumu"
    )
    audit_coverage_pct: float = Field(
        default=100.0, description="Denetim eşleşme yüzdesi"
    )
    is_cached: bool = Field(
        default=False, description="Önbellekten sunulup sunulmadığı"
    )
    clauses: list[Clause] = Field(default_factory=list)
    specs: StorageSpec | None = None
    disclaimer: str = (
        "NOT: Bu doküman bir ön şartname taslağıdır. "
        "İhale ve satın alma öncesinde teknik ekip tarafından kontrol edilmeli ve onaylanmalıdır."
    )
