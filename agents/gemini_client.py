"""
Münazara — Gemini API Wrapper

Tek fonksiyon: chat(system_prompt, history, temperature) → response text
Kişi A bu dosyayı yönetir.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Client oluştur
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Kullanılacak model — ücretsiz katman için Flash
MODEL = "gemini-2.0-flash"


def chat(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> str:
    """
    Gemini'a mesaj gönder, cevap al.

    Args:
        system_prompt: Ajanın karakter tanımı (system instruction)
        history: Mesaj geçmişi [{"role": "user"|"model", "content": "..."}]
        temperature: Yaratıcılık seviyesi (0.0-1.0)
        max_tokens: Maksimum cevap uzunluğu

    Returns:
        Gemini'ın cevap metni (str)
    """
    # History'yi Gemini formatına çevir
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],  # "user" veya "model"
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    # Config
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    # API çağrısı — retry mantığı
    for attempt in range(3):
        try:
            response = _client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            return response.text or "(boş cevap)"
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt  # 1s, 2s
                print(f"  ⚠ API hatası, {wait}s sonra tekrar: {e}")
                time.sleep(wait)
            else:
                return f"(API hatası: {e})"


# ========== HIZLI TEST ==========
if __name__ == "__main__":
    print("🔑 API key kontrolü...")
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "buraya_kendi_api_keyinizi_yazin":
        print("❌ .env dosyasına geçerli GEMINI_API_KEY yazın!")
        exit(1)

    print("✅ API key bulundu, test ediliyor...\n")
    result = chat(
        system_prompt="Sen yardımcı bir asistansın. Türkçe cevap ver.",
        history=[{"role": "user", "content": "Merhaba, çalışıyor musun?"}],
        temperature=0.5,
    )
    print(f"Gemini cevabı:\n{result}")
