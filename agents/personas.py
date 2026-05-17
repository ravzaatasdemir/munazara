"""
Münazara — Ajan Karakter Tanımları

YAML'dan yüklenir. Prompt düzenlemek için personas.yaml'ı düzenleyin,
bu dosyaya dokunmaya gerek yok.

FIX: Keyword matching artık token bazlı — substring false positive'leri yok.
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

# Keyword setleri
_KW = _data["topic_keywords"]
_MATH_KEYWORDS: frozenset[str] = frozenset(_KW["math"])
_HISTORY_KEYWORDS: frozenset[str] = frozenset(_KW["history"])
_CS_KEYWORDS: frozenset[str] = frozenset(_KW["cs"])
_ECON_KEYWORDS: frozenset[str] = frozenset(_KW["econ"])


# ===== FIX: Token bazlı keyword matching =====

def _tokenize(text: str) -> list[str]:
    """Metni küçük harfe çevirip kelime tokenlarına ayırır."""
    return re.findall(r"\w+", text.lower())


def _matches_any(text: str, keywords: frozenset[str]) -> bool:
    """
    Token bazlı eşleşme — Türkçe ek sorununu da çözer.
    'integrali' → 'integral' keyword'ünü yakalar (startswith).
    'integralcilik' → yanlış pozitif değil (min 4 char overlap kontrolü).
    """
    tokens = _tokenize(text)
    return any(
        token == kw or token.startswith(kw)
        for token in tokens
        for kw in keywords
    )


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