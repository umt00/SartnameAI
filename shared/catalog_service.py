"""Excel Donanım Kataloğu Servisi (SOLID: SRP & OCP).

Normalize edilmiş Excel dosyalarını tarar, modelleri indeksler ve StorageSpec nesnesine dönüştürür.
Otomatik dosya değişikliği algılama (mtime kontrolü) ile lazy indexing uygular.
"""

import re
from pathlib import Path
from typing import Any

import openpyxl

from shared.config import get_settings
from shared.models import CatalogModelSummary, StorageSpec


class ExcelCatalogService:
    """Excel dosyalarından donanım özelliklerini okuyan ve indeksleyen servis."""

    def __init__(self, catalogs_dir: Path | None = None):
        self.catalogs_dir = catalogs_dir or get_settings().CATALOGS_DIR
        self._cache: dict[str, StorageSpec] = {}
        self._summaries: list[CatalogModelSummary] = []
        self._last_mtimes: dict[Path, float] = {}
        self._is_indexed = False

    def _ensure_indexed(self) -> None:
        """Katalog dosyalarını tarar; yeni veya güncellenen dosya varsa belleği otomatik yeniler."""
        excel_files = sorted(self.catalogs_dir.glob("*.xlsx"))
        current_mtimes = {ef: ef.stat().st_mtime for ef in excel_files}

        if self._is_indexed and current_mtimes == self._last_mtimes:
            return

        self._cache.clear()
        self._summaries.clear()
        for ef in excel_files:
            self._load_excel_file(ef)

        self._last_mtimes = current_mtimes
        self._is_indexed = True

    def reload(self) -> None:
        """Kataloğu zorla yeniden tarar ve tüm önbelleği yeniler."""
        self._is_indexed = False
        self._last_mtimes = {}
        self._ensure_indexed()

    def _determine_series(self, filename: str, model_name: str) -> str:
        """Dosya adı ve modelden seri adını çıkarır."""
        fn_lower = filename.lower()
        if "aff a" in fn_lower:
            return "AFF A-Series (All-Flash High Perf)"
        if "aff c" in fn_lower:
            return "AFF C-Series (Capacity Flash)"
        if "afx" in fn_lower:
            return "AFX Series"
        if "asa" in fn_lower:
            return "ASA Series (All-SAN Storage)"
        if "e50" in fn_lower or "e80" in fn_lower or "e-series" in fn_lower:
            return "E-Series (Hybrid / High Density)"
        if "fas" in fn_lower:
            return "FAS Series (Unified Hybrid/Flash)"
        clean_stem = Path(filename).stem.replace("_excel", "").replace("_", " ").strip()
        return clean_stem or "Kurumsal Veri Depolama"

    def _determine_storage_tier(self, series: str, model_name: str) -> str:
        """Seriye ve modele göre depolama ortamı türünü belirler."""
        s_lower = (series + " " + model_name).lower()
        if any(t in s_lower for t in ["all-flash", "all flash", "nvme", "aff", "afx"]):
            return "All-Flash (NVMe SSD)"
        if "asa" in s_lower or "san" in s_lower:
            return "All-Flash SAN (NVMe SSD)"
        return "Hibrit (NVMe SSD ve NL-SAS)"

    def _load_excel_file(self, file_path: Path) -> None:
        """Tek bir Excel dosyasındaki modelleri okur."""
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            sheet = wb.active

            headers = [
                str(sheet.cell(1, c).value or "").strip() for c in range(1, sheet.max_column + 1)
            ]

            series = self._determine_series(file_path.name, "")

            for r in range(2, sheet.max_row + 1):
                model_raw = str(sheet.cell(r, 1).value or "").strip()
                if not model_raw or model_raw.lower() in ("notes description", "notes"):
                    continue

                row_data: dict[str, Any] = {}
                for c_idx, h in enumerate(headers, start=1):
                    if h:
                        val = sheet.cell(r, c_idx).value
                        if val is not None and str(val).strip() not in ("", "-"):
                            row_data[h] = val

                spec = self._parse_storage_spec(model_raw, series, file_path.name, row_data)
                clean_key = self._normalize_key(model_raw)
                self._cache[clean_key] = spec

                self._summaries.append(
                    CatalogModelSummary(
                        model_name=spec.model_name,
                        series=spec.series,
                        file_name=file_path.name,
                        ram_total_gb=spec.ram_total_gb,
                        max_drives=spec.max_drives,
                        max_raw_capacity=spec.max_raw_capacity,
                    )
                )
        except Exception as e:  # noqa: BLE001
            print(f"[Uyarı] Excel dosyası okunamadı ({file_path.name}): {e}")

    def _parse_storage_spec(
        self, model_name: str, series: str, filename: str, row: dict[str, Any]
    ) -> StorageSpec:
        """Ham satır verisini StorageSpec nesnesine dönüştürür."""
        tier = self._determine_storage_tier(series, model_name)
        architecture = "Unified (SAN, NAS ve Nesne)"
        if "e-series" in series.lower() or "e50" in model_name.lower() or "e80" in model_name.lower():
            architecture = "Blok Depolama (SAN / DDP)"
        elif "asa" in series.lower():
            architecture = "All-SAN (Blok Depolama)"

        # Kontrol Ünitesi sayısı
        ctrl_count = 2
        if "cluster" in model_name.lower() and "ha pair" not in model_name.lower():
            ctrl_count = 1
        if "Controller Count" in row:
            try:
                ctrl_count = int(row["Controller Count"])
            except (ValueError, TypeError):
                pass

        # RAM çıkarımı
        ram_node = 0
        ram_total = 0
        ram_raw = str(row.get("RAM (Per Node)") or row.get("System Memory") or "")
        m_node = re.search(r"(\d+)", ram_raw)
        if m_node:
            ram_node = int(m_node.group(1))

        ram_cfg_raw = str(row.get("RAM (Per Config)") or "")
        m_cfg = re.search(r"(\d+)", ram_cfg_raw)
        if m_cfg:
            ram_total = int(m_cfg.group(1))
        elif ram_node > 0:
            ram_total = ram_node * ctrl_count

        # NVMEM
        nvmem_node = 0.0
        nvmem_total = 0.0
        if "NVMEM (Per Node)" in row and str(row["NVMEM (Per Node)"]).strip() not in ("N/A", "-", ""):
            m = re.search(r"([\d\.]+)", str(row["NVMEM (Per Node)"]))
            if m:
                nvmem_node = float(m.group(1))
        if "NVMEM (Per Config)" in row and str(row["NVMEM (Per Config)"]).strip() not in ("N/A", "-", ""):
            m = re.search(r"([\d\.]+)", str(row["NVMEM (Per Config)"]))
            if m:
                nvmem_total = float(m.group(1))
        elif nvmem_node > 0:
            nvmem_total = nvmem_node * ctrl_count

        # NVRAM
        nvram_node = 0.0
        nvram_total = 0.0
        if "NVRAM (Per Node)" in row and str(row["NVRAM (Per Node)"]).strip() not in ("N/A", "-", ""):
            m = re.search(r"([\d\.]+)", str(row["NVRAM (Per Node)"]))
            if m:
                nvram_node = float(m.group(1))
        if "NVRAM (Per Config)" in row and str(row["NVRAM (Per Config)"]).strip() not in ("N/A", "-", ""):
            m = re.search(r"([\d\.]+)", str(row["NVRAM (Per Config)"]))
            if m:
                nvram_total = float(m.group(1))
        elif nvram_node > 0:
            nvram_total = nvram_node * ctrl_count

        # NVMe Cache
        nvme_cache_node = 0
        nvme_cache_tot = 0
        if "NVMe Flash Cache (Per Node)" in row:
            m = re.search(r"(\d+)", str(row["NVMe Flash Cache (Per Node)"]))
            if m:
                nvme_cache_node = int(m.group(1))
        if "NVMe Flash Cache (Per Config)" in row:
            m = re.search(r"(\d+)", str(row["NVMe Flash Cache (Per Config)"]))
            if m:
                nvme_cache_tot = int(m.group(1))
        elif nvme_cache_node > 0:
            nvme_cache_tot = nvme_cache_node * ctrl_count

        # Flash Read Cache & Destaging
        flash_read_cache = str(row.get("Flash Read Cache (GB)") or "").strip()
        destaging_cache = str(row.get("Max Destaging Cache-to- Flash Size (GB)") or row.get("Max Destaging Cache-to-Flash Size (GB)") or "").strip()

        # İşlemci
        proc_info = str(row.get("Processor Model") or "").strip()
        proc_arch = str(row.get("Processor Architecture") or "64 bit").strip()
        proc_speed = str(row.get("Processor Speed") or "").strip()
        proc_cores_node = 0
        proc_cores_tot = 0
        proc_count_node = 0
        proc_count_tot = 0

        cores_node_raw = str(row.get("Processor Cores (Per Node)") or "")
        m = re.search(r"(\d+)", cores_node_raw)
        if m:
            proc_cores_node = int(m.group(1))
        cores_cfg_raw = str(row.get("Processor Cores (Per Config)") or "")
        m = re.search(r"(\d+)", cores_cfg_raw)
        if m:
            proc_cores_tot = int(m.group(1))
        elif proc_cores_node > 0:
            proc_cores_tot = proc_cores_node * ctrl_count

        cnt_node_raw = str(row.get("Processor Count (Per Node)") or "")
        m = re.search(r"(\d+)", cnt_node_raw)
        if m:
            proc_count_node = int(m.group(1))
        cnt_cfg_raw = str(row.get("Processor Count (Per Config)") or "")
        m = re.search(r"(\d+)", cnt_cfg_raw)
        if m:
            proc_count_tot = int(m.group(1))
        elif proc_count_node > 0:
            proc_count_tot = proc_count_node * ctrl_count

        # Port bilgileri
        eth_ports_raw = str(row.get("Ethernet Ports") or "").strip()
        fc_ports_raw = str(row.get("Fibre Channel Ports") or "").strip()
        sas_ports_raw = str(row.get("SAS Ports") or "").strip()
        uta2_ports_raw = str(row.get("UTA2 Ports") or "").strip()
        expansion_raw = str(row.get("Expansion Slots") or "").strip()
        pci_raw = str(row.get("PCI Interface") or "").strip()
        oob_raw = str(row.get("OOB Management Port Interface (Per Controller)") or "").strip()

        # IP ve FC port sayıları (sayısal çıkarım)
        ip_count = 4
        ip_speed = 10
        fc_count = 4
        fc_speed = 32
        m_ip = re.search(r"(\d+)\s*[xX]\s*(\d+)", eth_ports_raw)
        if m_ip:
            ip_count = int(m_ip.group(1))
            ip_speed = int(m_ip.group(2))
        m_fc = re.search(r"(\d+)\s*[xX]\s*(\d+)", fc_ports_raw)
        if m_fc:
            fc_count = int(m_fc.group(1))
            fc_speed = int(m_fc.group(2))

        # Sürücüler
        max_drives = 0
        md_raw = str(
            row.get("Max Number of Drives (Total)")
            or row.get("Max number of Drives (Total)")
            or row.get("Max Drives")
            or row.get("Max number of Drives")
            or ""
        )
        if not md_raw:
            for k, v in row.items():
                if "max" in k.lower() and "drives" in k.lower() and "total" in k.lower():
                    md_raw = str(v)
                    break
        m = re.search(r"(\d+)", md_raw.replace(",", ""))
        if m:
            max_drives = int(m.group(1))

        # Scale-out düğümleri
        scale_out_nodes = 24
        scale_raw = str(row.get("Max Nodes per Cluster (NAS / SAN)") or "")
        m = re.search(r"(\d+)", scale_raw)
        if m:
            scale_out_nodes = int(m.group(1))

        nas_nodes_str = ""
        san_nodes_str = ""
        if "/" in scale_raw:
            parts = scale_raw.split("/")
            nas_nodes_str = parts[0].strip()
            san_nodes_str = parts[1].strip() if len(parts) > 1 else ""

        # Rack Units
        ru = 2
        ru_raw = str(row.get("Rack Units") or "")
        m = re.search(r"(\d+)", ru_raw)
        if m:
            ru = int(m.group(1))

        # Shelves
        shelves: dict[str, str] = {}
        for k, v in row.items():
            if "shelves" in k.lower() and v and str(v).strip() not in ("", "-", "N/A"):
                shelves[k] = str(v).strip()

        max_raw = str(row.get("Max FabricPool Size") or row.get("Max Volume Size (EB)") or row.get("Max Raw Capacity") or "").strip()

        # Sertifikalar
        cert_safety_keys = [
            "Certifications Safety", "Certifications Safety/EMC/EMI",
            "Certifications Safety/EMC/EMI/RoHS", "Certifications safety",
        ]
        found_safety = []
        for ck in cert_safety_keys:
            if ck in row and str(row[ck]).strip() not in ("", "-", "N/A"):
                val = str(row[ck]).strip()
                if val and val not in found_safety:
                    found_safety.append(val)
        cert_safety_str = "; ".join(found_safety)

        # Chassis Dimensions
        width_flanges = str(row.get("Chassis Width with Mounting Flanges") or row.get("Width with Mounting Flanges") or "").strip()
        width_no_flanges = str(row.get("Chassis Width without Mounting Flanges") or row.get("Width without Mounting Flanges") or "").strip()

        fc_cool = str(row.get("Front Clearance (Cooling)") or "").strip()
        fc_maint = str(row.get("Front Clearance (Maintenance)") or "").strip()
        if fc_cool and fc_maint and fc_cool != fc_maint:
            front_clearance = f"soğutma için {fc_cool} (bakım için {fc_maint})"
        else:
            front_clearance = fc_cool or fc_maint

        rc_cool = str(row.get("Rear Clearance (Cooling)") or "").strip()
        rc_maint = str(row.get("Rear Clearance (Maintenance)") or "").strip()
        if rc_cool and rc_maint and rc_cool != rc_maint:
            rear_clearance = f"soğutma için {rc_cool} (bakım için {rc_maint})"
        else:
            rear_clearance = rc_cool or rc_maint

        depth_with = str(row.get("Chassis Depth with Cable Mgmt") or "").strip()
        depth_without = str(row.get("Chassis Depth without Cable Mgmt") or "").strip()
        if depth_with and depth_without and depth_with != depth_without:
            chassis_depth = f"kablo yönetim kiti dahil {depth_with} (kablo yönetim kiti hariç {depth_without})"
        else:
            chassis_depth = depth_with or depth_without

        return StorageSpec(
            model_name=model_name,
            series=series,
            architecture=architecture,
            storage_tier=tier,
            controller_count=ctrl_count,
            scale_out_max_nodes=scale_out_nodes,
            scale_out_nas_nodes=nas_nodes_str,
            scale_out_san_nodes=san_nodes_str,
            ram_per_node_gb=ram_node,
            ram_total_gb=ram_total,
            ram_raw_text=ram_raw,
            nvmem_per_node_gb=nvmem_node,
            nvmem_total_gb=nvmem_total,
            nvram_per_node_gb=nvram_node,
            nvram_total_gb=nvram_total,
            nvme_cache_per_node_gb=nvme_cache_node,
            nvme_cache_total_gb=nvme_cache_tot,
            flash_read_cache_raw=flash_read_cache,
            max_destaging_cache_raw=destaging_cache,
            processor_info=proc_info,
            processor_arch=proc_arch,
            processor_speed=proc_speed,
            processor_cores_per_node=proc_cores_node,
            processor_cores_total=proc_cores_tot,
            processor_count_per_node=proc_count_node,
            processor_count_total=proc_count_tot,
            ethernet_ports_raw=eth_ports_raw,
            fc_ports_raw=fc_ports_raw,
            sas_ports_raw=sas_ports_raw,
            uta2_ports_raw=uta2_ports_raw,
            expansion_slots_raw=expansion_raw,
            pci_interface_raw=pci_raw,
            oob_mgmt_port_raw=oob_raw,
            ip_port_count=ip_count,
            ip_port_speed_gbps=ip_speed,
            fc_port_count=fc_count,
            fc_port_speed_gbps=fc_speed,
            internal_drives_count=str(row.get("Internal Drives count") or ""),
            max_drives=max_drives,
            max_nlsas_drives=str(row.get("Max number of NL-SAS Drives") or ""),
            max_sas_drives=str(row.get("Max number of SAS Drives") or ""),
            max_ssd_drives=str(row.get("Max number of SSD Drives") or ""),
            max_nvme_ssd_drives=str(row.get("Max number of NVMe SSD Drives") or ""),
            max_capacity_flash_drives=str(row.get("Max number of Capacity Flash NVMe SSD Drives") or ""),
            shelves_supported=shelves,
            max_raw_capacity=max_raw,
            efficiency_guarantee="3:1" if "Hibrit" in tier else "4:1",
            rack_units=ru,
            chassis_height=str(row.get("Chassis Height") or ""),
            chassis_width=width_flanges or width_no_flanges,
            chassis_width_with_flanges=width_flanges,
            chassis_width_without_flanges=width_no_flanges,
            chassis_depth=chassis_depth,
            chassis_weight=str(row.get("Weight") or row.get("Weight (Max)") or row.get("Weight (Min)") or ""),
            clearance_front=front_clearance,
            clearance_rear=rear_clearance,
            input_voltage=str(row.get("Input Power Voltage") or ""),
            acoustic_sound_power=str(row.get("Acoustic Noise - Sound Power") or ""),
            acoustic_sound_pressure=str(row.get("Acoustic Noise - Sound Pressure") or ""),
            operating_temp=str(row.get("Operating Temperature Range") or ""),
            operating_humidity=str(row.get("Operating Relative Humidity") or ""),
            operating_altitude=str(row.get("Operating Altitude Range") or ""),
            storage_temp=str(row.get("Storage Temperature Range") or ""),
            storage_altitude=str(row.get("Storage Altitude Range") or ""),
            transit_altitude=str(row.get("Transit Altitude Range") or ""),
            certifications_emc=str(row.get("Certifications EMC/EMI") or ""),
            certifications_safety=cert_safety_str,
            standards_emc=str(row.get("Standards EMC/EMI") or ""),
            standards_safety=str(row.get("Standards Safety") or ""),
            os_minimum=str(row.get("Minimum OS") or ""),
            os_maximum=str(row.get("Maximum OS") or ""),
            os_recommended=str(row.get("Recommended Version") or ""),
            min_root_volume_size=str(row.get("Min Root Volume Size") or ""),
            bios_version=str(row.get("BIOS") or ""),
            bmc_version=str(row.get("BMC") or ""),
            encryption_info=str(row.get("NetApp Volume Encryption") or ("Desteklenir" if str(row.get("Full Disk Encryption Support", "")).lower() == "yes" else "")),
            full_disk_encryption_support=str(row.get("Full Disk Encryption Support", "")).lower() == "yes",
            limits_aggregate=str(row.get("Aggregate") or ""),
            limits_volume=str(row.get("Volume") or row.get("Max Volume Count") or ""),
            limits_flexgroup=str(row.get("FlexGroup Volume") or row.get("FlexGroup") or ""),
            limits_flexgroup_constituent=str(row.get("FlexGroup Constituent") or ""),
            limits_lun=str(row.get("LUN") or ""),
            limits_snapshot=str(row.get("Snapshot") or ""),
            limits_svm=str(row.get("SVM") or row.get("Vserver") or ""),
            limits_connections=str(row.get("Connection") or ""),
            limits_consistency_group=str(row.get("Consistency group") or ""),
            limits_igroup=str(row.get("igroup") or ""),
            limits_max_files_node=str(row.get("Node") or ""),
            limits_max_files_pair=str(row.get("HA Pair") or ""),
            limits_bucket=str(row.get("Bucket") or ""),
            sector_bytes=str(row.get("Bytes") or ""),
            ddp_support=str(row.get("DDP Support", "")).lower() == "yes",
            t10_pi_support=str(row.get("Data Assurance (T10 PI) Support", "")).lower() == "yes",
            ssd_in_disk_pool_support=str(row.get("SSD support in a Disk Pool", "")).lower() == "yes",
            source_file=filename,
            raw_attributes=row,
        )

    def _normalize_key(self, text: str) -> str:
        """Arama için anahtar kelimeyi sadeleştirir."""
        return re.sub(r"[^a-zA-Z0-9]", "", text).lower()

    def get_spec(self, model_query: str) -> StorageSpec | None:
        """Model adına göre fuzzy/esnek eşleşmeyle donanım özelliğini getirir."""
        self._ensure_indexed()

        query_clean = self._normalize_key(model_query)
        if not query_clean:
            return None

        # 1. Tam normalize eşleşme
        if query_clean in self._cache:
            return self._cache[query_clean]

        # 2. Alt kelime eşleşmesi
        for key, spec in self._cache.items():
            if query_clean in key or key in query_clean:
                return spec

        # 3. Model parça eşleşmesi (kelime bazlı)
        tokens = re.findall(r"[a-zA-Z0-9]+", model_query.lower())
        for key, spec in self._cache.items():
            if all(t in key for t in tokens):
                return spec

        return None

    def list_models(self, series: str | None = None) -> list[CatalogModelSummary]:
        """Tüm modelleri veya belirli bir serideki modelleri döndürür."""
        self._ensure_indexed()
        if not series:
            return list(self._summaries)

        s_clean = series.lower()
        return [m for m in self._summaries if s_clean in m.series.lower()]

    def find_model(self, model_query: str) -> StorageSpec | None:
        """get_spec için kolaylık metodu."""
        return self.get_spec(model_query)

    def get_available_models(self) -> list[str]:
        """Kayıtlı tüm model adlarının listesini döner."""
        self._ensure_indexed()
        return [m.model_name for m in self._summaries]

    def get_all_specs(self) -> list[StorageSpec]:
        """Katalogdaki tüm modellerin StorageSpec listesini döner."""
        self._ensure_indexed()
        return list(self._cache.values())
