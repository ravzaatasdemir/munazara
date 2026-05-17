"""
Münazara — Orchestrator (v2: shared history)

Değişiklikler:
- prof_history + student_history → tek shared_history
  Her ajan tüm konuşmayı görür; kendi mesajları "model", diğerleri "user" olarak iletilir.
- Ardışık aynı-role mesajları otomatik birleştirilir (Gemini API gereksinimi).
- _pending_context kaldırıldı: öğrenci zaten tam geçmişi gördüğünden gereksiz.
- generate_summary(): tartışma bitince öğrenme özeti üretir.
"""

from __future__ import annotations
from typing import Callable, Optional
from agents.gemini_client import chat, chat_stream
from agents.personas import PROFESSOR_PROMPT, STUDENT_PROMPT, SUMMARY_PROMPT, get_opening_prompt
from agents.exceptions import MunazaraError

PROF_TEMP: float = 0.3
STUDENT_TEMP: float = 0.7

ChunkCallback = Optional[Callable[[str, str], None]]
CompleteCallback = Optional[Callable[[str, str], None]]


class DebateOrchestrator:
    def __init__(self, topic: str, max_rounds: int = 5) -> None:
        self.topic: str = topic
        self.max_rounds: int = max_rounds
        self.current_round: int = 0

        # Ortak geçmiş: her mesaj {"speaker": str, "content": str}
        # speaker değerleri: "professor" | "student" | "system" | "user_question"
        self.shared_history: list[dict[str, str]] = []

        # UI için ayrı liste: {"role": str, "content": str}
        self.messages: list[dict[str, str]] = []

        self.is_started: bool = False
        self.is_finished: bool = False
        self.waiting_for_user: bool = False
        self.last_error: Optional[str] = None
        self.summary: Optional[str] = None
        self.summary_error: Optional[str] = None

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def start_debate(
        self,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        opening = get_opening_prompt(self.topic)
        self.shared_history.append({"speaker": "system", "content": opening})
        try:
            success = self._professor_speaks(on_chunk, on_complete)
            if success:
                self.is_started = True
                self.waiting_for_user = True
                self.current_round = 1
            return success
        except MunazaraError as e:
            self.last_error = str(e)
            self.is_finished = True
            return False
        except Exception as e:
            self.last_error = f"Beklenmeyen hata: {e}"
            self.is_finished = True
            return False

    def user_skip_turn(
        self,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        if not self.waiting_for_user:
            return False
        try:
            if not self._student_speaks(on_chunk, on_complete):
                self.is_finished = True
                return False

            if not self._professor_speaks(on_chunk, on_complete):
                self.is_finished = True
                return False

            self.current_round += 1
            if self.current_round >= self.max_rounds:
                self.is_finished = True
                self.waiting_for_user = False
            return True
        except MunazaraError as e:
            self.last_error = str(e)
            self.is_finished = True
            return False
        except Exception as e:
            self.last_error = f"Beklenmeyen hata: {e}"
            self.is_finished = True
            self.waiting_for_user = False
            return False

    def user_ask_question(
        self,
        question: str,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        if not self.waiting_for_user:
            return False

        question = self._sanitize_input(question)
        context = (
            f"[Tartışmayı izleyen bir kullanıcı sana şunu sordu: '{question}']\n\n"
            f"Bu soruyu doğrudan yanıtla, ardından Kamil ile tartışmaya geri dön."
        )
        self.shared_history.append({"speaker": "user_question", "content": context})

        try:
            if not self._professor_speaks(on_chunk, on_complete):
                self.is_finished = True
                self.waiting_for_user = False
                return False

            self.current_round += 1
            if self.current_round >= self.max_rounds:
                self.is_finished = True
                self.waiting_for_user = False
            return True
        except MunazaraError as e:
            self.last_error = str(e)
            self.is_finished = True
            self.waiting_for_user = False
            return False
        except Exception as e:
            self.last_error = f"Beklenmeyen hata: {e}"
            self.is_finished = True
            self.waiting_for_user = False
            return False

    def generate_summary(self) -> Optional[str]:
        """
        Tartışma bitince öğrenme özeti üretir.
        Sadece professor ve student mesajlarını kullanır.
        """
        lines = []
        for msg in self.messages:
            if msg["role"] in ("professor", "student"):
                label = "PROFESÖR" if msg["role"] == "professor" else "KAMİL"
                lines.append(f"[{label}]: {msg['content']}")

        if not lines:
            return None

        transcript = "\n\n".join(lines)
        try:
            result = chat(
                system_prompt=SUMMARY_PROMPT,
                history=[{"role": "user", "content": f"Tartışma transkripi:\n\n{transcript}"}],
                temperature=0.3,
                max_tokens=400,
            )
            self.summary = result
            self.summary_error = None
            return result
        except Exception as e:
            self.summary_error = str(e)
            return None

    # ------------------------------------------------------------------
    # İÇ METODLAR
    # ------------------------------------------------------------------

    def _build_history_for(self, agent: str) -> list[dict[str, str]]:
        """
        Shared history'yi belirtilen ajan perspektifine çevirir:
          - Ajanın kendi mesajları  → role: "model"
          - Diğer tüm mesajlar     → role: "user"

        Gemini API ardışık aynı role'e izin vermediğinden,
        yan yana gelen aynı-role mesajlar içerik birleştirilerek tek mesaja indirilir.
        """
        raw: list[dict[str, str]] = []
        for msg in self.shared_history:
            role = "model" if msg["speaker"] == agent else "user"
            raw.append({"role": role, "content": msg["content"]})

        # Ardışık aynı-role mesajları birleştir
        merged: list[dict[str, str]] = []
        for item in raw:
            if merged and merged[-1]["role"] == item["role"]:
                merged[-1] = {
                    "role": merged[-1]["role"],
                    "content": merged[-1]["content"] + "\n\n" + item["content"],
                }
            else:
                merged.append(dict(item))
        return merged

    def _professor_speaks(
        self,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        history = self._build_history_for("professor")
        full_response: str = ""

        for chunk in chat_stream(PROFESSOR_PROMPT, history, PROF_TEMP):
            if chunk is None:
                return False
            full_response += chunk
            if on_chunk:
                on_chunk("professor", chunk)

        full_response = full_response.strip()
        if not full_response:
            return False

        self.shared_history.append({"speaker": "professor", "content": full_response})
        self.messages.append({"role": "professor", "content": full_response})
        if on_complete:
            on_complete("professor", full_response)
        return True

    def _student_speaks(
        self,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        if self.current_round < 2:
            level = "yüzeysel"
        elif self.current_round < 4:
            level = "orta"
        else:
            level = "derin"

        history = self._build_history_for("student")

        # Tur bağlamını son mesaja ekle — shared_history'yi kirletmez
        round_ctx = f"[Tur {self.current_round}/{self.max_rounds} — soru derinliği: {level}]"
        if history:
            history[-1] = {
                "role": history[-1]["role"],
                "content": round_ctx + "\n\n" + history[-1]["content"],
            }
        else:
            history.append({"role": "user", "content": round_ctx})

        full_response: str = ""
        for chunk in chat_stream(STUDENT_PROMPT, history, STUDENT_TEMP):
            if chunk is None:
                return False
            full_response += chunk
            if on_chunk:
                on_chunk("student", chunk)

        full_response = full_response.strip()
        if not full_response:
            return False

        self.shared_history.append({"speaker": "student", "content": full_response})
        self.messages.append({"role": "student", "content": full_response})
        if on_complete:
            on_complete("student", full_response)
        return True

    def _sanitize_input(self, text: str) -> str:
        """Prompt injection koruması."""
        dangerous_patterns: list[str] = [
            "talimatları unut", "ignore instructions", "ignore previous",
            "sistem promptunu", "system prompt", "karakterinden çık",
            "role play", "sen artık", "you are now", "DAN mode",
            "jailbreak", "forget everything", "her şeyi unut", "önceki kuralları",
        ]
        text_lower = text.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in text_lower:
                return "[Bu soru güvenlik filtresine takıldı. Lütfen konuyla ilgili bir soru sorun.]"
        if len(text) > 500:
            text = text[:500]
        return text