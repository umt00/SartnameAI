import json

from openai import AzureOpenAI

from shared.config import get_settings
from shared.models import Clause, SpecRequest, StorageSpec


class AIClauseEngine:
    """Azure OpenAI tabanlı dinamik şartname üretim motoru."""

    def __init__(self):
        self.settings = get_settings()

        if not self.settings.AZURE_OPENAI_API_KEY or not self.settings.AZURE_OPENAI_ENDPOINT:
            raise ValueError("Azure OpenAI yapılandırması eksik. (Endpoint veya API Key)")

        self.client = AzureOpenAI(
            api_key=self.settings.AZURE_OPENAI_API_KEY,
            api_version=self.settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=self.settings.AZURE_OPENAI_ENDPOINT,
        )
        self.deployment_name = self.settings.AZURE_OPENAI_DEPLOYMENT_NAME

        examples_path = self.settings.PROJECT_ROOT / "data" / "prompts" / "clause_examples.json"
        if examples_path.exists():
            with open(examples_path, "r", encoding="utf-8") as f:
                self.examples = json.load(f)
        else:
            self.examples = []

    def _build_system_prompt(self, request: SpecRequest) -> str:
        base_prompt = (
            "Sen kurumsal BT altyapıları konusunda uzman bir sistem mühendisi ve kurumsal şartname danışmanısın.\n"
            "Sana bir veri depolama sisteminin teknik özellikleri (JSON formatında) verilecek.\n"
            "Görevin, bu özellikleri kurumsal, rekabetçi ve hukuki/teknik açıdan bağlayıcı bir şartnameye dönüştürmektir.\n\n"
            "ŞARTNAME MİMARİSİ VE KURALLAR:\n"
            "1. Üretici Yeterliliği: Sistem üreticisi Gartner Magic Quadrant Primary Storage liderler çeyreğinde olmalı ve mikroçekirdek (microkernel) işletim sisteminin öz geliştiricisi/telif sahibi olmalıdır.\n"
            "2. Yüksek Erişilebilirlik & Mimari: Aktif-Aktif çalışan en az 2 kontrol ünitesi (HA Pair), 2U şasi, tek hata noktası (SPOF) barındırmayan tam yedekli donanım mimarisi (çift güç kaynağı, yedekli fanlar, modüler kontrol üniteleri).\n"
            "3. Donanım Özellikleri:\n"
            "   - İşlemci: Her düğümde ve toplamda fiziksel çekirdek sayısı açıkça belirtilmelidir.\n"
            "   - Bellek (DRAM): Fiziksel DRAM bellek miktarı belirtilmeli, SSD/Flash sanal bellekler hariç tutulmalıdır.\n"
            "   - Kalıcı Önbellek: Batarya/süper kapasitör korumalı NVMEM/NVRAM mimarisi olmalıdır.\n"
            "   - Ağ ve SAN Portları: Listelenen tüm 25GbE ve FC portları eksiksiz belirtilmeli; 25GbE portlar için gerekli tüm optik transceiver (SFP28 SR) modülleri eksiksiz temin edilmelidir.\n"
            "4. Kapasite ve Raf Genişlemesi:\n"
            "   - Harici Disk Rafları: 'SSD ve/veya NVMe SSD' ve 'toplamda en az X adet harici disk rafı' ifadesi kullanılmalıdır (NVMe/SAS ayrımı tek bir genel kısıtlama yaratmadan toplam genişleme olarak verilmelidir).\n"
            "   - Ham Kapasite: 'Sistem, tamamen flash yapılandırmada en az X PB ham kapasiteyi destekleyebilecek şekilde genişleyebilmelidir' formatında yazılmalıdır.\n"
            "   - Veri Verimliliği: Sistem tipine göre (Flash sistemlerde en az 4:1) satıriçi tekilleştirme, sıkıştırma ve kompaktlama taahhüt edilmeli; oran sağlanamazsa eksik kapasite üretici tarafından ücretsiz ek donanımla karşılanmalıdır.\n"
            "   - Net Kapasite Güvencesi: İşletim sistemi (root volume), sistem overhead ve RAID koruma alanları net kullanılabilir kapasiteden düşülmüş olmalıdır.\n"
            "5. Yazılım ve Yönetim Fonksiyonları:\n"
            "   - Yatayda Büyüme (Scale-Out): Dosya ve blok ölçeklenebilirliği tek bir maddede birleşik olarak verilmelidir (örn. en az 24 node dosya ve 12 node blok desteği).\n"
            "   - Depolama Havuzları: 800 gibi spesifik limitler kullanılmamalı; 'ihtiyaç duyulan sayıda bağımsız depolama havuzu' olarak jenerikleştirilmelidir.\n"
            "   - Geniş Ölçekli Dosya Alanları: 1000/1500 gibi mikro limitler kaldırılmalı; çoklu kaynağı tek bir küresel isim alanında birleştiren kesintisiz genişleme yeteneği belirtilmelidir.\n"
            "   - Eşzamanlı Bağlantı: 65.536 gibi sayısal kısıtlamalar kaldırılmalı; kurumsal ölçekte yüksek eşzamanlı oturum desteği olarak yazılmalıdır.\n"
            "   - Veri Şifreleme: 'Yazılım tabanlı' kısıtlaması kaldırılmalı; durağan veri şifreleme (Data-at-Rest Encryption - FIPS 140-2) olarak yazılmalıdır.\n"
            "   - Sistem Yazılımı: 9.19.1 gibi ONTAP patch sürümleri kesinlikle yazılmamalı; üreticinin resmi olarak desteklediği en güncel ve kararlı kurumsal işletim sistemi olarak yazılmalıdır.\n"
            "6. KESİNLİKLE EKLENMEYECEK GEREKSİZ/İÇSEL BİLGİLER (KARA LİSTE):\n"
            "   - 150 GiB dahili root volume gereksinimi (bu işletim sisteminin iç alanıdır, şartnamede istenmez).\n"
            "   - 10-35°C sıcaklık, %8-80 nem, akustik gürültü dB, milimetrik montaj boşlukları gibi veri merkezi standart çevresel koşulları.\n"
            "   - Markanın tescilli terimleri (Aggregate, FlexGroup, FabricPool vb.) yerine endüstri standardı jenerik terimler kullanılmalıdır.\n"
            "7. Hacim ve Sayı: Maddeler birbiriyle ilişkili şekilde mantıksal olarak gruplandırılmalı ve TOPLAMDA ORTALAMA 24-28 ADET Doyurucu Şartname Maddesi oluşturulmalıdır.\n"
            f"8. Şartname tonu: {'Kuruma ve ürüne özel (rekabeti daraltıcı/koruyucu)' if request.flexibility == 'tekil' else 'Rekabete açık, jenerik kurumsal standart'}.\n"
            "9. Yanıtını SADECE aşağıdaki JSON formatında döndür:\n"
            "{\n"
            "  \"clauses\": [\n"
            "    {\n"
            "      \"category\": \"Kategori Adı (örneğin CHASSIS_PHYSICAL, COMPUTE, STORAGE_MEDIA, HIGH_AVAILABILITY, SYSTEM_SOFTWARE)\",\n"
            "      \"title\": \"Madde Başlığı\",\n"
            "      \"text\": \"Maddenin kendisi\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "ÖRNEKLER:\n"
        )

        for ex in self.examples:
            base_prompt += f"Girdi Özellikleri:\n{json.dumps(ex['input_attributes'], ensure_ascii=False, indent=2)}\n"
            base_prompt += f"Çıktı Madde:\n{json.dumps(ex['output_clause'], ensure_ascii=False, indent=2)}\n\n"

        return base_prompt

    def generate_clauses(self, spec: StorageSpec, request: SpecRequest) -> list[Clause]:
        """Excel verilerini AI'ye gönderip Clauses üretir."""

        system_prompt = self._build_system_prompt(request)

        # Filtrele ve temizle (sadece anlamlı olan verileri gönder ki token tasarrufu olsun)
        clean_spec = spec.model_dump(exclude_none=True, exclude_defaults=True)
        # raw_attributes içindeki gereksiz/boş olanları da silebiliriz ama şimdilik doğrudan yollayalım

        user_prompt = f"Lütfen aşağıdaki teknik özellikler tablosundan şartname maddelerini JSON dizisi olarak üret:\n\n{json.dumps(clean_spec, ensure_ascii=False, indent=2)}"

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={ "type": "json_object" } # Bazı modellerde json_object desteklenmeyebilir diziler için, bu yüzden role='system' da zorluyoruz
            )

            content = response.choices[0].message.content
            # Eger json_object dict dönmeye zorlarsa, sarmalanmış olabilir. Biz düz string olarak parse edelim.
            # Azure OpenAI json_object kullanırken kök elemanın Object olmasını bekleyebilir.
            # Bizim promptumuzda Array dönmesini istedik. API'nin json_object kısıtlamasına takılmamak için
            # root node u "clauses": [...] yapalım.
        except Exception as e:
            print(f"Azure OpenAI Error: {e}")
            return []

        # Parse ve Clause objelerine dönüştür
        clauses = []
        clause_id = 1
        try:
            data = json.loads(content)
            items = data.get("clauses", data) if isinstance(data, dict) else data

            if isinstance(items, list):
                for item in items:
                    clauses.append(
                        Clause(
                            id=clause_id,
                            category=item.get("category", "GENEL"),
                            title=item.get("title", "Özellik"),
                            text=item.get("text", ""),
                            is_parametric=True,
                            source_note="Azure AI Generated"
                        )
                    )
                    clause_id += 1
        except json.JSONDecodeError:
            print("AI yanıtı parse edilemedi.")

        return clauses
