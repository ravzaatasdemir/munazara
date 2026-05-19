"""
Münazara — Gemini API Wrapper

Düzeltmeler:
- chat_stream() retry mantığı güvenli hale getirildi:
  Chunks yield edilmeye başlandıktan sonra retry yapılmaz.
  Neden: stream başlar, birkaç chunk gelir, sonra hata olursa
  retry yeni stream açar ve orchestrator aynı full_response'a
  eklemeye devam eder — cümleler çift yazılır. Düzeltme:
  chunks_yielded > 0 iken hata olursa retry değil, doğrudan raise.
  Retry yalnızca bağlantı hiç kurulamadıysa (chunks_yielded == 0)
  anlamlıdır.
- _build_contents ve _build_config ortak helper'lara çıkarıldı.
"""

import os
import time
import threading
from dotenv import load_dotenv
from google import genai
from google.genai import types
from agents.exceptions import (
    APIQuotaError,
    APIConnectionError,
    APIKeyError,
    EmptyResponseError,
)

load_dotenv()

MODEL = "gemini-2.5-flash"
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

    Retry politikası:
    - chunks_yielded == 0: bağlantı hiç kurulamadı → exponential backoff ile retry.
    - chunks_yielded > 0: stream başlamış, mid-stream hata → retry YOK, raise.
      Neden: retry açılırsa orchestrator'daki full_response'a yeni stream'in
      chunk'ları eklenir ve içerik çift yazılır. Bağlantı koparsa caller'ın
      hata işlemcisi devreye girer (is_finished = True).

    Kota hatası (429) her durumda anında raise edilir.
    """
    contents = _build_contents(history)
    config = _build_config(system_prompt, temperature, max_tokens)

    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES):
        chunks_yielded = 0
        try:
            stream = _get_client().models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=config,
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
                    chunks_yielded += 1
            return  # başarıyla tamamlandı

        except (APIKeyError, EmptyResponseError):
            raise  # retry yok

        except Exception as e:
            error_msg = str(e)
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                raise APIQuotaError()  # retry yok

            if chunks_yielded > 0:
                # Stream başlamıştı, mid-stream koptu.
                # Retry açmak içerik bozulmasına yol açar → raise.
                raise APIConnectionError(error_msg)

            # Henüz hiç chunk gelmedi; bağlantı kurulamadı → retry.
            last_error = APIConnectionError(error_msg)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # 1s, 2s

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