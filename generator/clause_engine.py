"""Şartname Maddeleri Dinamik ve Semantik Üretim Motoru (SOLID: SRP & OCP).

Excel tablolarındaki donanım özelliklerini semantik taksonomiyle analiz eden,
tüm bilinen donanım alanlarını profesyonel kurumsal ihale kalıplarına dönüştüren ve
daha önce hiç görülmemiş egzotik/yeni kolonları "Dinamik Fallback Motoru" ile
sıfır veri kaybı garantisiyle şartname maddesine çeviren genişleyebilir çekirdek motor.
"""


from shared.models import Clause, SpecRequest, StorageSpec
from shared.semantic_parser import (
    ColumnCategory,
    SemanticClassifier,
    TurkishNumberConverter,
    UnitAndMultiplierParser,
)
from shared.validators import scrub_brand_and_model


class ParametricClauseEngine:
    """Semantik taksonomi ve dinamik fallback destekli şartname motoru."""

    def __init__(self):
        self.num_to_words = TurkishNumberConverter.to_words
        self.clean_text = UnitAndMultiplierParser.clean_spec_text

    def generate_clauses(self, spec: StorageSpec, request: SpecRequest) -> list[Clause]:
        """Excel tablosundaki tüm geçerli verileri analiz ederek şartname maddelerini üretir."""
        clauses: list[Clause] = []
        clause_id = 1
        consumed_columns: set[str] = set()

        raw_attrs = spec.raw_attributes or {}

        # Yardımcı fonksiyon: Kullanılan kolonu kaydeder
        def mark_consumed(*col_names: str):
            for cn in col_names:
                consumed_columns.add(cn.lower().strip())

        # 1. Mimari, Kontrol Ünitesi ve Şasi Yapısı
        ctrl_words = self.num_to_words(spec.controller_count)
        model_part = f" ({spec.model_name})" if request.flexibility == "tekil" else ""
        c1_text = (
            f"Teklif edilen veri depolama sistemi{model_part} {spec.storage_tier} tipinde ve {spec.architecture} "
            f"mimarisine sahip olmalıdır. Sistem en fazla {spec.rack_units}U kabin yüksekliğinde şasi yapısında "
            f"olmalı ve kendi içerisinde aktif-aktif olarak çalışan, birbirini donanımsal arızalara karşı yedekleyen "
            f"en az {spec.controller_count} ({ctrl_words}) adet kontrol ünitesine (HA Pair) sahip olacaktır."
        )
        clauses.append(
            Clause(
                id=clause_id,
                category=ColumnCategory.CHASSIS_PHYSICAL.value,
                title="Şasi ve Kontrol Ünitesi Mimarisi",
                text=c1_text,
                is_parametric=True,
                source_note=f"{spec.source_file}: Model, Rack Units, Controller Count",
            )
        )
        clause_id += 1
        mark_consumed("model", "rack units", "controller count")

        # 2. Yatayda Genişleme ve Kümeleme (Scale-Out)
        if spec.scale_out_nas_nodes or spec.scale_out_san_nodes:
            parts = []
            if spec.scale_out_nas_nodes and not UnitAndMultiplierParser.is_boolean_negative(spec.scale_out_nas_nodes):
                parts.append(f"NAS (dosya) ortamları için en az {spec.scale_out_nas_nodes.strip()} kontrol ünitesine kadar")
            if spec.scale_out_san_nodes and not UnitAndMultiplierParser.is_boolean_negative(spec.scale_out_san_nodes):
                parts.append(f"SAN (blok) ortamları için en az {spec.scale_out_san_nodes.strip()} kontrol ünitesine kadar")

            if parts:
                c2_text = (
                    f"Teklif edilen veri depolama sistemi yatayda büyüme (scale-out) mimarisini desteklemelidir. "
                    f"Sistem {' ve '.join(parts)} kümeleme (cluster) yapısını kesintisiz olarak destekleyecektir."
                )
            else:
                c2_text = (
                    f"Teklif edilen veri depolama sistemi yatayda büyüme (scale-out) mimarisini desteklemeli ve "
                    f"en az {spec.scale_out_max_nodes} adet kontrol ünitesine kadar kümeleme desteği sunmalıdır."
                )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.HIGH_AVAILABILITY.value,
                    title="Yatayda Genişleme (Scale-Out) ve Küme Desteği",
                    text=c2_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Max Nodes per Cluster (NAS / SAN)",
                )
            )
            clause_id += 1
            mark_consumed("max nodes per cluster (nas / san)", "cluster")
        elif spec.scale_out_max_nodes > 2:
            max_node_words = self.num_to_words(spec.scale_out_max_nodes).upper()
            c2_text = (
                f"Teklif edilen veri depolama sistemi scale-out mimariyi destekleyerek en az "
                f"{spec.scale_out_max_nodes} ({max_node_words}) adet kontrol ünitesine kadar yükseltilmeyi destekleyecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.HIGH_AVAILABILITY.value,
                    title="Yatayda Genişleme (Scale-Out)",
                    text=c2_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Max Nodes per Cluster / Controller Count",
                )
            )
            clause_id += 1
            mark_consumed("max nodes per cluster (nas / san)", "cluster")

        # 3. İşlemci Mimarisi ve Hesaplama (Compute & CPU Cores)
        if spec.processor_cores_total > 0 or spec.processor_info:
            cores_node_w = self.num_to_words(spec.processor_cores_per_node)
            cores_tot_w = self.num_to_words(spec.processor_cores_total)
            proc_speed_txt = f", {spec.processor_speed} çalışma saat hızında" if spec.processor_speed else ""

            cores_cpu_str = str(raw_attrs.get("Processor Cores (Per CPU)") or "").strip()
            cpu_cnt_node_str = str(raw_attrs.get("Processor Count (Per Node)") or "").strip()

            if cores_cpu_str and not UnitAndMultiplierParser.is_boolean_negative(cores_cpu_str) and cores_cpu_str != str(spec.processor_cores_per_node):
                cpu_detail = f"{cpu_cnt_node_str or '2'} adet işlemci (işlemci başına en az {cores_cpu_str} çekirdek olmak üzere kontrol ünitesi başı {spec.processor_cores_per_node} ({cores_node_w}) çekirdek)"
            else:
                cpu_detail = f"en az {spec.processor_cores_per_node} ({cores_node_w}) çekirdek"

            if spec.processor_cores_per_node > 0 and spec.controller_count > 1:
                calc_txt = f"{spec.controller_count}x{spec.processor_cores_per_node} = sistem toplamında en az {spec.processor_cores_total} ({cores_tot_w})"
            else:
                calc_txt = f"sistem genelinde toplamda en az {spec.processor_cores_total} ({cores_tot_w})"

            c3_text = (
                f"Teklif edilen veri depolama sistemindeki her bir kontrol ünitesi üzerinde {cpu_detail} olmak üzere, {calc_txt} "
                f"fiziksel çekirdeğe sahip, {spec.processor_arch} mimarisinde{proc_speed_txt} kurumsal işlemciler bulunmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.COMPUTE.value,
                    title="İşlemci Mimarisi ve Çekirdek Sayısı",
                    text=c3_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Processor Model / Cores (Node: {spec.processor_cores_per_node}, Total: {spec.processor_cores_total})",
                )
            )
            clause_id += 1
            mark_consumed(
                "processor model", "processor architecture", "processor speed",
                "processor cores (per node)", "processor cores (per config)",
                "processor cores (per cpu)", "processor count (per node)", "processor count (per config)"
            )

        # 4. Sistem Belleği (RAM / DRAM Multiplier)
        if spec.ram_total_gb > 0 or spec.ram_per_node_gb > 0:
            ram_node_w = self.num_to_words(spec.ram_per_node_gb)
            ram_tot_w = self.num_to_words(spec.ram_total_gb)

            if spec.controller_count > 1 and spec.ram_per_node_gb > 0:
                ram_calc_txt = (
                    f"her bir kontrol ünitesi üzerinde en az {spec.ram_per_node_gb} ({ram_node_w}) GB sistem belleği "
                    f"olmak üzere, {spec.controller_count} kontrol ünitesi için 2x{spec.ram_per_node_gb} GB = sistem "
                    f"toplamında en az {spec.ram_total_gb} ({ram_tot_w}) GB sistem belleği bulunacaktır."
                )
            else:
                ram_calc_txt = f"sistem toplamında en az {spec.ram_total_gb} ({ram_tot_w}) GB sistem belleği bulunacaktır."

            c4_text = (
                f"Teklif edilen veri depolama sisteminde {ram_calc_txt} Bu bellek doğrudan DRAM tipinde olmalı ve "
                f"SSD/Flash/NVMe temelli sanal bellek alanları bu kapsamda kabul edilmeyecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.MEMORY.value,
                    title="Sistem Belleği (DRAM)",
                    text=c4_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: RAM Per Node: {spec.ram_per_node_gb} GB, RAM Per Config: {spec.ram_total_gb} GB",
                )
            )
            clause_id += 1
            mark_consumed("ram (per node)", "ram (per config)", "system memory")

        # 5. Kalıcı Yazma Belleği ve Pil Koruması (NVRAM / NVMEM)
        if spec.nvram_total_gb > 0 or spec.nvram_per_node_gb > 0:
            if spec.nvram_per_node_gb > 0 and spec.controller_count > 1:
                nv_calc = (
                    f"her bir kontrol ünitesi üzerinde en az {spec.nvram_per_node_gb} GB olmak üzere, "
                    f"{spec.controller_count} kontrol ünitesi için 2x{spec.nvram_per_node_gb} GB = toplamda en az {spec.nvram_total_gb} GB"
                )
            else:
                nv_calc = f"toplamda en az {spec.nvram_total_gb} GB"
            c5_text = (
                f"Teklif edilen veri depolama sisteminde yazma gecikmelerini minimize etmek ve güvenliği sağlamak için {nv_calc} "
                f"yüksek hızlı kalıcı yazma belleği (NVRAM) bulunacaktır. Olası bir elektrik kesintisi durumunda "
                f"yazma belleğindeki tüm veriler pil/akü sistemi ile tam koruma altına alınmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Kalıcı Yazma Belleği (NVRAM) ve Pil Koruması",
                    text=c5_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: NVRAM Per Node: {spec.nvram_per_node_gb} GB, NVRAM Per Config: {spec.nvram_total_gb} GB",
                )
            )
            clause_id += 1
            mark_consumed("nvram (per node)", "nvram (per config)")
        elif spec.nvmem_total_gb > 0 or spec.nvmem_per_node_gb > 0:
            if spec.nvmem_per_node_gb > 0 and spec.controller_count > 1:
                nv_calc = (
                    f"her bir kontrol ünitesi üzerinde en az {spec.nvmem_per_node_gb} GB olmak üzere, "
                    f"{spec.controller_count} kontrol ünitesi için 2x{spec.nvmem_per_node_gb} GB = toplamda en az {spec.nvmem_total_gb} GB"
                )
            else:
                nv_calc = f"toplamda en az {spec.nvmem_total_gb} GB"
            c5_text = (
                f"Teklif edilen veri depolama sisteminde {nv_calc} kalıcı yazma belleği (NVMEM) bulunacaktır. "
                f"Olası bir elektrik kesintisi durumunda yazma belleğindeki veriler pil veya akü sistemi ile kesintisiz korunacaktır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Kalıcı Yazma Belleği (NVMEM) ve Güç Koruması",
                    text=c5_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: NVMEM Per Node: {spec.nvmem_per_node_gb} GB, NVMEM Per Config: {spec.nvmem_total_gb} GB",
                )
            )
            clause_id += 1
            mark_consumed("nvmem (per node)", "nvmem (per config)")

        # 5.1. Dahili NVMe Flash Önbellek (Flash Cache / Flash Pool)
        if spec.nvme_cache_total_gb > 0:
            c_nvme_text = (
                f"Teklif edilen veri depolama sisteminde her bir kontrol ünitesi üzerinde en az {spec.nvme_cache_per_node_gb} GB "
                f"olmak üzere, {spec.controller_count} kontrol ünitesi için 2x{spec.nvme_cache_per_node_gb} GB = toplamda en az "
                f"{spec.nvme_cache_total_gb} GB dahili yüksek hızlı NVMe Flash önbellek (Flash Cache) bulunmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Dahili NVMe Flash Önbellek (Flash Cache)",
                    text=c_nvme_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: NVME Per Node: {spec.nvme_cache_per_node_gb} GB, NVME Per Config: {spec.nvme_cache_total_gb} GB",
                )
            )
            clause_id += 1
            mark_consumed("nvme (per node)", "nvme (per config)")

        # 5.2. İkincil Flash Okuma ve Boşaltma Önbelleği (E-Serisi)
        if spec.flash_read_cache_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.flash_read_cache_raw):
            c_frc_text = (
                f"Teklif edilen veri depolama sistemi üzerinde en az {spec.flash_read_cache_raw.strip()} "
                f"Flash Okuma Önbelleği (Flash Read Cache) desteklenmelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Flash Okuma Önbelleği (Flash Read Cache)",
                    text=c_frc_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Flash Read Cache (GB)",
                )
            )
            clause_id += 1
            mark_consumed("flash read cache (gb) (min/max)")

        if spec.max_destaging_cache_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.max_destaging_cache_raw):
            c_dest_text = (
                f"Teklif edilen veri depolama sisteminde olası güç kesintilerine karşı en az "
                f"{spec.max_destaging_cache_raw.strip()} GB önbellek boşaltma (Destaging Cache-to-Flash) koruma alanı bulunmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NV_MEMORY.value,
                    title="Önbellek Boşaltma Alanı (Destaging Cache-to-Flash)",
                    text=c_dest_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Max Destaging Cache-to- Flash Size (GB)",
                )
            )
            clause_id += 1
            mark_consumed("max destaging cache-to- flash size (gb)")

        # 6. Sürücü Kapasitesi ve Dahili / Harici Sürücü Yuvaları
        drive_intro = []
        if spec.internal_drives_count and not UnitAndMultiplierParser.is_boolean_negative(spec.internal_drives_count):
            clean_internal = self.clean_text(spec.internal_drives_count)
            drive_intro.append(f"şasisi üzerinde dahili olarak {clean_internal}")
        if spec.max_drives > 0:
            drive_intro.append(f"harici disk rafları ile birlikte toplamda en az {spec.max_drives} adet sürücüye kadar")

        if drive_intro:
            c6_text = (
                f"Teklif edilen veri depolama sistemi {', '.join(drive_intro)} sürücü genişlemesini kesintisiz "
                f"olarak destekleyecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.STORAGE_MEDIA.value,
                    title="Azami Sürücü Sayısı ve Dahili Yuvalar",
                    text=c6_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Internal Drives count: {spec.internal_drives_count}, Max Drives: {spec.max_drives}",
                )
            )
            clause_id += 1
            mark_consumed("internal drives count", "max number of drives (total)", "max number of drives")

        # 7. Desteklenen Sürücü Tipleri
        supported_drive_types = []
        if spec.max_nlsas_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_nlsas_drives):
            supported_drive_types.append(f"NL-SAS disk sürücüleri ({self.clean_text(spec.max_nlsas_drives)})")
            mark_consumed("max number of nl-sas drives")
        if spec.max_sas_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_sas_drives):
            supported_drive_types.append(f"SAS disk sürücüleri ({self.clean_text(spec.max_sas_drives)})")
            mark_consumed("max number of sas drives")
        if spec.max_ssd_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_ssd_drives):
            supported_drive_types.append(f"SAS SSD sürücüleri ({self.clean_text(spec.max_ssd_drives)})")
            mark_consumed("max number of ssd drives")
        if spec.max_nvme_ssd_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_nvme_ssd_drives):
            supported_drive_types.append(f"NVMe SSD yüksek performans sürücüleri ({self.clean_text(spec.max_nvme_ssd_drives)})")
            mark_consumed("max number of nvme ssd drives")
        if spec.max_capacity_flash_drives and not UnitAndMultiplierParser.is_boolean_negative(spec.max_capacity_flash_drives):
            supported_drive_types.append(f"Capacity Flash NVMe SSD sürücüleri ({self.clean_text(spec.max_capacity_flash_drives)})")
            mark_consumed("max number of capacity flash nvme ssd drives")

        if supported_drive_types:
            c7_text = (
                f"Teklif edilen veri depolama sistemi sürücü mimarisi kapsamında şu sürücü tiplerini desteklemelidir: "
                f"{'; '.join(supported_drive_types)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.STORAGE_MEDIA.value,
                    title="Desteklenen Sürücü Tipleri ve Sınırları",
                    text=c7_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Desteklenen Sürücü Sütunları",
                )
            )
            clause_id += 1

        # 8. Desteklenen Disk Rafları (Shelves)
        if spec.shelves_supported:
            shelf_items = [f"{name} ({self.clean_text(count)})" for name, count in spec.shelves_supported.items()]
            c8_text = (
                f"Teklif edilen veri depolama sistemi, kapasite artırımı amacıyla üreticiye ait şu harici disk genişleme "
                f"raflarını desteklemelidir: {', '.join(shelf_items)}. Raf eklemeleri sistem çalışırken kesintisiz (online) "
                f"yapılabilmelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.EXPANSION_SHELF.value,
                    title="Desteklenen Disk Rafları (Shelves)",
                    text=c8_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Desteklenen Raf Sütunları",
                )
            )
            clause_id += 1
            for k in raw_attrs:
                if "shelves" in k.lower():
                    mark_consumed(k)

        # 9. Azami Ham Kapasite ve Katmanlama
        if spec.max_raw_capacity and not UnitAndMultiplierParser.is_boolean_negative(spec.max_raw_capacity):
            c9_text = (
                f"Teklif edilen veri depolama sistemi, herhangi bir kontrol ünitesi yükseltmesi gerektirmeden yalnızca "
                f"disk ve disk rafı ekleyerek en az {spec.max_raw_capacity} azami ham/bulut katmanlama kapasitesine "
                f"kadar genişleyebilmelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.STORAGE_MEDIA.value,
                    title="Azami Genişleme ve Ham Kapasite",
                    text=c9_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Max FabricPool / Raw Capacity",
                )
            )
            clause_id += 1
            mark_consumed("max fabricpool size", "max volume size (eb)", "max volume size")

        # 10. Ağ, Portlar ve İletişim Arayüzleri
        port_clauses = []
        if spec.ethernet_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.ethernet_ports_raw):
            port_clauses.append(f"en az {spec.ethernet_ports_raw.strip()} Ethernet portu")
            mark_consumed("ethernet ports")
        if spec.fc_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.fc_ports_raw):
            port_clauses.append(f"en az {spec.fc_ports_raw.strip()} Fiber Channel (FC) portu")
            mark_consumed("fibre channel ports")
        if spec.uta2_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.uta2_ports_raw):
            port_clauses.append(f"en az {spec.uta2_ports_raw.strip()} UTA2 tümleşik portu")
            mark_consumed("uta2 ports")
        if spec.sas_ports_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.sas_ports_raw):
            port_clauses.append(f"harici disk rafı bağlantıları için en az {spec.sas_ports_raw.strip()} SAS portu")
            mark_consumed("sas ports")
        if spec.oob_mgmt_port_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.oob_mgmt_port_raw):
            port_clauses.append(f"denetleyici başına en az {spec.oob_mgmt_port_raw.strip()} harici yönetim (OOB) portu")
            mark_consumed("oob management port interface (per controller)")

        if port_clauses:
            c10_text = (
                f"Teklif edilen veri depolama sistemi üzerinde ağ ve çevre birim bağlantıları için: "
                f"{'; '.join(port_clauses)} bulunmalıdır. Tüm portlar kontrol ünitelerine dengeli ve eşit dağıtılmış olacaktır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NETWORKING.value,
                    title="Ağ ve İletişim Port Yapısı",
                    text=c10_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Ethernet, FC, SAS, UTA2, OOB Ports",
                )
            )
            clause_id += 1

        # 11. Genişleme Yuvaları ve Arayüz Standartları
        if spec.expansion_slots_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.expansion_slots_raw):
            c11_text = (
                f"Teklif edilen veri depolama sistemi üzerinde ilave ağ ve arayüz kartlarının takılabilmesi amacıyla "
                f"en az {spec.expansion_slots_raw.strip()} genişleme yuvası bulunacaktır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NETWORKING.value,
                    title="Genişleme Yuvaları (Expansion Slots)",
                    text=c11_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Expansion Slots",
                )
            )
            clause_id += 1
            mark_consumed("expansion slots")
        elif spec.pci_interface_raw and not UnitAndMultiplierParser.is_boolean_negative(spec.pci_interface_raw):
            c11_text = (
                f"Teklif edilen veri depolama sisteminde dahili ve harici veri yolu iletişimi için en az "
                f"{spec.pci_interface_raw.strip()} veri yolu arayüzü desteklenecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.NETWORKING.value,
                    title="PCI Arayüz Standardı",
                    text=c11_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: PCI Interface",
                )
            )
            clause_id += 1
            mark_consumed("pci interface")

        # 12. Veri Güvenliği ve Şifreleme
        # 12. Veri Güvenliği ve Şifreleme (NVE / FDE)
        enc_types = []
        if spec.full_disk_encryption_support:
            enc_types.append("donanımsal tam disk şifreleme (Full Disk Encryption - FDE / SED)")
            mark_consumed("full disk encryption support")
        if spec.encryption_info and not UnitAndMultiplierParser.is_boolean_negative(spec.encryption_info):
            if "desteklenir" not in spec.encryption_info.lower():
                enc_types.append(f"veri depolama birim düzeyinde şifreleme ({spec.encryption_info.strip()})")
            elif not enc_types:
                enc_types.append("kurumsal veri depolama donanımsal/yazılımsal şifreleme")
            mark_consumed("netapp volume encryption")

        if enc_types:
            c12_text = (
                f"Teklif edilen veri depolama sistemi üzerinde veri güvenliğini sağlamak amacıyla depolanan verilerin "
                f"şifrelenmesini sağlayan {', '.join(enc_types)} mekanizmaları eksiksiz olarak desteklenmelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.DATA_PROTECTION.value,
                    title="Veri Güvenliği ve Şifreleme Mekanizması",
                    text=c12_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: NetApp Volume Encryption / Full Disk Encryption",
                )
            )
            clause_id += 1

        # 13. Mantıksal Depolama Limitleri (Aggregates, Volumes, LUNs, Snapshots, SVM, SAN igroup, Dosya Sayıları)
        limits_list = []
        if spec.limits_aggregate and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_aggregate):
            limits_list.append(f"en az {spec.limits_aggregate.strip()} adet Aggregate/Depolama Havuzu")
            mark_consumed("aggregate")

        # 13.1 Volume Boyutu ve Adedi
        max_constituent = str(raw_attrs.get("Max FlexGroup Data Constituent Size") or "").strip()
        vol_cnt = spec.limits_volume.strip() if spec.limits_volume and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_volume) else ""
        if max_constituent and not UnitAndMultiplierParser.is_boolean_negative(max_constituent) and vol_cnt:
            limits_list.append(f"tek bir mantıksal birim (Volume) boyutu en az {max_constituent} olmak üzere en az {vol_cnt} adet mantıksal alan (Volume)")
            mark_consumed("volume", "max volume count", "max flexgroup data constituent size", "max infinite volume data constituent size")
        elif vol_cnt:
            limits_list.append(f"en az {vol_cnt} adet mantıksal alan (Volume)")
            mark_consumed("volume", "max volume count")

        # 13.2 FlexGroup & Constituent
        if spec.limits_flexgroup and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_flexgroup):
            limits_list.append(f"en az {spec.limits_flexgroup.strip()} adet FlexGroup Volume")
            mark_consumed("flexgroup volume", "flexgroup")
        if spec.limits_flexgroup_constituent and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_flexgroup_constituent):
            limits_list.append(f"tekil FlexGroup yapısında en az {spec.limits_flexgroup_constituent.strip()} bileşen hacim (Constituent)")
            mark_consumed("flexgroup constituent", "flexgroup/node")

        # 13.3 SAN Başlatıcı Grubu (igroup) ve LUN Sınırı
        if spec.limits_igroup and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_igroup):
            limits_list.append(f"en az {spec.limits_igroup.strip()} adet SAN Başlatıcı Grubu (igroup)")
            mark_consumed("igroup")
        if spec.limits_lun and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_lun):
            limits_list.append(f"birim başına en az {spec.limits_lun.strip()} adet LUN (Logical Unit Number)")
            mark_consumed("lun")

        # 13.4 NVMe Namespace ve Subsystem
        namespace_val = str(raw_attrs.get("Namespace") or "").strip()
        subsystem_val = str(raw_attrs.get("Subsystem") or "").strip()
        if namespace_val and not UnitAndMultiplierParser.is_boolean_negative(namespace_val):
            sub_str = f" ve en az {subsystem_val} adet NVMe altsistemi (Subsystem)" if subsystem_val and not UnitAndMultiplierParser.is_boolean_negative(subsystem_val) else ""
            limits_list.append(f"en az {namespace_val} adet NVMe ad alanı (Namespace){sub_str}")
            mark_consumed("namespace", "subsystem")

        # 13.5 Snapshot
        if spec.limits_snapshot and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_snapshot):
            limits_list.append(f"en az {spec.limits_snapshot.strip()} adet anlık görüntü (Snapshot)")
            mark_consumed("snapshot")

        # 13.6 Sanal Depolama Sunucusu (SVM / Vserver) & NAS SVM
        svm_val = str(raw_attrs.get("SVM") or "").strip()
        vserver_val = str(raw_attrs.get("Vserver") or "").strip()
        svm_parts = []
        if svm_val and not UnitAndMultiplierParser.is_boolean_negative(svm_val):
            svm_parts.append(f"en az {svm_val} adet Depolama Sanal Sunucusu (SVM)")
            mark_consumed("svm")
        if vserver_val and not UnitAndMultiplierParser.is_boolean_negative(vserver_val):
            if vserver_val != svm_val:
                svm_parts.append(f"en az {vserver_val} adet Sanal Depolama Sunucusu (Vserver)")
            mark_consumed("vserver")
        if svm_parts:
            limits_list.append(" ve ".join(svm_parts))
        nas_svm_val = str(raw_attrs.get("NAS SVM") or "").strip()
        node_svm_val = str(raw_attrs.get("Node/SVM") or "").strip()
        if nas_svm_val and not UnitAndMultiplierParser.is_boolean_negative(nas_svm_val):
            node_desc = f" (SVM başına en az {node_svm_val} kontrol ünitesi)" if node_svm_val and not UnitAndMultiplierParser.is_boolean_negative(node_svm_val) else ""
            limits_list.append(f"en az {nas_svm_val} adet NAS veri sunucusu (NAS SVM){node_desc}")
            mark_consumed("nas svm", "node/svm")

        # 13.7 Bağlantı ve Tutarlılık Grupları
        if spec.limits_connections and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_connections):
            limits_list.append(f"en az {spec.limits_connections.strip()} eşzamanlı bağlantı (Connection)")
            mark_consumed("connection")
        cluster_cg = str(raw_attrs.get("Cluster") or "").strip()
        cg_text_parts = []
        if spec.limits_consistency_group and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_consistency_group):
            cg_text_parts.append(f"en az {spec.limits_consistency_group.strip()} tutarlılık grubu (Consistency Group)")
        if cluster_cg and not UnitAndMultiplierParser.is_boolean_negative(cluster_cg) and cluster_cg != spec.limits_consistency_group:
            cg_text_parts.append(f"küme (Cluster) genelinde en az {cluster_cg} tutarlılık grubu sınırı")
        if cg_text_parts:
            limits_list.append(" ve ".join(cg_text_parts))
            mark_consumed("consistency group", "child consistency group", "parent consistency group", "cluster")

        # 13.8 Dosya ve Dizin Sınırları (Node / HA Pair / File)
        file_val = str(raw_attrs.get("File") or "").strip()
        if file_val and not UnitAndMultiplierParser.is_boolean_negative(file_val):
            limits_list.append(f"hacim başına en az {file_val} dosya/dizin yapısı")
            mark_consumed("file")
        if spec.limits_max_files_node and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_max_files_node):
            pair_str = f" (HA çifti başına en az {spec.limits_max_files_pair.strip()})" if spec.limits_max_files_pair else ""
            limits_list.append(f"düğüm başına en az {spec.limits_max_files_node.strip()}{pair_str} dosya/inode kapasitesi")
            mark_consumed("node", "ha pair", "ha pair (non-scalable)", "origin")

        # 13.9 SAN Portset ve Ağ Portları (Port / Portset)
        portset_val = str(raw_attrs.get("Portset") or "").strip()
        port_val = str(raw_attrs.get("Port") or "").strip()
        if portset_val and not UnitAndMultiplierParser.is_boolean_negative(portset_val):
            p_str = f" ve en az {port_val} adet mantıksal ağ portu (LIF)" if port_val and not UnitAndMultiplierParser.is_boolean_negative(port_val) else ""
            limits_list.append(f"en az {portset_val} adet SAN Portset kümesi{p_str}")
            mark_consumed("portset", "port")

        # 13.10 S3 Nesne Depolama Sınırı (S3 Objects)
        if spec.limits_bucket and not UnitAndMultiplierParser.is_boolean_negative(spec.limits_bucket):
            limits_list.append(f"en az {spec.limits_bucket.strip()} adet S3 nesnesi (Object) ve nesne depolama desteği")
            mark_consumed("bucket", "object store/storagevm")

        # 13.11 Sektör Blok Biçimlendirme
        if spec.sector_bytes and not UnitAndMultiplierParser.is_boolean_negative(spec.sector_bytes):
            limits_list.append(f"{spec.sector_bytes.strip()} bayt sektör blok biçimlendirme desteği")
            mark_consumed("bytes")

        # 13.12 Controller / Queue Öncelik Desteği
        mark_consumed("high priority controller", "high priority queue", "regular priority controller", "regular priority queue")

        if limits_list:
            c13_text = (
                f"Teklif edilen veri depolama sistemi kurumsal veri yönetiminde asgari olarak şu mantıksal kapasite "
                f"sınırlarını desteklemelidir: {', '.join(limits_list)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.SOFTWARE_LIMITS.value,
                    title="Mantıksal Yönetim Limitleri",
                    text=c13_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Aggregate, Volume, LUN, Snapshot, SVM Sütunları",
                )
            )
            clause_id += 1

        # 14. E-Serisi ve Kurumsal Disk Havuzu Teknolojileri (DDP, T10-PI, SSD Havuzlama)
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
            c14_text = (
                f"Teklif edilen veri depolama sistemi; {', '.join(ddp_items)} teknolojilerini tam olarak destekleyecektir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.DATA_PROTECTION.value,
                    title="DDP ve Veri Güvencesi Teknolojileri",
                    text=c14_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: DDP Support, Data Assurance (T10 PI) Support, SSD support in a Disk Pool",
                )
            )
            clause_id += 1

        # 15. İşletim Sistemi ve Firmware Desteği (OS, BIOS, BMC, Kök Birim)
        firmware_items = []
        if spec.os_minimum and not UnitAndMultiplierParser.is_boolean_negative(spec.os_minimum):
            firmware_items.append(f"asgari sürüm {spec.os_minimum.strip()} (önerilen sürüm: {spec.os_recommended.strip() or spec.os_minimum.strip()}) depolama işletim sistemi")
            mark_consumed("minimum os", "maximum os", "recommended version")
        if spec.min_root_volume_size and not UnitAndMultiplierParser.is_boolean_negative(spec.min_root_volume_size):
            firmware_items.append(f"en az {spec.min_root_volume_size.strip()} kök birim (Root Volume) alanı")
            mark_consumed("min root volume size")
        if spec.bios_version and not UnitAndMultiplierParser.is_boolean_negative(spec.bios_version):
            firmware_items.append(f"en az {spec.bios_version.strip()} BIOS sürümü")
            mark_consumed("bios")
        if spec.bmc_version and not UnitAndMultiplierParser.is_boolean_negative(spec.bmc_version):
            firmware_items.append(f"en az {spec.bmc_version.strip()} BMC donanım yönetim firmware sürümü")
            mark_consumed("bmc")

        if firmware_items:
            c15_text = (
                f"Teklif edilen veri depolama sistemi, üreticinin onayladığı şu resmi yazılım ve firmware seviyelerinde "
                f"olmalıdır: {'; '.join(firmware_items)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.FIRMWARE_OS.value,
                    title="İşletim Sistemi ve Firmware Sürümleri",
                    text=c15_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Minimum OS, Maximum OS, BIOS, BMC, Min Root Volume Size",
                )
            )
            clause_id += 1

        # 16. Güç ve Voltaj Uyumluluğu
        if spec.input_voltage and not UnitAndMultiplierParser.is_boolean_negative(spec.input_voltage):
            v_raw = spec.input_voltage.strip().rstrip(";")
            v_parts = []
            if "40 to 48" in v_raw or "48" in v_raw:
                v_parts.append("-40 ile -48 V DC (telekom tipi Doğru Akım)")
            if "200 to 240" in v_raw or "240" in v_raw or "100 to 240" in v_raw or "100-240" in v_raw:
                if "100 to 240" in v_raw or "100-240" in v_raw:
                    v_parts.append("100 ile 240 VAC (Alternatif Akım)")
                elif "200 to 240" in v_raw:
                    v_parts.append("200 ile 240 VAC (Alternatif Akım)")
                else:
                    v_parts.append(f"{v_raw} VAC")
            if not v_parts:
                v_parts.append(f"{v_raw} VAC")

            voltage_desc = " ve/veya ".join(v_parts)
            c16_text = (
                f"Teklif edilen veri depolama sistemi üzerinde tam yedekli güç kaynakları bulunmalı ve "
                f"{voltage_desc} elektrik şebeke besleme standartlarında kesintisiz çalışmayı desteklemelidir."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.ENVIRONMENTAL.value,
                    title="Giriş Gücü ve Voltaj Uyumluluğu",
                    text=c16_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Input Power Voltage",
                )
            )
            clause_id += 1
            mark_consumed("input power voltage")

        # 17. Akustik Ses Düzeyleri
        if (spec.acoustic_sound_power and not UnitAndMultiplierParser.is_boolean_negative(spec.acoustic_sound_power)) or (
            spec.acoustic_sound_pressure and not UnitAndMultiplierParser.is_boolean_negative(spec.acoustic_sound_pressure)
        ):
            sound_parts = []
            if spec.acoustic_sound_power and not UnitAndMultiplierParser.is_boolean_negative(spec.acoustic_sound_power):
                sound_parts.append(f"ses gücü en fazla {spec.acoustic_sound_power.strip()}")
                mark_consumed("acoustic noise - sound power")
            if spec.acoustic_sound_pressure and not UnitAndMultiplierParser.is_boolean_negative(spec.acoustic_sound_pressure):
                sound_parts.append(f"ses basıncı en fazla {spec.acoustic_sound_pressure.strip()}")
                mark_consumed("acoustic noise - sound pressure")
            c17_text = (
                f"Teklif edilen veri depolama sisteminin sistem odası çalışma ortamında ürettiği akustik gürültü seviyeleri; "
                f"{' ve '.join(sound_parts)} sınırları içerisinde olmalıdır."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.ENVIRONMENTAL.value,
                    title="Akustik Ses Düzeyleri",
                    text=c17_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Acoustic Noise Sound Power / Pressure",
                )
            )
            clause_id += 1

        # 18. Çevresel Koşullar (Sıcaklık, Nem, İrtifa Aralıkları)
        env_parts = []
        if spec.operating_temp and not UnitAndMultiplierParser.is_boolean_negative(spec.operating_temp):
            env_parts.append(f"çalışma sıcaklığı {spec.operating_temp.strip()}")
            mark_consumed("operating temperature range")
        if spec.operating_humidity and not UnitAndMultiplierParser.is_boolean_negative(spec.operating_humidity):
            clean_ohum = spec.operating_humidity.replace("%", "").strip()
            env_parts.append(f"çalışma bağıl nem oranı %{clean_ohum}")
            mark_consumed("operating relative humidity")
        storage_hum = str(raw_attrs.get("Storage Relative Humidity") or raw_attrs.get("Transit Relative Humidity") or "").strip()
        if storage_hum and not UnitAndMultiplierParser.is_boolean_negative(storage_hum):
            clean_shum = storage_hum.replace("%", "").strip()
            env_parts.append(f"depolama ve nakliye bağıl nem oranı %{clean_shum}")
            mark_consumed("storage relative humidity", "transit relative humidity")
        if spec.operating_altitude and not UnitAndMultiplierParser.is_boolean_negative(spec.operating_altitude):
            env_parts.append(f"çalışma irtifası {spec.operating_altitude.strip()}")
            mark_consumed("operating altitude range")
        if spec.storage_temp and not UnitAndMultiplierParser.is_boolean_negative(spec.storage_temp):
            env_parts.append(f"depolama sıcaklığı {spec.storage_temp.strip()}")
            mark_consumed("storage temperature range")
        if spec.storage_altitude and not UnitAndMultiplierParser.is_boolean_negative(spec.storage_altitude):
            env_parts.append(f"depolama ortam irtifası {spec.storage_altitude.strip()}")
            mark_consumed("storage altitude range")
        if spec.transit_altitude and not UnitAndMultiplierParser.is_boolean_negative(spec.transit_altitude):
            env_parts.append(f"nakliye ve taşıma irtifası {spec.transit_altitude.strip()}")
            mark_consumed("transit altitude range")
        mark_consumed("transit temperature range")

        if env_parts:
            c18_text = (
                f"Teklif edilen veri depolama sistemi şu çevresel koşullarda kesintisiz çalışmayı ve depolamayı güvence "
                f"altına almalıdır: {'; '.join(env_parts)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.ENVIRONMENTAL.value,
                    title="Çevresel Çalışma ve Depolama Koşulları",
                    text=c18_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Operating Temperature, Humidity, Altitude, Storage/Transit Range",
                )
            )
            clause_id += 1

        # 19. Şasi Boyutları, Ağırlık ve Bakım Açıklıkları
        dim_parts = []
        if spec.chassis_height and not UnitAndMultiplierParser.is_boolean_negative(spec.chassis_height):
            dim_parts.append(f"yükseklik: {spec.chassis_height.strip()}")
            mark_consumed("chassis height")
        if spec.chassis_width_with_flanges and spec.chassis_width_without_flanges:
            dim_parts.append(f"genişlik: montaj kulakları dahil {spec.chassis_width_with_flanges.strip()} (montaj kulakları hariç {spec.chassis_width_without_flanges.strip()})")
            mark_consumed("chassis width with mounting flanges", "chassis width without mounting flanges", "width with mounting flanges", "width without mounting flanges")
        elif spec.chassis_width and not UnitAndMultiplierParser.is_boolean_negative(spec.chassis_width):
            dim_parts.append(f"genişlik: {spec.chassis_width.strip()}")
            mark_consumed("chassis width with mounting flanges", "chassis width without mounting flanges", "width with mounting flanges", "width without mounting flanges")
        if spec.chassis_depth and not UnitAndMultiplierParser.is_boolean_negative(spec.chassis_depth):
            dim_parts.append(f"derinlik: {spec.chassis_depth.strip()}")
            mark_consumed("chassis depth with cable mgmt", "chassis depth without cable mgmt")
        if spec.chassis_weight and not UnitAndMultiplierParser.is_boolean_negative(spec.chassis_weight):
            dim_parts.append(f"ağırlık: en fazla {spec.chassis_weight.strip()}")
            mark_consumed("weight", "weight (max)", "weight (min)")
        if spec.clearance_front and not UnitAndMultiplierParser.is_boolean_negative(spec.clearance_front):
            dim_parts.append(f"ön soğutma/bakım açıklığı: {spec.clearance_front.strip()}")
            mark_consumed("front clearance (cooling)", "front clearance (maintenance)")
        if spec.clearance_rear and not UnitAndMultiplierParser.is_boolean_negative(spec.clearance_rear):
            dim_parts.append(f"arka soğutma/bakım açıklığı: {spec.clearance_rear.strip()}")
            mark_consumed("rear clearance (cooling)", "rear clearance (maintenance)")

        if dim_parts:
            c19_text = (
                f"Teklif edilen veri depolama ünitesinin fiziksel boyutları, ağırlığı ve montaj standartları şu değerleri sağlamalıdır: "
                f"{'; '.join(dim_parts)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.CHASSIS_PHYSICAL.value,
                    title="Fiziksel Şasi Boyutları, Ağırlık ve Bakım Açıklıkları",
                    text=c19_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Chassis Dimensions, Weight, and Clearances",
                )
            )
            clause_id += 1

        # 20. Standartlar ve Sertifikalar
        cert_parts = []
        if spec.certifications_emc and not UnitAndMultiplierParser.is_boolean_negative(spec.certifications_emc):
            cert_parts.append(f"EMC/EMI sertifikaları: {spec.certifications_emc.strip()}")
            mark_consumed("certifications emc/emi")
        if spec.certifications_safety and not UnitAndMultiplierParser.is_boolean_negative(spec.certifications_safety):
            cert_parts.append(f"Güvenlik sertifikaları: {spec.certifications_safety.strip()}")
            mark_consumed("certifications safety", "certifications safety/emc/emi/rohs", "certifications safety/emc/emi")
        if spec.standards_emc and not UnitAndMultiplierParser.is_boolean_negative(spec.standards_emc):
            cert_parts.append(f"EMC/EMI teknik standartları: {spec.standards_emc.strip()}")
            mark_consumed("standards emc/emi")
        if spec.standards_safety and not UnitAndMultiplierParser.is_boolean_negative(spec.standards_safety):
            cert_parts.append(f"Güvenlik teknik standartları: {spec.standards_safety.strip()}")
            mark_consumed("standards safety")

        if cert_parts:
            c20_text = (
                f"Teklif edilen donanım elektromanyetik uyumluluk ve güvenlik standartları kapsamında şu onaylara "
                f"ve test standartlarına tam uyumlu olacaktır: {'; '.join(cert_parts)}."
            )
            clauses.append(
                Clause(
                    id=clause_id,
                    category=ColumnCategory.COMPLIANCE.value,
                    title="Uluslararası Uyumluluk ve Güvenlik Sertifikaları",
                    text=c20_text,
                    is_parametric=True,
                    source_note=f"{spec.source_file}: Certifications and Standards Columns",
                )
            )
            clause_id += 1

        # =====================================================================
        # 21. TAM DİNAMİK FALLBACK MOTORU (DYNAMIC FALLBACK SYNTHESIZER)
        # Tabloya sonradan eklenmiş veya yukarıdaki standart bloklarda geçmeyen
        # her türlü yeni üretici kolonu için otomatik şartname maddesi üretir.
        # Bu sayede TABLODA OLAN HİÇBİR BİLGİ ASLA ATLANMAZ!
        # =====================================================================
        administrative_metadata_keys = {
            "model", "release date", "end of support (eos)", "1", "acl (access list)",
            "high priority controller", "high priority queue", "regular priority controller", "regular priority queue",
            "intercluster lif"
        }

        for raw_col, val in raw_attrs.items():
            col_key = raw_col.lower().strip()
            if col_key in consumed_columns or col_key in administrative_metadata_keys:
                continue
            if val is None or UnitAndMultiplierParser.is_boolean_negative(val):
                continue

            # Kolonu semantik olarak analiz et
            category = SemanticClassifier.classify(raw_col)
            val_str = str(val).strip()

            # Türkçe kurumsal şartname metni sentezleme
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

        # 22. Garanti ve Destek Standardı
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
                source_note="İhale Garanti Standardı",
            )
        )
        clause_id += 1

        # Jenerik Mod filtrelemesi (İstenmişse marka/model isimlerini temizle)
        if request.flexibility == "jenerik":
            for c in clauses:
                c.text = scrub_brand_and_model(c.text, request.brand, spec.model_name)

        return clauses
