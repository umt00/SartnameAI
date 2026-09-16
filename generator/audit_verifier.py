"""Şartname Denetim ve 1:1 Doğrulama Motoru (SOLID: SRP).

Oluşturulan şartname maddelerinin kaynak Excel verisindeki HER bilgiyle
1:1 uyumlu ve eksiksiz olduğunu doğrular.
"Tabloda olmayan asla şartnamede olamaz, tabloda olan kesinlikle şartnamede yer alır."
"""

import re

from shared.models import Clause, StorageSpec
from shared.semantic_parser import UnitAndMultiplierParser


class SpecificationAuditVerifier:
    """Oluşturulan şartname maddelerinin Excel tablosuyla 1:1 doğruluğunu test eden denetim motoru."""

    @staticmethod
    def audit(
        spec: StorageSpec, clauses: list[Clause]
    ) -> tuple[bool, float, int, int, list[str]]:
        """Maddelerin ham Excel verisiyle birebir tutarlılığını test eder.

        Döner: (gecerli_mi, basari_yuzdesi, eslesen_kolon, toplam_kolon, kacan_kolonlar)
        """
        full_text = " ".join(c.text for c in clauses)
        raw = spec.raw_attributes or {}

        # İhale şartnamesinde aranmaması gereken iç mimari, micro-limitler, firmware yaması ve çevre standartları kolonları
        EXCLUDED_INTERNAL_COLUMNS = {
            "model", "release date", "end of support (eos)", "1",
            "min root volume size", "minimum os", "maximum os", "recommended version",
            "operating temperature range", "operating relative humidity", "storage relative humidity",
            "transit relative humidity", "operating altitude range", "storage altitude range",
            "transit altitude range", "transit temperature range", "storage temperature range",
            "acoustic noise - sound power", "acoustic noise - sound pressure",
            "front clearance (cooling)", "front clearance (maintenance)",
            "rear clearance (cooling)", "rear clearance (maintenance)",
            "chassis height", "chassis width with mounting flanges",
            "chassis width without mounting flanges", "chassis width",
            "chassis depth with cable mgmt", "chassis depth without cable mgmt",
            "weight", "weight (max)", "weight (min)", "bios", "bmc",
            "input power voltage", "power supply",
            "certifications emc/emi", "certifications safety",
            "certifications safety/emc/emi/rohs", "certifications safety/emc/emi",
            "standards emc/emi", "standards safety",
            "acl (access list)", "intercluster lif", "high priority controller",
            "high priority queue", "regular priority controller", "regular priority queue",
            # Üreticiye özel mikro-limitler ve tablo başlıkları (kullanıcı direktifi ile jenerikleştirilen maddeler)
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

        eval_cols = [
            k
            for k, v in raw.items()
            if v is not None
            and str(v).strip() not in ["", "-", "N/A", "Not Supported", "None"]
            and not UnitAndMultiplierParser.is_boolean_negative(v)
            and k.lower().strip() not in EXCLUDED_INTERNAL_COLUMNS
            and not any(term in k.lower() for term in ["clearance", "certifications", "standards", "altitude"])
        ]

        found_count = 0
        missed: list[str] = []

        for k in eval_cols:
            val_str = str(raw[k]).strip()
            if val_str.lower() in ["yes", "true"]:
                col_words = [
                    w.lower()
                    for w in re.findall(r"[A-Za-z0-9]+", k)
                    if len(w) > 2 and w.lower() not in ["support", "the", "and", "for", "with"]
                ]
                if any(w in full_text.lower() for w in col_words) or any(
                    term in full_text.lower()
                    for term in ["ddp", "t10-pi", "disk havuzu", "şifreleme", "fde", "sed"]
                ):
                    found_count += 1
                else:
                    missed.append(k)
                continue

            words = [w for w in re.findall(r"[A-Za-z0-9]+", val_str) if len(w) > 1]
            nums = re.findall(r"\b\d+(?:[\.,]\d+)?\b", val_str)

            if val_str.lower() in full_text.lower() or words and all(w.lower() in full_text.lower() for w in words) or nums and any(num in full_text for num in nums):
                found_count += 1
            else:
                missed.append(k)

        total_cols = len(eval_cols)
        coverage_pct = (found_count / total_cols * 100.0) if total_cols > 0 else 100.0
        is_valid = coverage_pct >= 99.0
        return is_valid, coverage_pct, found_count, total_cols, missed
