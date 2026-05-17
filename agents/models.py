"""
Münazara — Veri Modelleri

dict[str, str] yerine tip güvenli dataclass'lar.
"""

from dataclasses import dataclass


@dataclass
class Message:
    """UI messages listesi için — UI'a gösterilen mesajlar."""
    role: str      # "professor" | "student" | "user" | "system"
    content: str


@dataclass
class HistoryEntry:
    """shared_history için — ajan perspektifini bilir."""
    speaker: str   # "professor" | "student" | "system" | "user_question"
    content: str