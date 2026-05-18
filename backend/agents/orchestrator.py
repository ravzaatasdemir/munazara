"""
Münazara — Orchestrator (v5)

Değişiklikler v4 → v5:
- max_user_questions parametresi eklendi (varsayılan: 3).
  user_ask_question() artık bu limiti aşınca False döner ve
  last_error'a kullanıcıya gösterilebilir bir mesaj yazar.
- questions_remaining property eklendi (UI için).
- generate_summary() transcript'i MAX_TRANSCRIPT_CHARS ile kırpar;
  uzun tartışmalarda Gemini token limitini aşmaz.
- user_skip_turn() çağrısında waiting_for_user False → True düzeltmesi:
  limit dolmadıkça beklemeye devam edilir.
"""

from __future__ import annotations
from typing import Callable, Optional
from agents.gemini_client import chat_stream
from agents.models import Message, HistoryEntry
from agents.personas import PROFESSOR_PROMPT, STUDENT_PROMPT, SUMMARY_PROMPT, get_opening_prompt
from agents.exceptions import MunazaraError

PROF_TEMP: float = 0.3
STUDENT_TEMP: float = 0.7
MAX_TRANSCRIPT_CHARS: int = 4000  # ~1000 token — Gemini için güvenli üst sınır

ChunkCallback = Optional[Callable[[str, str], None]]
CompleteCallback = Optional[Callable[[str, str], None]]


class DebateOrchestrator:
    def __init__(
        self,
        topic: str,
        max_rounds: int = 5,
        max_user_questions: int = 3,
    ) -> None:
        self.topic: str = topic
        self.max_rounds: int = max_rounds
        self.max_user_questions: int = max_user_questions
        self.current_round: int = 0
        self.user_question_count: int = 0

        self.shared_history: list[HistoryEntry] = []
        self.messages: list[Message] = []

        self.is_started: bool = False
        self.is_finished: bool = False
        self.waiting_for_user: bool = False
        self.last_error: Optional[str] = None
        self.summary: Optional[str] = None
        self.summary_error: Optional[str] = None

    # ------------------------------------------------------------------
    # PROPERTY'LER
    # ------------------------------------------------------------------

    @property
    def questions_remaining(self) -> int:
        return max(0, self.max_user_questions - self.user_question_count)

    @property
    def can_ask_question(self) -> bool:
        return self.waiting_for_user and self.questions_remaining > 0

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def start_debate(
        self,
        on_chunk: ChunkCallback = None,
        on_complete: CompleteCallback = None,
    ) -> bool:
        opening = get_opening_prompt(self.topic)
        self.shared_history.append(HistoryEntry(speaker="system", content=opening))
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
            else:
                self.waiting_for_user = True  # FIX: açıkça True yap
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

        # Soru limiti kontrolü
        if self.user_question_count >= self.max_user_questions:
            self.last_error = (
                f"Soru hakkınız bitti ({self.max_user_questions}/{self.max_user_questions}). "
                f"Tartışmaya devam etmek için 'Turumu atla' butonunu kullanın."
            )
            return False

        question = self._sanitize_input(question)
        context = (
            f"[Tartışmayı izleyen bir kullanıcı sana şunu sordu: '{question}']\n\n"
            f"Bu soruyu doğrudan yanıtla, ardından Kamil ile tartışmaya geri dön."
        )
        self.shared_history.append(HistoryEntry(speaker="user_question", content=context))

        try:
            if not self._professor_speaks(on_chunk, on_complete):
                self.is_finished = True
                self.waiting_for_user = False
                return False

            self.user_question_count += 1

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

    def generate_summary(
        self,
        on_chunk: ChunkCallback = None,
    ) -> Optional[str]:
        lines = []
        for msg in self.messages:
            if msg.role in ("professor", "student"):
                label = "PROFESÖR" if msg.role == "professor" else "KAMİL"
                lines.append(f"[{label}]: {msg.content}")

        if not lines:
            return None

        transcript = "\n\n".join(lines)

        # Token limit koruması: çok uzun transcript'leri kırp
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = transcript[-MAX_TRANSCRIPT_CHARS:]
            # Yarım cümleden başlamamak için ilk satır sonuna kadar at
            first_newline = transcript.find("\n")
            if first_newline > 0:
                transcript = transcript[first_newline + 1:]
            transcript = "[...tartışmanın önceki kısımları kısaltıldı...]\n\n" + transcript

        full_response = ""

        try:
            for chunk in chat_stream(
                system_prompt=SUMMARY_PROMPT,
                history=[{"role": "user", "content": f"Tartışma transkripi:\n\n{transcript}"}],
                temperature=0.3,
                max_tokens=400,
            ):
                full_response += chunk
                if on_chunk:
                    on_chunk("summary", chunk)

            self.summary = full_response.strip()
            self.summary_error = None
            return self.summary
        except Exception as e:
            self.summary_error = str(e)
            return None

    # ------------------------------------------------------------------
    # İÇ METODLAR
    # ------------------------------------------------------------------

    def _build_history_for(self, agent: str) -> list[dict[str, str]]:
        """
        Shared history'yi Gemini API formatına çevirir (dict listesi).
        Ajanın kendi mesajları → 'model', diğerleri → 'user'.
        Ardışık aynı-role mesajlar birleştirilir.
        """
        raw: list[dict[str, str]] = []
        for entry in self.shared_history:
            role = "model" if entry.speaker == agent else "user"
            raw.append({"role": role, "content": entry.content})

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

        try:
            for chunk in chat_stream(PROFESSOR_PROMPT, history, PROF_TEMP):
                full_response += chunk
            if on_chunk:
                on_chunk("professor", chunk)
        except Exception as e:
            self.last_error = f"Beklenmeyen hata: {e}"
            return False

        full_response = full_response.strip()
        if not full_response:
            return False

        self.shared_history.append(HistoryEntry(speaker="professor", content=full_response))
        self.messages.append(Message(role="professor", content=full_response))
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

        self.shared_history.append(HistoryEntry(speaker="student", content=full_response))
        self.messages.append(Message(role="student", content=full_response))
        if on_complete:
            on_complete("student", full_response)
        return True

    def _sanitize_input(self, text: str) -> str:
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