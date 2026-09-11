import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI

# Load .env explicitly for the test script
load_dotenv()

def test_azure_openai():
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if not endpoint or not api_key:
        print("HATA: .env dosyasında AZURE_OPENAI_ENDPOINT veya AZURE_OPENAI_API_KEY bulunamadı.")
        sys.exit(1)

    print(f"Bağlantı test ediliyor...")
    print(f"Endpoint: {endpoint}")
    print(f"Deployment: {deployment}")
    print(f"API Version: {api_version}")
    
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint,
        )
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "user", "content": "Merhaba, bağlantı testi için bana tek kelimelik bir cevap ver (örneğin: Başarılı)."}
            ]
        )
        print("\n[BASARILI] BAGLANTI BASARILI!")
        print(f"Azure AI Foundry (OpenAI) Yaniti: {response.choices[0].message.content}")
        
    except Exception as e:
        print("\n[BASARISIZ] BAGLANTI BASARISIZ!")
        print(f"Hata Detayı: {e}")

if __name__ == "__main__":
    test_azure_openai()
