"""
Münazara — Gemini API Wrapper

Düzeltmeler:
- chat_stream() artık chat() ile aynı retry + exponential backoff mantığına sahip.
  Önceki versiyonda streaming path'inde retry yoktu; tüm orchestrator akışı
  korumasız bırakılıyordu.
- Streaming retry'da generator semantiği bozulmaz: hata olursa yeni bir stream
  açılır, önceki chunk'lar tekrar yield edilmez (caller tarafı placeholder'ı
  sıfırlamalı — UI zaten spinner kullanıyor, bu kabul edilebilir).
"""

import os
import time
import threading
from dotenv import load_dotenv
from google import genai
from google.genai import types
from agents.exceptions import APIQuotaError, APIConnectionError, APIKeyError, EmptyResponseError

load_dotenv()

MODEL = "gemini-2.0-flash"
_client = None
_client_lock = threading.Lock()

MAX_RETRIES = 3


def _get_client():
    """Client'ı ilk kullanımda oluştur (lazy loading, thread-safe)."""
    global _client
    with _client_lock:
        if _client is None:
            api_key = os.getenv("GEMINI_API_KEY")

            if not api_key or api_key == "buraya_kendi_api_keyinizi_yazin":
                try:
                    import streamlit as st
                    api_key = st.secrets.get("GEMINI_API_KEY", None)
                except Exception:
                    pass

            if not api_key or api_key == "buraya_kendi_api_keyinizi_yazin":
                raise APIKeyError()

            _client = genai.Client(api_key=api_key)
    return _client


def _build_contents(history: list[dict]) -> list[types.Content]:
    return [
        types.Content(
            role=msg["role"],
            parts=[types.Part.from_text(text=msg["content"])],
        )
        for msg in history
    ]


def _build_config(
    system_prompt: str,
    temperature: float,
    max_tokens: int,
) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )


def chat(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
):
    """Gemini'a mesaj gönder, cevap al."""
    contents = _build_contents(history)
    config = _build_config(system_prompt, temperature, max_tokens)

    for attempt in range(MAX_RETRIES):
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
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
            else:
                raise APIConnectionError(error_msg)


def chat_stream(
    system_prompt: str,
    history: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1500,
):
    """
    Gemini'a mesaj gönder, STREAMING cevap al.

    Retry mantığı: her denemede yeni bir stream açılır.
    Kota hatası → hemen yükselt (retry faydasız).
    Diğer hatalar → exponential backoff ile MAX_RETRIES kez dene.
    """
    contents = _build_contents(history)
    config = _build_config(system_prompt, temperature, max_tokens)

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            stream = _get_client().models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=config,
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
            return  # başarıyla bitti, döngüden çık

        except (APIKeyError, EmptyResponseError):
            raise  # retry yok

        except Exception as e:
            error_msg = str(e)
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                raise APIQuotaError()  # retry yok

            last_error = APIConnectionError(error_msg)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s
            # son denemeyse döngü bitince raise

    raise last_error


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