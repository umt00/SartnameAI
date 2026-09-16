"""Şartname Maddeleri Dinamik ve Semantik Üretim Motoru (SOLID: SRP & OCP).

Tüm kurumsal depolama modelleri (FAS, AFF, ASA, AFX, E-Serisi) için geçerli,
kurumsal ihale standartlarına (Gartner Liderler, Full Redundancy, In-Line Veri Azaltma)
tam uyumlu, donanım limitlerini profesyonel dille ifade eden ve iç yazılım/çevre
ayrıntılarını (kök alan, sürüm yamaları, sıcaklık/nem) ayıklayan altın standart motor.
"""

import re

from shared.models import Clause, SpecRequest, StorageSpec
from shared.semantic_parser import (
    ColumnCategory,
    SemanticClassifier,
    TurkishNumberConverter,
    UnitAndMultiplierParser,
)
from shared.validators import scrub_brand_and_model


class ParametricClauseEngine:
    """Evrensel kurumsal şartname ve semantik parametre motoru."""

    def __init__(self):
        self.num_to_words = TurkishNumberConverter.to_words
        self.clean_text = UnitAndMultiplierParser.clean_spec_text

    def _calc_raw_pb_threshold(self, spec: StorageSpec) -> str:
        """Modelin azami kapasitesinden net PB alt sınırını hesaplar."""
        raw_text = spec.max_raw_capacity or ""
        m_pb = re.search(r"([\d\.]+)\s*PB", raw_text, re.IGNORECASE)
        if m_pb:
            return f"{m_pb.group(1)} PB"
        m_tib = re.search(r"(\d+)\s*TiB", raw_text, re.IGNORECASE)
        if m_tib:
            val = float(m_tib.group(1))
            if "a30" in spec.model_name.lower() or "c30" in spec.model_name.lower():
                return "4 PB"
            pb_val = round(val / 1024, 1)
            if pb_val >= 1:
                return f"{pb_val} PB"
        if "a30" in spec.model_name.lower():
            return "4 PB"
        if "fas2820" in spec.model_name.lower():
            return "3.45 PB"
        return "3 PB"

    def _calc_max_shelf_count(self, spec: StorageSpec) -> int:
        """Desteklenen harici disk rafı tavanını hesaplar."""
        counts = []
        for name, cnt in spec.shelves_supported.items():
            m = re.findall(r"\d+", str(cnt))
            if m:
                counts.extend(int(x) for x in m)
        return max(counts) if counts else 5

    def _calc_scale_out_node_limit(self, spec: StorageSpec) -> int:
        """Yatayda desteklenen azami kümeleme kontrol ünitesi adedini döner."""
        for val in [spec.scale_out_san_nodes, spec.scale_out_nas_nodes]:
            if val:
                m = re.search(r"\d+", str(val))
                if m:
                    return int(m.group(0))
        if spec.scale_out_max_nodes > 0:
            return spec.scale_out_max_nodes
        return 8

    def generate_clauses(self, spec: StorageSpec, request: SpecRequest) -> list[Clause]:
        """Tüm donanım parametrelerini kurumsal altın standartta şartname maddelerine dönüştürür."""
        clauses: list[Clause] = []
        clause_id = 1
        consumed_columns: set[str] = set()
        raw_attrs = spec.raw_attributes or {}

        def mark_consumed(*col_names: str):
            for cn in col_names:
                consumed_columns.add(cn.lower().strip())

        # =====================================================================
        # BÖLÜM 1: KURUMSAL GÜVENCE VE MİMARİ OMURGA (GOLD-STANDARD SPEC)
        # =====================================================================

        # 1.1 Tasarımcı Markası ve Microkernel Güvencesi
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.CHASSIS_PHYSICAL.value,
                title="Tasarımcı Markası ve Microkernel Güvencesi",
                text=(
                    "Teklif edilen veri depolama sistemi bileşenleri ve üzerinde çalışan yazılımlar "
                    "donanımın tasarımını yapan ve microkernel/yazılımları geliştiren firmanın markası ile teklif edilecektir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Microkernel & Donanım Bütünlüğü",
            )
        )
        clause_id += 1

        # 1.2 Gartner Magic Quadrant Liderler Konumu
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.COMPLIANCE.value,
                title="Gartner Magic Quadrant Liderler Konumu",
                text=(
                    "Veri depolama sistemi üreticisi yayınlanan en güncel 'Gartner Magic Quadrant for Primary Storage' "
                    "raporunda Liderler (Leaders) konumda olmalıdır."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Gartner Primary Storage Leaders",
            )
        )
        clause_id += 1

        # 1.3 Ürün Ailesi ve Depolama Mimarisi
        model_part = f" ({spec.model_name})" if request.flexibility == "tekil" else ""
        series_label = spec.series
        if ("all-flash" in spec.storage_tier.lower() or "all flash" in spec.storage_tier.lower()) and "hybrid" in series_label.lower():
            series_label = re.sub(r"\(Hybrid\s*/\s*High\s*Density\)", "(All-Flash / High Density)", series_label, flags=re.IGNORECASE)

        if "all-flash" in spec.storage_tier.lower() or "all flash" in spec.storage_tier.lower():
            media_desc = "veri ortamı olarak NVMe SSD teknolojisini kullanmalıdır"
            tier_desc = "yüksek performanslı tamamen flash depolama mimarisinde olmalı"
        elif "all-san" in spec.storage_tier.lower():
            media_desc = "veri ortamı olarak NVMe SSD teknolojisini kullanmalıdır"
            tier_desc = "blok depolama ortamları için optimize edilmiş simetrik All-SAN mimarisinde olmalı"
        else:
            media_desc = "NVMe SSD'ler ve NL-SAS / SAS disklerden oluşmalıdır"
            tier_desc = "hibrit kurumsal depolama mimarisinde olmalı"

        c3_text = (
            f"Teklif edilen veri depolama sistemi{model_part}, üreticinin en son nesil {series_label} "
            f"ürün ailesi içerisinde yer almalı; kurumsal iş yükleri için tasarlanmış {tier_desc} ve {media_desc}."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.CHASSIS_PHYSICAL.value,
                title="Depolama Mimarisi ve Ürün Ailesi",
                text=c3_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Series, Storage Tier, Architecture",
            )
        )
        clause_id += 1
        mark_consumed("model", "series", "storage tier", "architecture")

        # 1.4 Aktif-Aktif Kontrol Ünitesi ve Şasi Mimarisi
        ctrl_words = self.num_to_words(spec.controller_count)
        c4_text = (
            f"Teklif edilen ana depolama şasisi standart 19 inç kabinlerde kullanılmak üzere en fazla {spec.rack_units}U "
            f"kabin yüksekliğinde olmalı ve aynı şasi içerisinde yer alan, tekil kontrolör arızalarına karşı hizmet "
            f"sürekliliğini destekleyecek şekilde kendi içerisinde aktif-aktif olarak çalışan ve birbirini donanımsal "
            f"arızalara karşı yedekleyen en az {spec.controller_count} ({ctrl_words}) adet kontrol ünitesinden (HA Pair) "
            f"oluşan yüksek erişilebilirlik yapısına sahip olmalıdır."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.CHASSIS_PHYSICAL.value,
                title="Aktif-Aktif Kontrol Ünitesi ve Şasi Yapısı",
                text=c4_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Rack Units, Controller Count",
            )
        )
        clause_id += 1
        mark_consumed("rack units", "controller count")

        # 1.5 Tam Donanımsal Yedeklilik (Full Redundancy & No SPOF)
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.HIGH_AVAILABILITY.value,
                title="Tam Donanımsal Yedeklilik (Full Redundancy)",
                text=(
                    "Teklif edilen veri depolama sistemi üzerinde yer alan aktif komponentlerde yedeksiz bir unsur bulunmayacaktır "
                    "(Full Redundancy). Her bir veri depolama sistemi üzerindeki aktif bileşenler birbirini tamamen yedekleyecek "
                    "şekilde aktif-aktif çalışacaktır (disk denetleyicileri, önbellek, fan ve soğutma sistemleri, güç kaynağı, "
                    "ön yüz (front end) ve arka yüz (back end) bağlantı birimleri gibi tüm aktif bileşenler)."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Full Redundancy & Active-Active",
            )
        )
        clause_id += 1

        # 1.6 Hizmet Kalitesi (QoS - Quality of Service)
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Hizmet Kalitesi (QoS) Desteği",
                text=(
                    "Veri depolama sistemi, QoS (Quality of Service – Hizmet Kalitesi) özelliğini destekleyecektir. "
                    "Bu özellik servis önceliklendirmesi veya limitlemesi şeklinde olacaktır. Bu özellik için lisans gerekiyorsa "
                    "desteklenen maksimum kapasite için teklife dahil edilecektir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: QoS Policy & Priority Control",
            )
        )
        clause_id += 1

        # 1.7 Tümleşik Erişim Protokolleri (Yerel Protokoller, Ağ Geçitsiz)
        if "all-san" in spec.storage_tier.lower() or "asa" in spec.series.lower():
            proto_text = (
                "Teklif edilen veri depolama sistemi kurumsal blok (SAN) yapıda çalışmayı destekleyecektir. "
                "FC, iSCSI ve NVMe-oF (NVMe/TCP, NVMe/FC) erişim protokol lisansları maksimum kapasite için teklife dahil edilecektir. "
                "Bu özellikler ağ geçitleri veya ayrı bir donanım ile sağlanmayacaktır."
            )
        elif "e-series" in spec.series.lower():
            proto_text = (
                "Teklif edilen veri depolama sistemi kurumsal blok (SAN) depolama mimarisinde çalışmayı destekleyecek; "
                "FC, iSCSI ve SAS ana sunucu arayüz protokol lisansları harici bir ağ geçidine ihtiyaç duyulmaksızın teklife dahil edilecektir."
            )
        else:
            proto_text = (
                "Teklif edilen veri depolama sistemi tümleşik (SAN, NAS ve Nesne) yapıda çalışmayı destekleyecektir. "
                "iSCSI, NVMe/TCP, NFS, SMB ve S3 erişim protokol lisansları maksimum kapasite için teklife dahil edilecektir. "
                "Bu özellikler ağ geçitleri veya ayrı bir donanım ile sağlanmayacaktır."
            )

        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.NETWORKING.value,
                title="Tümleşik Erişim Protokolleri Desteği",
                text=proto_text,
                is_parametric=True,
                source_note="Kurumsal İhale Standardı: Unified / SAN Native Protocols",
            )
        )
        clause_id += 1

        # 1.8 In-Line Donanımsal Veri Azaltma (Deduplication, Compression, Compaction, Zero-Detection)
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.DATA_PROTECTION.value,
                title="In-Line Donanımsal Veri Azaltma",
                text=(
                    "Teklif edilen veri depolama sistemi blok ve dosya (file) tipinde alanlar için in-line (anlık) olarak "
                    "tüm disk tiplerinde deduplication (tekilleştirme), compression (sıkıştırma), compaction (yoğunlaştırma) "
                    "ve zero-detection (sıfır yakalama) özelliklerine sahip olacaktır. Bu özellik için lisans gerekiyorsa "
                    "desteklenen maksimum kapasiteye göre yüklenici firma tarafından sağlanacaktır."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: In-Line Data Reduction Suite",
            )
        )
        clause_id += 1

        # =====================================================================
        # BÖLÜM 2: HESAPLAMA, BELLEK VE İLETİŞİM PORTLARI
        # =====================================================================

        # 2.1 İşlemci Mimarisi ve Çekirdek Sayısı
        if spec.processor_cores_total > 0 or spec.processor_info:
            cores_node_w = self.num_to_words(spec.processor_cores_per_node)
            cores_tot_w = self.num_to_words(spec.processor_cores_total)
            proc_speed_txt = f" ve en az {spec.processor_speed} çalışma saat hızına sahip" if spec.processor_speed else ""

            c_proc_text = (
                f"Her bir kontrol ünitesinde en az 1 (bir) adet, {spec.processor_arch} mimarisinde, en az "
                f"{spec.processor_cores_per_node} ({cores_node_w}) fiziksel çekirdekli{proc_speed_txt} kurumsal sınıf "
                f"işlemci bulunmalıdır. Yüksek erişilebilirlik yapılandırmasındaki iki kontrol ünitesi birlikte değerlendirildiğinde, "
                f"sistem toplamında en az {spec.processor_cores_total} ({cores_tot_w}) fiziksel işlemci çekirdeği sağlanmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.COMPUTE.value,
                    title="İşlemci Mimarisi ve Çekirdek Sayısı",
                    text=c_proc_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Processor Cores / Count",
                )
            )
            clause_id += 1
            mark_consumed(
                "processor model",
                "processor architecture",
                "processor speed",
                "processor cores (per node)",
                "processor cores (per config)",
                "processor count (per node)",
                "processor count (per config)",
            )

        # 2.2 DRAM Sistem Belleği
        if spec.ram_total_gb > 0 or spec.ram_per_node_gb > 0:
            ram_node_w = self.num_to_words(spec.ram_per_node_gb)
            ram_tot_w = self.num_to_words(spec.ram_total_gb)
            c_ram_text = (
                f"Her bir kontrol ünitesinde en az {spec.ram_per_node_gb} ({ram_node_w}) GB DRAM sistem belleği bulunmalı; "
                f"iki kontrol üniteli yapı için toplam sistem belleği en az {spec.ram_total_gb} ({ram_tot_w}) GB olmalıdır. "
                f"2 (iki) kontrol ünitesinden oluşan veri depolama sistemi desteklediği en yüksek önbellek kapasitesi ile teklif edilecektir. "
                f"SSD, flash, NVMe veya sanal bellek alanları bu bellek kapasitesi kapsamında kabul edilmeyecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.MEMORY.value,
                    title="DRAM Sistem Belleği",
                    text=c_ram_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: RAM Per Node: {spec.ram_per_node_gb} GB, Total: {spec.ram_total_gb} GB",
                )
            )
            clause_id += 1
            mark_consumed("ram (per node)", "ram (per config)", "system memory")

        # 2.3 Kalıcı Yazma Belleği (NVMEM / NVRAM) ve Pil/Akü Koruması
        nv_node = spec.nvmem_per_node_gb or spec.nvram_per_node_gb or spec.nvme_cache_per_node_gb
        nv_tot = spec.nvmem_total_gb or spec.nvram_total_gb or spec.nvme_cache_total_gb
        if nv_tot > 0:
            node_disp = int(nv_node) if nv_node.is_integer() else nv_node
            tot_disp = int(nv_tot) if nv_tot.is_integer() else nv_tot
            c_nv_text = (
                f"Sistem, elektrik veya kontrolör kesintilerinde henüz diske yazılmamış verilerin korunmasını desteklemek "
                f"amacıyla, her bir kontrol ünitesinde en az {node_disp} GB kalıcı bellek tabanlı yazma önbelleğine "
                f"(NVMEM/NVRAM) sahip olmalıdır. Toplam kalıcı yazma önbelleği kapasitesi en az {tot_disp} GB olmalı; "
                f"olası bir elektrik kesintisi halinde yazma belleğindeki tüm bilgilerin pil veya akü sistemi ile kesintisiz "
                f"korunması sağlanacaktır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Kalıcı Yazma Önbelleği ve Pil Koruması",
                    text=c_nv_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: NVMEM/NVRAM Per Node and Config",
                )
            )
            clause_id += 1
            mark_consumed(
                "nvmem (per node)",
                "nvmem (per config)",
                "nvram (per node)",
                "nvram (per config)",
                "nvme flash cache (per node)",
                "nvme flash cache (per config)",
                "flash read cache (gb) (min/max)",
                "max destaging cache-to- flash size (gb)",
            )

        # 2.4 Ağ ve İletişim Portları (+ 25G SR SFP28 Transceiver Modülleri)
        port_items = []
        if spec.ethernet_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.ethernet_ports_raw):
            port_items.append(f"en az {spec.ip_port_count} adet ve en az {spec.ip_port_speed_gbps} Gbps hızı destekleyen IP portu ({spec.ethernet_ports_raw.strip()})")
            mark_consumed("ethernet ports")
        else:
            port_items.append(f"en az {spec.ip_port_count} adet ve en az {spec.ip_port_speed_gbps} Gbps hızında IP port")

        if spec.fc_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.fc_ports_raw):
            port_items.append(f"en az {spec.fc_port_count} adet ve en az {spec.fc_port_speed_gbps} GB hızında Fiber Kanal (FC) portu ({spec.fc_ports_raw.strip()})")
            mark_consumed("fibre channel ports")
        else:
            port_items.append(f"en az {spec.fc_port_count} adet ve en az {spec.fc_port_speed_gbps} GB hızında Fiber Kanal (FC) port")

        if spec.uta2_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.uta2_ports_raw):
            port_items.append(f"en az {spec.uta2_ports_raw.strip()} UTA2 portu")
            mark_consumed("uta2 ports")
        if spec.sas_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.sas_ports_raw):
            port_items.append(f"harici disk rafı bağlantıları için en az {spec.sas_ports_raw.strip()} SAS portu")
            mark_consumed("sas ports")
        if spec.oob_mgmt_port_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.oob_mgmt_port_raw):
            port_items.append(f"denetleyici başına en az {spec.oob_mgmt_port_raw.strip()} harici yönetim (OOB) portu")
            mark_consumed("oob management port interface (per controller)")

        c_port_text = (
            f"Teklif edilen veri depolama sisteminde toplamda: {'; '.join(port_items)} bulunacaktır. "
            f"Tüm portlar kontrol ünitelerine eşit dağıtılmış olmalıdır ve tüm IP portlar için gerekli 25G SR SFP28 "
            f"transceiver modülleri teklife eksiksiz dahil edilmelidir."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.NETWORKING.value,
                title="Ağ Portları ve Altyapı Transceiver Modülleri",
                text=c_port_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Ethernet, FC, SAS Ports & Transceiver standard",
            )
        )
        clause_id += 1

        # 2.5 Genişleme Yuvaları (Expansion Slots)
        if spec.expansion_slots_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.expansion_slots_raw):
            c_exp_text = (
                f"Teklif edilen sistem, bağlantı ve G/Ç gereksinimlerinin artırılabilmesi amacıyla "
                f"sistem genelinde en az {spec.expansion_slots_raw.strip()} genişleme yuvasını (Expansion Slots / IO Module) desteklemelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NETWORKING.value,
                    title="Genişleme Yuvaları (Expansion Slots)",
                    text=c_exp_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Expansion Slots",
                )
            )
            clause_id += 1
            mark_consumed("expansion slots", "pci interface")

        # =====================================================================
        # BÖLÜM 3: SÜRÜCÜLER, RAFLAR, KAPASİTE VE VERİMLİLİK
        # =====================================================================

        # 3.1 Dahili Yuvalar ve Azami Sürücü Kapasitesi
        internal_cnt = self.clean_text(spec.internal_drives_count) if spec.internal_drives_count else "24"
        c_drive_text = (
            f"Ana depolama şasisi üzerinde en az {internal_cnt} adet dahili SSD/NVMe SSD sürücünün kullanılabilmesine "
            f"imkân tanınmalı; harici disk rafları ile birlikte bir yüksek erişilebilirlik çifti kapsamında toplamda "
            f"en az {spec.max_drives} adet sürücüye kadar büyüme desteklenmelidir."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.STORAGE_MEDIA.value,
                title="Dahili Yuvalar ve Azami Sürücü Kapasitesi",
                text=c_drive_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Internal Drives: {spec.internal_drives_count}, Max Drives: {spec.max_drives}",
            )
        )
        clause_id += 1
        mark_consumed("internal drives count", "max number of drives", "max number of drives (total)")

        # 3.2 Desteklenen Sürücü Tipleri ve Sınırları
        drv_limits = []
        if spec.max_nvme_ssd_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_nvme_ssd_drives):
            drv_limits.append(f"bir yüksek erişilebilirlik çifti kapsamında en az {self.clean_text(spec.max_nvme_ssd_drives)} adet NVMe SSD sürücü")
            mark_consumed("max number of nvme ssd drives")
        if spec.max_ssd_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_ssd_drives):
            drv_limits.append(f"en az {self.clean_text(spec.max_ssd_drives)} adet SSD sürücü")
            mark_consumed("max number of ssd drives")
        if spec.max_capacity_flash_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_capacity_flash_drives):
            drv_limits.append(f"en az {self.clean_text(spec.max_capacity_flash_drives)} adet Capacity Flash NVMe SSD")
            mark_consumed("max number of capacity flash nvme ssd drives")
        if spec.max_nlsas_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_nlsas_drives):
            drv_limits.append(f"en az {self.clean_text(spec.max_nlsas_drives)} adet NL-SAS sürücü")
            mark_consumed("max number of nl-sas drives")
        if spec.max_sas_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_sas_drives):
            drv_limits.append(f"en az {self.clean_text(spec.max_sas_drives)} adet SAS sürücü")
            mark_consumed("max number of sas drives")

        if drv_limits:
            c_drvt_text = (
                f"Sistem, yüksek performans gerektiren kurumsal iş yükleri için esnek sürücü yapılandırmalarını desteklemeli; "
                f"desteklenen sürücü tipleri ve azami sınırları kapsamında: {'; '.join(drv_limits)} desteği sunmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.STORAGE_MEDIA.value,
                    title="Desteklenen Sürücü Tipleri ve Sınırları",
                    text=c_drvt_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Supported Drive Types and Limits",
                )
            )
            clause_id += 1

        # 3.3 Özel Disk Yapılandırması (Kullanıcı İstemişse)
        if request.disk_configuration:
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.STORAGE_MEDIA.value,
                    title="Özel Disk Yapılandırması ve RAID Koruması",
                    text=(
                        f"Teklif edilen veri depolama sistemi üzerinde {request.disk_configuration} sürücülerle "
                        f"ve en az aynı anda 2 (iki) disk hatasına karşı veri kaybını engelleyen çift parite RAID "
                        f"(RAID-DP / RAID-6) koruma mimarisi oluşturulmalıdır."
                    ),
                    is_mandatory=True,
                    is_parametric=True,
                    source_note="Kullanıcı Özel Disk Yapılandırma Talebi",
                )
            )
            clause_id += 1

        # 3.4 Harici Disk Rafları (Shelves) — [USER REVISION 1.12 STANDARDI]
        max_shelf_count = self._calc_max_shelf_count(spec)
        shelf_w = self.num_to_words(max_shelf_count)
        c_shelf_text = (
            f"Teklif edilen sistem, farklı SSD ve/veya NVMe SSD raf seçenekleriyle harici kapasite genişlemesini "
            f"desteklemeli; yapılandırmaya bağlı olarak toplamda en az {max_shelf_count} ({shelf_w}) adet harici disk rafının "
            f"sisteme eklenebilmesine imkân vermelidir. Raf eklemeleri sistem çalışırken kesintisiz (online) yapılabilmelidir."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.EXPANSION_SHELF.value,
                title="Harici Disk Rafları ve Genişleme",
                text=c_shelf_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Desteklenen Raf Sütunları (Shelves)",
            )
        )
        clause_id += 1
        for k in raw_attrs:
            if "shelves" in k.lower():
                mark_consumed(k)

        # 3.5 Ham Kapasite ve Genişleme Sınırı — [USER REVISION 1.13 STANDARDI]
        calc_pb = self._calc_raw_pb_threshold(spec)
        c_raw_text = (
            f"Teklif edilen veri depolama sistemi, kurumsal ölçekte yüksek ham kapasite gereksinimlerini karşılayacak "
            f"şekilde, herhangi bir kontrol ünitesi veya sistem bileşeninde yükseltme (upgrade) gerektirmeden yalnızca "
            f"disk ve disk rafı (shelf) ekleyerek {spec.storage_tier} yapılandırmada en az {calc_pb} ham kapasiteyi "
            f"destekleyebilecek şekilde genişleyebilmelidir."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.STORAGE_MEDIA.value,
                title="Ham Kapasite Genişleme Tavanı",
                text=c_raw_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Max FabricPool / Raw Capacity",
            )
        )
        clause_id += 1
        mark_consumed("max fabricpool size", "max volume size (eb)", "max volume size")

        # 3.6 Veri Verimliliği Garantisi ve Telafi Taahhüdü — [GOLD-STANDARD SPEC]
        eff_ratio = spec.efficiency_guarantee or "4:1"
        c_eff_text = (
            f"Teklif edilen sistem; tekilleştirme, sıkıştırma ve benzeri veri azaltma teknolojilerini desteklemeli, "
            f"önceden sıkıştırılmış veri tipleri (video, resim, ses, PDF, exe vb.) dışında kalan veri tiplerinde "
            f"üretici koşulları çerçevesinde en az {eff_ratio} veri verimliliği oranı sağlayabilmelidir. "
            f"Belirtilen verimlilik oranının sağlanamaması durumunda eksik kalan kapasitenin karşılanması için gerekli ek "
            f"sürücüler ve bu sürücüler için gerekebilecek disk çekmecesi, lisans, kablo gibi tüm yazılım ve donanımlar "
            f"yüklenici firma tarafından ücretsiz olarak sağlanacaktır."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.DATA_PROTECTION.value,
                title="Veri Verimliliği Garantisi ve Telafi Taahhüdü",
                text=c_eff_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Efficiency Guarantee ({eff_ratio}) with Remedy clause",
            )
        )
        clause_id += 1
        mark_consumed("efficiency guarantee")

        # 3.7 Sistem Alanlarının Hesaplanması Güvencesi — [GOLD-STANDARD SPEC]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.STORAGE_MEDIA.value,
                title="Sistem Alanlarının Hesaplanması",
                text=(
                    "Teklif edilen veri depolama sistemi üzerinde üretici firmanın teknolojisi gereği kullanılması "
                    "gereken sistem alanları var ise bu alanlar toplam disk adedi/net kullanılabilir kapasite hesaplaması "
                    "haricinde tutulacaktır."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Net Kapasite Güvencesi (Overhead Excluded)",
            )
        )
        clause_id += 1

        # =====================================================================
        # BÖLÜM 4: ÖLÇEKLENEBİLİRLİK, MANTIKSAL YÖNETİM VE YAZILIM
        # =====================================================================

        # 4.1 Yatayda Genişleme (Scale-Out Kümeleme) — [USER REVISION 1.15 & 1.16 BİRLEŞTİRİLMİŞ]
        node_limit = self._calc_scale_out_node_limit(spec)
        node_w = self.num_to_words(node_limit)
        c_scale_text = (
            f"Sistem, kesintisiz büyümeyi destekleyen yatayda ölçeklenebilir küme mimarisine sahip olmalı; "
            f"dosya ve blok tabanlı depolama iş yüklerinde en az {node_limit} ({node_w}) kontrol ünitesine kadar genişleyebilmelidir."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.HIGH_AVAILABILITY.value,
                title="Ölçeklenebilir Küme Mimarisi (Scale-Out)",
                text=c_scale_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Max Nodes per Cluster (NAS / SAN)",
            )
        )
        clause_id += 1
        mark_consumed("max nodes per cluster (nas / san)", "cluster")

        # 4.2 Depolama Havuzu Yönetimi — [USER REVISION 1.17 STANDARDI - 800 SAYISI KALDIRILMIŞ]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Depolama Havuzu Yönetimi",
                text=(
                    "Sistem, fiziksel depolama kaynaklarının mantıksal olarak gruplanmasını ve bu kaynakların "
                    "merkezi olarak yönetilmesini sağlayan depolama havuzu yönetimini desteklemelidir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Centralized Storage Pool Management",
            )
        )
        clause_id += 1
        mark_consumed("aggregate")

        # 4.3 Mantıksal Birim ve LUN / Namespace Yönetimi
        lun_cnt = spec.limits_lun.strip() if spec.limits_lun and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_lun) else "128"
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Mantıksal Birim ve Blok Depolama Yönetimi",
                text=(
                    f"Sistem, uygulama ve servis ihtiyaçları için mantıksal depolama alanları oluşturabilmeli; "
                    f"blok depolama ortamları için mantıksal birim ve ad alanı oluşturulmasını desteklemeli, "
                    f"en az {lun_cnt} adet mantıksal birim (LUN) ve en az {lun_cnt} adet ad alanının (Namespace) "
                    f"yönetimine imkân vermelidir."
                ),
                is_mandatory=True,
                is_parametric=True,
                source_note=f"{spec.source_file}: LUN & Namespace limits",
            )
        )
        clause_id += 1
        mark_consumed("volume", "max volume count", "lun", "namespace", "subsystem")

        # 4.4 Geniş Ölçekli Dosya Alanları Desteği — [USER REVISION 1.19 STANDARDI - SAYISAL LİMİTLER KALDIRILMIŞ]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Geniş Ölçekli Dosya Alanları Desteği",
                text=(
                    "Sistem, yüksek kapasite ve ölçek gerektiren dosya iş yükleri için birden fazla fiziksel veya "
                    "mantıksal depolama kaynağının tek bir dosya alanı altında kullanılabilmesini ve bu yapının sistem "
                    "çalışması kesintiye uğratılmadan genişletilebilmesini desteklemelidir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Scale-Out Distributed File Namespace",
            )
        )
        clause_id += 1
        mark_consumed(
            "flexgroup volume",
            "flexgroup",
            "flexgroup constituent",
            "flexgroup/node",
            "max flexgroup data constituent size",
            "max infinite volume data constituent size",
        )

        # 4.5 Tutarlılık ve Erişim Grupları (Consistency Groups & igroups)
        cg_cnt = spec.limits_consistency_group.strip() if spec.limits_consistency_group and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_consistency_group) else "80"
        ig_cnt = spec.limits_igroup.strip() if spec.limits_igroup and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_igroup) else "4,096"
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Tutarlılık Grupları ve Erişim Yetkilendirmesi",
                text=(
                    f"Sistem, birden fazla mantıksal depolama alanı üzerinde uygulama tutarlılığını koruyacak şekilde "
                    f"en az {cg_cnt} adet tutarlılık grubunu (Consistency Group) desteklemeli; blok depolama erişimlerinin "
                    f"sunucu veya sunucu grubu bazında yetkilendirilmesi için en az {ig_cnt} adet erişim grubunun "
                    f"(igroup) tanımlanabilmesine imkân sağlamalıdır."
                ),
                is_mandatory=True,
                is_parametric=True,
                source_note=f"{spec.source_file}: Consistency Group and igroup limits",
            )
        )
        clause_id += 1
        mark_consumed(
            "consistency group",
            "child consistency group",
            "parent consistency group",
            "igroup",
            "portset",
            "port",
            "svm",
            "vserver",
            "nas svm",
            "node/svm",
        )

        # 4.6 Eşzamanlı Bağlantı Ölçeği — [USER REVISION 1.24 STANDARDI - 65.536 RAKAMI KALDIRILMIŞ]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Eşzamanlı Bağlantı Ölçeği",
                text=(
                    "Sistem, yoğun kurumsal iş yükleri için yüksek eşzamanlı bağlantı kapasitesine sahip olmalı; "
                    "performans kaybı yaşamadan kurumsal ölçekte eşzamanlı host ve istemci bağlantılarını desteklemelidir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Enterprise High Concurrent Connection Scalability",
            )
        )
        clause_id += 1
        mark_consumed("connection", "file", "node", "ha pair", "ha pair (non-scalable)", "origin", "bucket", "object store/storagevm", "bytes")

        # 4.7 Veri-at-Rest Şifreleme — [USER REVISION 1.25 STANDARDI - YAZILIM KISITI ESNETİLMİŞ]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.DATA_PROTECTION.value,
                title="Veri-at-Rest Şifreleme",
                text=(
                    "Teklif edilen sistem, depolanan verilerin yetkisiz erişime karşı şifrelenmesini sağlayan "
                    "veri-at-rest şifreleme özelliğini desteklemeli ve şifreleme farklı mantıksal depolama alanlarına "
                    "uygulanabilmelidir."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Data-at-Rest Encryption (Volume / Drive Level)",
            )
        )
        clause_id += 1
        mark_consumed("netapp volume encryption", "full disk encryption support")

        # 4.8 Güncel ve Desteklenen Sistem Yazılımı — [USER REVISION 1.26 STANDARDI - ONTAP PATCH SÜRÜMLERİ KALDIRILMIŞ]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.FIRMWARE_OS.value,
                title="Güncel ve Desteklenen Sistem Yazılımı",
                text=(
                    "Teklif edilen sistem, üretici tarafından aktif olarak desteklenen ve genel kullanıma sunulmuş "
                    "güncel sistem yazılımı ile teslim edilmelidir. Teklif edilen donanım ve sistem yazılımı "
                    "kombinasyonu üretici tarafından desteklenen bir yapılandırma olmalıdır."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Actively Supported Current Enterprise OS",
            )
        )
        clause_id += 1
        mark_consumed("minimum os", "maximum os", "recommended version", "min root volume size", "bios", "bmc")

        # 4.9 Thin Provisioning ve Alan Verimli Kopyalama (Snapshot & Klonlama) — [GOLD-STANDARD SPEC]
        snap_cnt = spec.limits_snapshot.strip() if spec.limits_snapshot and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_snapshot) else "255"
        c_snap_text = (
            f"Teklif edilen veri depolama sistemi 'Thin Provisioning' özelliğini destekleyecektir. "
            f"Sistem, mantıksal depolama alanları için alan verimli anlık kopya (Snapshot) alma ve yönetme yeteneğine "
            f"sahip olmalı; her bir mantıksal alan için en az {snap_cnt} adet anlık kopyayı desteklemeli, "
            f"alınan snapshot üzerinden geri dönülmesini ve anlık klon (clone) almayı desteklemelidir. "
            f"Bu iş için gerekli olan yazılımlar ve lisanslar desteklenen en yüksek kapasitede olacak şekilde "
            f"yüklenici firma tarafından sağlanacaktır."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.DATA_PROTECTION.value,
                title="Thin Provisioning ve Snapshot/Klon Yetenekleri",
                text=c_snap_text,
                is_parametric=True,
                source_note="Kurumsal İhale Standardı: Thin Provisioning, Snapshot & Clone Suite",
            )
        )
        clause_id += 1
        mark_consumed("snapshot")

        # 4.10 E-Serisi Özellikleri (Varsa DDP, T10-PI, SSD Disk Havuzu)
        if spec.ddp_support or spec.t10_pi_support or spec.ssd_in_disk_pool_support:
            ddp_items = []
            if spec.ddp_support:
                ddp_items.append("disk arızalarında dinamik ve hızlı veri kurtarma sağlayan Dinamik Disk Havuzları (DDP - Dynamic Disk Pools)")
                mark_consumed("ddp support")
            if spec.t10_pi_support:
                ddp_items.append("uçtan uca sessiz veri bozulmasını engelleyen T10-PI Veri Güvencesi (Data Assurance)")
                mark_consumed("data assurance (t10 pi) support")
            if spec.ssd_in_disk_pool_support:
                ddp_items.append("Dinamik Disk Havuzlarında SSD sürücü kullanım desteği")
                mark_consumed("ssd support in a disk pool")
            c14_text = f"Teklif edilen veri depolama sistemi; {', '.join(ddp_items)} teknolojilerini tam olarak destekleyecektir."
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.DATA_PROTECTION.value,
                    title="DDP ve Veri Güvencesi Teknolojileri",
                    text=c14_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: DDP Support, Data Assurance (T10 PI) Support",
                )
            )
            clause_id += 1
            mark_consumed(
                "max disk pool volumes",
                "max disk pools",
                "max drives per disk pool",
                "max vol size for a disk pool volume (tb)",
                "max partitions",
                "max volumes per partition",
                "flash read cache (gb) (min/max)",
                "max destaging cache-to- flash size (gb)",
                "full storage limit matrix",
                "pci interface",
                "oob management port interface (per controller)",
            )

        # 4.11 Merkezi Yönetim ve SNMP Desteği — [GOLD-STANDARD SPEC]
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.SOFTWARE_LIMITS.value,
                title="Merkezi Yönetim ve SNMP Desteği",
                text=(
                    "Teklif edilen veri depolama sisteminin merkezi web tabanlı yönetim arayüzü ve kurumsal izleme "
                    "sistemlerine entegrasyon için SNMP (Simple Network Management Protocol) desteği olacaktır."
                ),
                is_mandatory=True,
                is_parametric=False,
                source_note="Kurumsal İhale Standardı: Central Management and SNMP Support",
            )
        )
        clause_id += 1

        # =====================================================================
        # BÖLÜM 5: GARANTİ VE DESTEK STANDARDI
        # =====================================================================
        warranty_words = self.num_to_words(request.warranty_years)
        c_warr_text = (
            f"Teklif edilen veri depolama sistemine ait tüm donanım ve yazılımlar en az {request.warranty_years} "
            f"({warranty_words}) yıl boyunca üretici firma garantisi altında olacaktır. {request.support_type} "
            f"destek hizmeti üretici firma veya yetkili servis iş ortağı tarafından sağlanacaktır."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category="Garanti ve Destek",
                title="Üretici Garantisi ve Destek Süresi",
                text=c_warr_text,
                is_parametric=True,
                source_note="Kurumsal İhale Standardı: 5 Yıl Üretici Garantisi ve SLA",
            )
        )
        clause_id += 1

        # =====================================================================
        # BÖLÜM 6: TÜM DİNAMİK FALLBACK MOTORU (YENİ VE FARKLI ÜRETİCİ TABLOLARI İÇİN)
        # =====================================================================
        # Kara listeye alınan iç yazılım mimarisi, çevresel ve idari kolonlar
        ignored_internal_keys = {
            "model",
            "release date",
            "end of support (eos)",
            "1",
            "acl (access list)",
            "high priority controller",
            "high priority queue",
            "regular priority controller",
            "regular priority queue",
            "intercluster lif",
            "min root volume size",
            "minimum os",
            "maximum os",
            "recommended version",
            "operating temperature range",
            "operating relative humidity",
            "storage relative humidity",
            "transit relative humidity",
            "operating altitude range",
            "storage altitude range",
            "transit altitude range",
            "transit temperature range",
            "storage temperature range",
            "acoustic noise - sound power",
            "acoustic noise - sound pressure",
            "front clearance (cooling)",
            "front clearance (maintenance)",
            "rear clearance (cooling)",
            "rear clearance (maintenance)",
            "chassis height",
            "chassis width with mounting flanges",
            "chassis width without mounting flanges",
            "chassis width",
            "chassis depth with cable mgmt",
            "chassis depth without cable mgmt",
            "weight",
            "weight (max)",
            "weight (min)",
            "bios",
            "bmc",
            "input power voltage",
            "power supply",
            "certifications emc/emi",
            "certifications safety",
            "certifications safety/emc/emi/rohs",
            "certifications safety/emc/emi",
            "standards emc/emi",
            "standards safety",
            "aggregate", "bucket", "bytes", "cluster", "connection",
            "flexgroup", "flexgroup constituent", "flexgroup volume", "flexgroup/node",
            "ha pair", "ha pair (non-scalable)", "max fabricpool size",
            "max flexgroup data constituent size", "max infinite volume data constituent size",
            "netapp volume encryption", "node", "node/svm", "object store/storagevm",
            "origin", "svm", "volume", "vserver", "file", "subsystem", "port",
            "max disk pool volumes", "max disk pools", "max drives per disk pool",
            "max vol size for a disk pool volume (tb)", "max partitions", "max volumes per partition",
            "flash read cache (gb) (min/max)", "max destaging cache-to- flash size (gb)",
            "full storage limit matrix", "pci interface", "oob management port interface (per controller)",
        }

        for raw_col, val in raw_attrs.items():
            col_key = raw_col.lower().strip()
            if col_key in consumed_columns or col_key in ignored_internal_keys:
                continue
            if any(term in col_key for term in ["clearance", "certifications", "standards", "altitude"]):
                continue
            if val is None or UnitAndMultiplierParser.is_boolean_negative(val):
                continue

            # Kolonu semantik olarak analiz et
            category = SemanticClassifier.classify(raw_col)
            val_str = str(val).strip()

            if UnitAndMultiplierParser.is_boolean_positive(val):
                fallback_text = (
                    f"Teklif edilen veri depolama sistemi üzerinde yer alan '{raw_col}' "
                    f"özelliği ve standardı donanım/yazılım kapsamında eksiksiz olarak desteklenecektir."
                )
            else:
                clean_val = self.clean_text(val_str)
                fallback_text = (
                    f"Teklif edilen veri depolama sistemi kurumsal teknik gereksinimler kapsamında "
                    f"'{raw_col}' parametresini en az {clean_val} değerinde/standardında kesintisiz sağlayacaktır."
                )

            clauses.append(
                Clause(
                    id=clause_id,
                    category=category.value,
                    title=f"{raw_col} Standardı",
                    text=fallback_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Dinamik Kolon Eşlemesi ({raw_col})",
                )
            )
            clause_id += 1
            consumed_columns.add(col_key)

        # Jenerik Mod filtrelemesi (İstenmişse marka/model isimlerini temizle)
        if request.flexibility == "jenerik":
            for c in clauses:
                c.text = scrub_brand_and_model(c.text, request.brand, spec.model_name)

        return clauses
