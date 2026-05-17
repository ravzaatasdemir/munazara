"""
Münazara — Orchestrator
"""

from __future__ import annotations
from typing import Callable, Optional
from agents.gemini_client import chat_stream
from agents.personas import PROFESSOR_PROMPT, STUDENT_PROMPT, get_opening_prompt
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
        self.prof_history: list[dict[str, str]] = []
        self.student_history: list[dict[str, str]] = []
        self.messages: list[dict[str, str]] = []
        self.is_started: bool = False
        self.is_finished: bool = False
        self.waiting_for_user: bool = False
        self.last_error: Optional[str] = None
        self._pending_context: Optional[str] = None

    def start_debate(self, on_chunk: ChunkCallback = None, on_complete: CompleteCallback = None) -> bool:
        opening = get_opening_prompt(self.topic)
        self.prof_history.append({"role": "user", "content": opening})
        try:
            success = self._professor_speaks(on_chunk, on_complete)
            if success:
                self.is_started = True
                self.waiting_for_user = True
                self.current_round = 1
            return success
        except MunazaraError as e:
            self.last_error = str(e)
            return False

    def user_skip_turn(self, on_chunk: ChunkCallback = None, on_complete: CompleteCallback = None) -> bool:
        if not self.waiting_for_user:
            return False
        try:
            prof_last = self.prof_history[-1]["content"]
            student_success = self._student_speaks(prof_last, on_chunk, on_complete)
            if not student_success:
                self.is_finished = True
                return False
            student_last = self.student_history[-1]["content"]
            self.prof_history.append({"role": "user", "content": student_last})
            prof_success = self._professor_speaks(on_chunk, on_complete)
            if not prof_success:
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

    def user_ask_question(self, question: str, on_chunk: ChunkCallback = None, on_complete: CompleteCallback = None) -> bool:
        if not self.waiting_for_user:
            return False
        question = self._sanitize_input(question)
        context = f"[Tartışma sırasında başka bir öğrenci '{question}' diye sordu]\n\nBu soruyu yanıtla."
        self.prof_history.append({"role": "user", "content": context})
        try:
            success = self._professor_speaks(on_chunk, on_complete)
            if success:
                prof_response = self.prof_history[-1]["content"]
                self._pending_context = (
                    f"[Az önce başka bir öğrenci (kullanıcı) '{question}' diye sordu, "
                    f"Profesör ona da açıkladı: '{prof_response[:120]}...']"
                )
                self.current_round += 1
                if self.current_round >= self.max_rounds:
                    self.is_finished = True
                    self.waiting_for_user = False
            else:
                self.is_finished = True
                self.waiting_for_user = False
            return success
        except MunazaraError as e:
            self.last_error = str(e)
            self.is_finished = True
            self.waiting_for_user = False
            return False

    def _professor_speaks(self, on_chunk: ChunkCallback = None, on_complete: CompleteCallback = None) -> str | bool:
        full_response: str = ""
        for chunk in chat_stream(PROFESSOR_PROMPT, self.prof_history, PROF_TEMP):
            if chunk is None:
                return False
            full_response += chunk
            if on_chunk:
                on_chunk("professor", chunk)
        full_response = full_response.strip()
        if not full_response:
            return False
        self.prof_history.append({"role": "model", "content": full_response})
        self.messages.append({"role": "professor", "content": full_response})
        if on_complete:
            on_complete("professor", full_response)
        return full_response

    def _student_speaks(self, prof_last_message: str, on_chunk: ChunkCallback = None, on_complete: CompleteCallback = None) -> str | bool:
        if self.current_round < 2:
            level = "yüzeysel"
        elif self.current_round < 4:
            level = "orta"
        else:
            level = "derin"

        context = f"[Tur {self.current_round}/{self.max_rounds}. Soru seviyen: {level}]"
        if self._pending_context:
            context += f"\n{self._pending_context}"
            self._pending_context = None
        context += f"\n\n{prof_last_message}"

        self.student_history.append({"role": "user", "content": context})
        full_response: str = ""
        for chunk in chat_stream(STUDENT_PROMPT, self.student_history, STUDENT_TEMP):
            if chunk is None:
                return False
            full_response += chunk
            if on_chunk:
                on_chunk("student", chunk)
        full_response = full_response.strip()
        if not full_response:
            return False
        self.student_history.append({"role": "model", "content": full_response})
        self.messages.append({"role": "student", "content": full_response})
        if on_complete:
            on_complete("student", full_response)
        return full_response

    def _sanitize_input(self, text: str) -> str:
        """Prompt injection koruması"""
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