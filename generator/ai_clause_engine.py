import json
from pathlib import Path
from typing import List

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
            "Sen uzman bir kurumsal sistem mühendisi ve şartname hazırlayıcısın.\n"
            "Sana bir veri depolama sisteminin teknik özellikleri (JSON formatında) verilecek.\n"
            "Görevin SADECE bu özellikleri kullanarak profesyonel bir şartname diliyle maddeler (clauses) üretmektir.\n\n"
            "KURALLAR:\n"
            "1. Asla tablodaki (JSON'daki) özellikler dışında bir donanım uydurma (NO HALLUCINATION).\n"
            "2. Markanın birebir ürün modellerini, çekmece/kabin kodlarını (örn: AFF A30, DS224C, NS224) kesinlikle ekleme. Şartname spesifik tek bir modele değil, 'ürün grubuna' hitap etmeli ve kapsayıcı olmalıdır.\n"
            "3. Elektrik voltaj değerleri, akustik gürültü seviyeleri, milimetrik ebat ve ağırlıklar, EMC/EMI sertifika kodları gibi gereksiz teknik spesifikasyonları ŞARTNAMEYE EKLEME. (Kabin boyutu U olarak kalabilir).\n"
            "4. Aggregate, FlexGroup, Constituent gibi sadece tek bir markaya (örneğin NetApp) özel teknolojilerin marka isimlerini kullanma; yerine 'Depolama Havuzu', 'Mantıksal Alan' gibi jenerik terimler kullan.\n"
            "5. Çok detaya giren spesifik kapasite limitlerini (örneğin 'en az 4,413,600 dosya', 'en az 16800 TiB ham kapasite') ilk aşamada verme, bunları daha esnek ve kurumsal ölçeği belirtecek şekilde jenerikleştir.\n"
            "6. Eğer bir özellik '0', 'Yok' veya null ise o konudan bahsetme.\n"
            "7. Tüm teknik detayları birbiriyle ilişkili şekilde mantıksal olarak gruplandır ve TOPLAMDA ORTALAMA 25-30 ADET Doyurucu Şartname Maddesi oluştur. Çok parçalı (60-70 madde) bir yapı kurma; benzer konuları (örneğin işlemci, RAM, NVRAM) aynı maddede veya ardışık 2-3 maddede eriterek birleştir.\n"
            f"8. Şartname tonu: {'Kuruma ve ürüne özel' if request.flexibility == 'tekil' else 'Rekabete açık, jenerik'}.\n"
            "9. Yanıtını SADECE aşağıdaki formattaki bir JSON nesnesi (object) olarak döndür:\n"
            "{\n"
            "  \"clauses\": [\n"
            "    {\n"
            "      \"category\": \"Kategori Adı (örneğin COMPUTE, STORAGE_MEDIA, HIGH_AVAILABILITY)\",\n"
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

    def generate_clauses(self, spec: StorageSpec, request: SpecRequest) -> List[Clause]:
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
