# SartnameAI — Kurumsal Teknik Şartname & Karşılaştırma Asistanı

SartnameAI; kurumsal veri depolama sistemleri için **ETL Veri Pipeline'ı**, **1:1 Doğrulamalı Şartname Üretimi** ve **Akıllı Şartname Karşılaştırma** işlevlerini bir araya getiren, bağımsız FastMCP sunucuları üzerinden **Microsoft Teams**, **Copilot Studio** ve **Azure** ortamlarına entegre olabilen 3 katmanlı yapay zekâ asistanıdır.

---

## 🏗️ 3 Modüllü Sistem Mimarisi

```
                             ┌──────────────────────────────────────┐
                             │ Microsoft Teams / Copilot Studio     │
                             └──────────────────┬───────────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    ┌─────────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────────┐
    │  Modül 1: Pipeline ETL  │    │  Modül 2: Generator     │    │  Modül 3: Matcher       │
    │  FastMCP (:8001)        │    │  FastMCP (:8002)        │    │  FastMCP (:8003)        │
    ├─────────────────────────┤    ├─────────────────────────┤    ├─────────────────────────┤
    │ • PDF Tablo Çıkarıcı    │    │ • 22+ Donanım Bloğu     │    │ • 4 Seviyeli Puanlama   │
    │ • Pivot ve Normalizasyon│    │ • Dinamik Fallback      │    │ • Akıllı Satış Tavsiyesi│
    │ • Otomatik Arşivleme    │    │ • 1:1 Doğrulama Motoru  │    │ • Absürt Talep Tespiti  │
    │ • Katalog İndeksleme    │    │ • Word (.docx) Üretici  │    │ • Kriter Analizi        │
    └────────────┬────────────┘    └────────────┬────────────┘    └────────────┬────────────┘
                 │                              │                              │
                 └──────────────────────────────┼──────────────────────────────┘
                                                ▼
                               ┌─────────────────────────────────┐
                               │     Ortak Katman (shared/)      │
                               │  • ExcelCatalogService          │
                               │  • StorageSpec & Clause Modeller│
                               │  • Semantik Taksonomi & Parser  │
                               │  • Yerel & Azure Blob Depolama  │
                               └─────────────────────────────────┘
```

---

## 🚀 Temel Özellikler

### 1. Sıfır Veri Kaybı ve Dinamik Fallback
- Standart 22+ donanım bloğunun haricinde, Excel tablolarına yeni eklenmiş veya egzotik herhangi bir kolon algılandığında **Dinamik Fallback Motoru** otomatik devreye girer.
- Hiçbir üretici parametresi atlanmaz; tabloda olan her bilgi şartnamede mutlaka yer alır.

### 2. %100 1:1 Doğrulama Güvencesi (Zero Hallucination)
- Her şartname üretildikten sonra `SpecificationAuditVerifier` tarafından otomatik teste sokulur.
- Tabloda olmayan hiçbir bilgi şartnameye eklenemez, tablodaki her bilgi teyit edilir.
- Doğrulama sonuçları dokümanın yanında `.audit.json` raporu olarak saklanır.

### 3. Çok Katmanlı Şartname Karşılaştırma (Matcher)
- **Tier 1 (Tam Uyum, 90-100 Puan):** Şartnamenin tüm kriterlerini doğrudan karşılayan ürünler.
- **Tier 2 (Büyük Çoğunluk, 80-89 Puan):** Çoğu kriteri sağlayan, ufak opsiyonlarla tamamlanabilecek ürünler.
- **Tier 3 (Ufak Değişiklik, 60-79 Puan):** RAM/disk revizyonu ile teklif edilebilecek alternatifler.
- **Absürt Talep Analizi:** İhale metinlerindeki mantıksız (örn: 2048 GB RAM talebi) veya teknik olarak çelişkili maddeleri tespit ederek itiraz zeyilnamesi önerir.

### 4. Kurumsal Word (.docx) Doküman Çıktısı
- Örnek şartname şablonunun kurumsal yazı tiplerini, renklerini ve başlık hiyerarşisini miras alır.
- Tekil (markaya özel) veya Jenerik (rekabete açık) formatta üretilir.

---

## 📂 Dizin Yapısı

```
SartnameAI/
├── main.py                         # Zengin Terminal Kontrol Paneli (Rich CLI)
├── pyproject.toml                  # UV Bağımlılık Yönetimi
├── .env.example                    # Örnek Ortam Değişkenleri
├── .gitignore                      # Git Kuralları
├── README.md                       # Dokümantasyon
│
├── data/
│   ├── catalogs/                   # Normalize edilmiş Excel tabloları (TEK KAYNAK)
│   │   ├── AFF A series HW_excel.xlsx
│   │   ├── AFF C series HW_excel.xlsx
│   │   ├── AFX HW_excel.xlsx
│   │   ├── ASA A&C Series HW_excel.xlsx
│   │   ├── E50-E80 HW_excel.xlsx
│   │   └── FAS Series HW_excel.xlsx
│   └── templates/                  # Örnek şartname Word şablonu
│       └── NetAppTaslak-Ornek-Sartname-v02_FAS2820_Calix.docx
│
├── output/                         # Üretilen şartnameler (.docx) ve denetim raporları (.audit.json)
│   └── .gitkeep
│
├── pipeline/                       # MODÜL 1: ETL Pipeline
│   ├── pipeline_service.py         # PDF → Excel dönüşüm motoru
│   ├── mcp_server.py               # FastMCP sunucusu (:8001)
│   ├── 1_incoming_pdfs/            # Yeni eklenen PDF'ler
│   └── 2_processed_pdfs/           # İşlenmiş arşiv PDF'leri
│
├── generator/                      # MODÜL 2: Şartname Üretici
│   ├── clause_engine.py            # 22+ blok ve dinamik fallback motoru
│   ├── audit_verifier.py           # 1:1 doğrulama ve denetim motoru
│   ├── spec_service.py             # Uçtan uca orkestrasyon servisi
│   ├── docx_builder.py             # Word (.docx) doküman üretici
│   ├── search_enricher.py          # Hibrit web arama & üretici teyidi
│   └── mcp_server.py               # FastMCP sunucusu (:8002)
│
├── matcher/                        # MODÜL 3: Şartname Karşılaştırma
│   ├── scoring_engine.py           # 4 katmanlı ağırlıklı puanlama
│   ├── advisor_engine.py           # Akıllı satış önerisi & absürtlük tespiti
│   ├── matcher_service.py          # Karşılaştırma orkestratörü
│   └── mcp_server.py               # FastMCP sunucusu (:8003)
│
├── shared/                         # Ortak Katman
│   ├── config.py                   # Pydantic Settings (.env)
│   ├── models.py                   # StorageSpec, Clause, MatchResult vb.
│   ├── catalog_service.py          # Excel tarayıcı, önbellek & fuzzy arama
│   ├── semantic_parser.py          # Semantik taksonomi ve metin motoru
│   ├── storage_service.py          # Yerel ve Azure Blob depolama
│   └── validators.py               # Jenerik mod marka filtresi
│
└── tests/                          # Kapsamlı Test Paketi
    ├── test_catalog.py             # Katalog ve fuzzy model testleri
    ├── test_generator.py           # Şartname üretim ve %100 audit testleri
    ├── test_matcher.py             # Eşleştirme ve absürtlük testleri
    └── test_pipeline.py            # PDF dönüşüm ve pipeline testleri
```

---

## ⚡ Hızlı Başlangıç

### Gereksinimler
- Python >= 3.10
- [uv](https://github.com/astral-sh/uv) paket yöneticisi

### Kurulum

```bash
# Bağımlılıkları yükleyin
uv sync

# Ortam değişkenlerini yapılandırın
cp .env.example .env
```

### 1. Terminal Kontrol Panelini Başlatma

```bash
uv run python main.py
```

Kontrol paneli üzerinden tek tuşla:
- Yeni şartname hazırlayabilir,
- Gelen şartnameyi karşılaştırıp en uygun ürünü bulabilir,
- Yeni PDF'leri kataloğa dönüştürebilir,
- Tüm otomatik testleri çalıştırabilirsiniz.

---

## 🔌 FastMCP Sunucularını Çalıştırma

Her modül bağımsız bir FastMCP sunucusu olarak çalışır:

```bash
# Modül 1: Pipeline MCP (:8001)
uv run python pipeline/mcp_server.py

# Modül 2: Şartname Oluşturma MCP (:8002)
uv run python generator/mcp_server.py

# Modül 3: Şartname Karşılaştırma MCP (:8003)
uv run python matcher/mcp_server.py
```

### Copilot Studio ve Teams Entegrasyonu
Sunucular dahili **CORS Middleware** ve **PathNormalizer** içerir. Cloudflare tüneli (`cloudflared`) veya Azure App Service üzerinden doğrudan Copilot Studio'ya bağlanabilir.

---

## 🧪 Testleri Çalıştırma

Tüm modüllerin birim ve entegrasyon testleri:

```bash
uv run pytest tests/ -v
```

---

## 📄 Lisans ve İletişim
- **Geliştirici:** Umut Arslan (umtarsln00@icloud.com)
- **Repo:** [https://github.com/umt00/SartnameAI](https://github.com/umt00/SartnameAI)