"""
Münazara — Gemini API Wrapper

chat(system_prompt, history, temperature) → response text
chat_stream(system_prompt, history, temperature) → generator (streaming)
Kişi A bu dosyayı yönetir.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "gemini-2.5-flash"

# Lazy loading — client ilk kullanımda oluşturulur
_client = None


def _get_client():
    """Client'ı ilk kullanımda oluştur (lazy loading)"""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "buraya_kendi_api_keyinizi_yazin":
            raise ValueError(
                "GEMINI_API_KEY bulunamadı! "
                ".env dosyasına geçerli bir API key yazın."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def chat(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
):
    """Gemini'a mesaj gönder, cevap al."""
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    for attempt in range(3):
        try:
            response = _get_client().models.generate_content(
                model=MODEL,
                contents=contents,
                config=config,
            )
            return response.text or "(boş cevap)"
        except ValueError as e:
            print(f"\n❌ {e}")
            return None
        except Exception as e:
            error_msg = str(e)
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                print(f"\n⚠️ API kotası bitti.")
                return None
            if attempt < 2:
                wait = 2 ** attempt
                print(f"  ⚠ API hatası, {wait}s sonra tekrar: {e}")
                time.sleep(wait)
            else:
                print(f"\n❌ API hatası (3 deneme sonrası): {e}\n")
                return None


def chat_stream(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
):
    """Gemini'a mesaj gönder, STREAMING cevap al (kelime kelime)."""
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["content"])],
            )
        )

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    try:
        stream = _get_client().models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=config,
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except ValueError as e:
        print(f"\n❌ {e}")
        yield None
    except Exception as e:
        error_msg = str(e)
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            print(f"\n⚠️ API kotası bitti.")
        else:
            print(f"\n❌ Streaming hatası: {e}")
        yield None


# ========== HIZLI TEST ==========
if __name__ == "__main__":
    print("🔑 API key kontrolü...")
    
    try:
        client = _get_client()
        print("✅ API key bulundu, test ediliyor...\n")
    except ValueError as e:
        print(f"❌ {e}")
        exit(1)

    result = chat(
        system_prompt="Sen yardımcı bir asistansın. Türkçe cevap ver.",
        history=[{"role": "user", "content": "Merhaba, çalışıyor musun?"}],
        temperature=0.5,
    )
    
    if result is None:
        print("❌ Test başarısız.")
    else:
        print(f"✅ Test başarılı!\n{result}")