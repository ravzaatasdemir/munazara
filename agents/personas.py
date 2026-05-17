"""
Münazara — Ajan Karakter Tanımları

YAML'dan yüklenir. Prompt düzenlemek için personas.yaml'ı düzenleyin,
bu dosyaya dokunmaya gerek yok.

FIX v2:
- Bigram desteği eklendi: "diferansiyel denklem", "vektörel çarpım" gibi
  çok kelimeli keyword'ler artık doğru eşleşiyor.
- Tek kelimeli keyword'lerde startswith mantığı korundu (Türkçe ek desteği).
"""

import re
import yaml
from pathlib import Path

# ===== YAML yükle =====
_YAML_PATH = Path(__file__).parent / "personas.yaml"

with _YAML_PATH.open(encoding="utf-8") as _f:
    _data = yaml.safe_load(_f)

# Prompt sabitleri
PROF_MAX_WORDS: int = _data["professor"]["max_words"]
STUDENT_MAX_WORDS: int = _data["student"]["max_words"]

PROFESSOR_PROMPT: str = _data["professor"]["prompt"].format(max_words=PROF_MAX_WORDS)
STUDENT_PROMPT: str = _data["student"]["prompt"].format(max_words=STUDENT_MAX_WORDS)
SUMMARY_PROMPT: str = _data["summary"]["prompt"]

# Keyword setleri — tek ve çok kelimeli ayrı tutulur
_KW = _data["topic_keywords"]
_MATH_KEYWORDS: frozenset[str] = frozenset(_KW["math"])
_HISTORY_KEYWORDS: frozenset[str] = frozenset(_KW["history"])
_CS_KEYWORDS: frozenset[str] = frozenset(_KW["cs"])
_ECON_KEYWORDS: frozenset[str] = frozenset(_KW["econ"])


# ===== Token + Bigram bazlı keyword matching =====

def _tokenize(text: str) -> list[str]:
    """Metni küçük harfe çevirip kelime tokenlarına ayırır."""
    return re.findall(r"\w+", text.lower())


def _make_ngrams(tokens: list[str], n: int) -> list[str]:
    """tokens listesinden n-gram'lar üretir."""
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _matches_any(text: str, keywords: frozenset[str]) -> bool:
    """
    Token + bigram bazlı eşleşme.

    Tek kelimeli keyword'ler:
      - Tam eşleşme: 'türev' → 'türev' ✓
      - Türkçe ek: 'integrali' → 'integral' startswith ✓
      - False positive koruması: min 4 karakter örtüşme

    Çok kelimeli keyword'ler (boşluk içerenler):
      - Bigram eşleşmesi: 'diferansiyel denklem' → ['diferansiyel denklem'] ✓
      - startswith ile ek toleransı: 'diferansiyel denklemler' ✓
    """
    tokens = _tokenize(text)

    # Tek kelimeli keyword'ler
    single_kws = {kw for kw in keywords if " " not in kw}
    for token in tokens:
        for kw in single_kws:
            if token == kw:
                return True
            # startswith: Türkçe ek desteği, min 4 karakter örtüşme
            if len(kw) >= 4 and token.startswith(kw):
                return True

    # Çok kelimeli keyword'ler — bigram ve trigram kontrolü
    multi_kws = {kw for kw in keywords if " " in kw}
    if not multi_kws:
        return False

    max_n = max(len(kw.split()) for kw in multi_kws)
    for n in range(2, max_n + 1):
        ngrams = _make_ngrams(tokens, n)
        for ngram in ngrams:
            for kw in multi_kws:
                if len(kw.split()) == n:
                    if ngram == kw or ngram.startswith(kw):
                        return True

    return False


# ===== Açılış prompt seçici =====

def get_opening_prompt(topic: str) -> str:
    """Kavrama göre farklı açılış tarzı döner."""

    if _matches_any(topic, _MATH_KEYWORDS):
        return (
            f'Bir öğrencin sana "{topic}" konusunu sordu. '
            f"Sokratik yöntemle başla: önce öğrenciye kavramın günlük hayatta nerede "
            f"göründüğünü sor ya da sezgisel bir benzetme kur, sonra formal tanımı ver. "
            f"Öğrenciyi düşünmeye zorlayan bir soruyla bitir."
        )

    if _matches_any(topic, _HISTORY_KEYWORDS):
        return (
            f'Bir öğrencin sana "{topic}" konusunu sordu. '
            f"Anlatı odaklı bir açılış yap: dönemin bağlamını çiz, "
            f"ana kavramı o bağlam içinde yerleştir, öğrenciyi o tarihin içine çek. "
            f"Ardından nedensellik sorusu sor."
        )

    if _matches_any(topic, _CS_KEYWORDS):
        return (
            f'Bir öğrencin sana "{topic}" konusunu sordu. '
            f"Teknik kavramı gerçek hayattan bir benzetmeyle aç — ağ protokolü ise "
            f"mektup/posta sistemi gibi. Adım adım nasıl çalıştığını göster, "
            f"sonunda öğrenciyi bir senaryo üzerine düşündür."
        )

    if _matches_any(topic, _ECON_KEYWORDS):
        return (
            f'Bir öğrencin sana "{topic}" konusunu sordu. '
            f"Günlük hayattan somut bir örnek ver — pazar, ekmek fiyatı, döviz. "
            f"Kavramı o örnek üzerinden açıkla. "
            f"Ardından öğrenciye 'peki bu durumda ne olur?' diye sor."
        )

    return (
        f'Bir öğrencin sana "{topic}" konusunu sordu. '
        f"Kavramı sade ve anlaşılır şekilde açıklayarak tartışmayı başlat. "
        f"Öğrencinin seviyesine uygun, merak uyandıracak şekilde anlat."
    )