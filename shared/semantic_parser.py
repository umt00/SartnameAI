"""Semantik Kolon Sınıflandırma, Metin İşleme ve Yardımcı Motor.

SOLID: SRP — Metin analizi, sayı dönüştürme ve kolon sınıflandırmasından sorumludur.
"""

import re
from enum import Enum
from typing import Any, ClassVar


class ColumnCategory(str, Enum):
    """Semantik Donanım ve Teknik Kolon Kategorileri."""

    COMPUTE = "İşlemci ve Hesaplama"
    MEMORY = "Sistem Belleği (RAM)"
    NV_MEMORY = "Kalıcı Yazma Belleği (NVRAM / NVMEM)"
    STORAGE_MEDIA = "Kapasite ve Sürücüler"
    EXPANSION_SHELF = "Disk Genişleme Rafları"
    NETWORKING = "Ağ ve Bağlantı Portları"
    CHASSIS_PHYSICAL = "Şasi ve Fiziksel Boyutlar"
    ENVIRONMENTAL = "Güç ve Çevre Koşulları"
    COMPLIANCE = "Standartlar ve Sertifikalar"
    SOFTWARE_LIMITS = "Yazılım ve Mantıksal Limitler"
    FIRMWARE_OS = "İşletim Sistemi ve Firmware"
    HIGH_AVAILABILITY = "Yüksek Erişilebilirlik ve Kümeleme"
    DATA_PROTECTION = "Veri Güvenliği ve Şifreleme"
    GENERIC_FEATURE = "Genel Teknik Donanım Özellikleri"


class TurkishNumberConverter:
    """Sayısal değerleri şartnameler için Türkçe okunuşlarına çevirir."""

    UNITS: ClassVar[list[str]] = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
    TENS: ClassVar[list[str]] = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]

    @classmethod
    def to_words(cls, num: int) -> str:
        if num < 0:
            return f"eksi {cls.to_words(abs(num))}"
        if num < 10:
            return cls.UNITS[num]
        if num < 100:
            t = num // 10
            u = num % 10
            return f"{cls.TENS[t]} {cls.UNITS[u]}" if u else cls.TENS[t]
        if num < 1000:
            h = num // 100
            rem = num % 100
            prefix = f"{cls.UNITS[h]} yüz" if h > 1 else "yüz"
            return f"{prefix} {cls.to_words(rem)}" if rem else prefix
        if num < 10000:
            th = num // 1000
            rem = num % 1000
            prefix = f"{cls.UNITS[th]} bin" if th > 1 else "bin"
            return f"{prefix} {cls.to_words(rem)}" if rem else prefix
        return str(num)


class SemanticClassifier:
    """Herhangi bir kolon adını semantik kategoriye eşleyen sınıflandırıcı."""

    TAXONOMY_RULES: ClassVar[list[tuple[ColumnCategory, list[str]]]] = [
        (
            ColumnCategory.COMPUTE,
            ["processor", "cpu", "core", "ghz", "işlemci", "çekirdek", "socket", "hesaplama"],
        ),
        (
            ColumnCategory.NV_MEMORY,
            ["nvram", "nvmem", "non-volatile", "write cache", "destaging", "kalıcı bellek"],
        ),
        (
            ColumnCategory.MEMORY,
            ["ram", "system memory", "dram", "bellek", "controller memory", "main memory"],
        ),
        (
            ColumnCategory.EXPANSION_SHELF,
            ["shelves", "shelf", "enclosure", "jbod", "ebod", "genişleme raf", "disk raf"],
        ),
        (
            ColumnCategory.NETWORKING,
            [
                "port", "ethernet", "fibre channel", "fc port", "uta2", "sas port",
                "interface", "expansion slot", "pci", "roce", "iscsi", "oob", "qsfp", "sfp",
                "nvme-of",
            ],
        ),
        (
            ColumnCategory.STORAGE_MEDIA,
            [
                "drive", "disk", "ssd", "nvme", "nl-sas", "sas drives", "sürücü",
                "fabricpool", "raw capacity", "usable capacity", "capacity flash",
                "pool", "volume size", "ebod", "flash read cache",
            ],
        ),
        (
            ColumnCategory.HIGH_AVAILABILITY,
            ["cluster", "scale-out", "nodes per", "ha pair", "duplex", "controller count", "failover"],
        ),
        (
            ColumnCategory.CHASSIS_PHYSICAL,
            ["chassis", "rack unit", "height", "width", "depth", "clearance", "weight", "boyut", "kabin"],
        ),
        (
            ColumnCategory.ENVIRONMENTAL,
            [
                "acoustic", "noise", "sound power", "sound pressure", "temperature",
                "humidity", "altitude", "voltage", "power", "watt", "btu", "sıcaklık", "nem", "voltaj",
            ],
        ),
        (
            ColumnCategory.COMPLIANCE,
            ["certification", "standards", "emc", "safety", "rohs", "fcc", "sertifika", "uyumluluk"],
        ),
        (
            ColumnCategory.FIRMWARE_OS,
            ["os", "operating system", "minimum os", "maximum os", "bios", "bmc", "firmware", "yazılım"],
        ),
        (
            ColumnCategory.DATA_PROTECTION,
            ["encryption", "security", "şifreleme", "ddp", "data assurance", "t10", "immutable", "ransomware"],
        ),
        (
            ColumnCategory.SOFTWARE_LIMITS,
            ["aggregate", "volume", "flexgroup", "lun", "snapshot", "svm", "vserver", "igroup", "namespace", "bucket", "limit"],
        ),
    ]

    @classmethod
    def classify(cls, column_name: str) -> ColumnCategory:
        """Kolon adını analiz ederek en uygun semantik kategoriyi döndürür."""
        clean_name = column_name.lower().strip()

        for category, keywords in cls.TAXONOMY_RULES:
            for kw in keywords:
                if kw in clean_name:
                    return category

        return ColumnCategory.GENERIC_FEATURE


class UnitAndMultiplierParser:
    """Hücredeki metinsel/sayısal veriyi ve çarpanları analiz eden motor."""

    @staticmethod
    def extract_numeric(val: Any) -> float | None:
        """Metin içerisindeki ilk anlamlı sayısal değeri çıkarır."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        m = re.search(r"([\d\.,]+)", str(val))
        if m:
            clean_str = m.group(1).replace(",", "")
            try:
                return float(clean_str)
            except ValueError:
                return None
        return None

    @staticmethod
    def is_boolean_positive(val: Any) -> bool:
        """Değerin olumlu/desteklenen bir özellik olup olmadığını denetler."""
        s = str(val).strip().lower()
        return s in ("yes", "supported", "true", "desteklenir", "var", "1", "evet")

    @staticmethod
    def is_boolean_negative(val: Any) -> bool:
        """Değerin desteklenmeyen veya boş olup olmadığını denetler."""
        s = str(val).strip().lower()
        negatives = {"no", "not supported", "false", "desteklenmez", "yok", "0", "hayır", "n/a", "-", "none", ""}
        if s in negatives:
            return True
        parts = [p.strip() for p in s.split("/") if p.strip()]
        return bool(parts and all(p in negatives for p in parts))

    @staticmethod
    def clean_spec_text(text: str) -> str:
        """Şartnamede sırıtacak teknik kısaltmaları ve İngilizce kalıntıları temizler."""
        res = str(text).strip()
        res = re.sub(r"Max:\s*", "azami ", res)
        res = re.sub(r"Min:\s*", "asgari ", res)
        res = re.sub(r"per Chassis;?", "şasi başına", res, flags=re.IGNORECASE)
        res = re.sub(r"per HA Pair;?", "HA çifti başına", res, flags=re.IGNORECASE)
        res = re.sub(r"per Cluster;?", "küme başına", res, flags=re.IGNORECASE)
        res = re.sub(r"per System;?", "sistem genelinde", res, flags=re.IGNORECASE)
        res = re.sub(r";\s*$", "", res)
        return res
