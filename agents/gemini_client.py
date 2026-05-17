"""
Münazara — Gemini API Wrapper
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from agents.exceptions import APIQuotaError, APIConnectionError, APIKeyError, EmptyResponseError

load_dotenv()

MODEL = "gemini-2.0-flash"  # fix: "gemini-2.5-flash" geçersiz model adıydı
_client = None


def _get_client():
    """Client'ı ilk kullanımda oluştur (lazy loading)"""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "buraya_kendi_api_keyinizi_yazin":
            raise APIKeyError()
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
            if not response.text:
                raise EmptyResponseError()
            return response.text
        except (APIKeyError, APIQuotaError, EmptyResponseError):
            raise
        except Exception as e:
            error_msg = str(e)
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                raise APIQuotaError()
            if attempt < 2:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                raise APIConnectionError(error_msg)


def chat_stream(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
):
    """Gemini'a mesaj gönder, STREAMING cevap al."""
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
    except Exception as e:
        error_msg = str(e)
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            raise APIQuotaError()
        raise APIConnectionError(error_msg)


if __name__ == "__main__":
    try:
        _get_client()
        print("✅ API key bulundu, test ediliyor...\n")
        result = chat(
            system_prompt="Sen yardımcı bir asistansın. Türkçe cevap ver.",
            history=[{"role": "user", "content": "Merhaba, çalışıyor musun?"}],
            temperature=0.5,
        )
        print(f"✅ Test başarılı!\n{result}")
    except Exception as e:
        print(f"❌ {e}")