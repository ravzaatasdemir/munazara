"""
Münazara — Integration Testler (v4)

Değişiklikler:
- msg["role"] → msg.role, msg["speaker"] → msg.speaker (dataclass uyumu)
- TestKeywordMatching sınıfı eklendi (FIX: token bazlı eşleşme)
"""

import pytest
from unittest.mock import patch
from agents.orchestrator import DebateOrchestrator
from agents.personas import get_opening_prompt, _matches_any, _MATH_KEYWORDS, _CS_KEYWORDS


# ===== Mock helpers =====

def _make_stream(text: str):
    for word in text.split():
        yield word + " "


def _patch_stream(prof_responses: list[str], student_responses: list[str]):
    prof_iter = iter(prof_responses)
    student_iter = iter(student_responses)

    def _fake_stream(system_prompt, history, temperature=0.7, max_tokens=1500):
        from agents.personas import PROFESSOR_PROMPT
        if system_prompt == PROFESSOR_PROMPT:
            text = next(prof_iter, "Anladım.")
        else:
            text = next(student_iter, "Peki hocam.")
        return _make_stream(text)

    return patch("agents.orchestrator.chat_stream", side_effect=_fake_stream)


# ===== Ajan davranış testleri =====

class TestProfessorBehavior:
    def test_professor_speaks_on_start(self):
        with _patch_stream(
            prof_responses=["Türev, anlık değişim hızıdır. Siz ne düşünüyorsunuz?"],
            student_responses=[],
        ):
            o = DebateOrchestrator("Türev nedir", max_rounds=3)
            success = o.start_debate()

        assert success
        assert len(o.messages) == 1
        assert o.messages[0].role == "professor"

    def test_professor_response_in_shared_history(self):
        with _patch_stream(prof_responses=["Kavramı açıklayayım."], student_responses=[]):
            o = DebateOrchestrator("Fotosentez", max_rounds=3)
            o.start_debate()

        speakers = [e.speaker for e in o.shared_history]
        assert "professor" in speakers

    def test_professor_sees_student_history(self):
        with _patch_stream(
            prof_responses=["İlk açıklama.", "İkinci açıklama."],
            student_responses=["Anlamadım hocam, neden öyle?"],
        ):
            o = DebateOrchestrator("Newton", max_rounds=3)
            o.start_debate()
            o.user_skip_turn()

        prof_view = o._build_history_for("professor")
        all_content = " ".join(m["content"] for m in prof_view)
        assert "Anlamadım" in all_content

    def test_user_question_reaches_professor(self):
        with _patch_stream(
            prof_responses=["İlk açıklama.", "Kullanıcı sorusuna cevap."],
            student_responses=[],
        ):
            o = DebateOrchestrator("Bayes", max_rounds=5)
            o.start_debate()
            o.user_ask_question("Bayes günlük hayatta ne işe yarar?")

        prof_view = o._build_history_for("professor")
        all_content = " ".join(m["content"] for m in prof_view)
        assert "Bayes günlük hayatta" in all_content


class TestStudentBehavior:
    def test_student_speaks_on_skip(self):
        with _patch_stream(
            prof_responses=["Açıklama.", "Devam."],
            student_responses=["Peki hocam ama neden?"],
        ):
            o = DebateOrchestrator("Limit", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        roles = [m.role for m in o.messages]
        assert "student" in roles

    def test_student_sees_professor_history(self):
        with _patch_stream(prof_responses=["Türev şöyle çalışır."], student_responses=[]):
            o = DebateOrchestrator("Türev", max_rounds=3)
            o.start_debate()

        student_view = o._build_history_for("student")
        all_content = " ".join(m["content"] for m in student_view)
        assert "Türev şöyle çalışır" in all_content

    def test_student_sees_user_question_context(self):
        with _patch_stream(
            prof_responses=["İlk açıklama.", "Kullanıcı sorusuna cevap.", "Devam."],
            student_responses=["İyi soru hocam, ben de merak ediyordum."],
        ):
            o = DebateOrchestrator("TCP", max_rounds=5)
            o.start_debate()
            o.user_ask_question("Handshake neden 3 adım?")
            o.user_skip_turn()

        student_view = o._build_history_for("student")
        all_content = " ".join(m["content"] for m in student_view)
        assert "Handshake neden 3 adım" in all_content


class TestDebateFlow:
    def test_full_round_increments(self):
        with _patch_stream(
            prof_responses=["A.", "B.", "C."],
            student_responses=["a?", "b?"],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            assert o.current_round == 1
            o.user_skip_turn()
            assert o.current_round == 2
            o.user_skip_turn()
            assert o.current_round == 3

    def test_finishes_at_max_rounds(self):
        with _patch_stream(
            prof_responses=["A.", "B.", "C."],
            student_responses=["a?", "b?"],
        ):
            o = DebateOrchestrator("Test", max_rounds=2)
            o.start_debate()
            o.user_skip_turn()

        assert o.is_finished
        assert not o.waiting_for_user

    def test_messages_order_professor_student_professor(self):
        with _patch_stream(
            prof_responses=["Prof 1.", "Prof 2."],
            student_responses=["Student 1."],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        roles = [m.role for m in o.messages]
        assert roles == ["professor", "student", "professor"]

    def test_shared_history_grows_correctly(self):
        with _patch_stream(
            prof_responses=["Prof 1.", "Prof 2."],
            student_responses=["Student 1."],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        speakers = [e.speaker for e in o.shared_history]
        assert speakers == ["system", "professor", "student", "professor"]

    def test_no_skip_when_not_waiting(self):
        o = DebateOrchestrator("Test", max_rounds=3)
        assert o.user_skip_turn() is False

    def test_no_question_when_not_waiting(self):
        o = DebateOrchestrator("Test", max_rounds=3)
        assert o.user_ask_question("Soru?") is False


class TestRoundCounting:
    def test_user_questions_dont_consume_rounds(self):
        with _patch_stream(
            prof_responses=["A.", "Cevap 1.", "Cevap 2.", "B."],
            student_responses=["a?"],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            assert o.current_round == 1

            o.user_ask_question("Soru 1?")
            assert o.current_round == 1
            assert o.user_question_count == 1

            o.user_ask_question("Soru 2?")
            assert o.current_round == 1
            assert o.user_question_count == 2

            o.user_skip_turn()
            assert o.current_round == 2
            assert o.user_question_count == 2

    def test_debate_doesnt_finish_early_due_to_questions(self):
        with _patch_stream(
            prof_responses=["A.", "Q1.", "Q2.", "Q3.", "B.", "C.", "D.", "E."],
            student_responses=["a?", "b?", "c?", "d?"],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            o.user_ask_question("Soru 1?")
            o.user_ask_question("Soru 2?")
            o.user_ask_question("Soru 3?")
            assert not o.is_finished

            o.user_skip_turn()
            o.user_skip_turn()
            o.user_skip_turn()
            assert not o.is_finished

            o.user_skip_turn()
            assert o.is_finished

    def test_question_count_tracked_separately(self):
        with _patch_stream(prof_responses=["A.", "Q1.", "Q2."], student_responses=[]):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            assert o.user_question_count == 0
            o.user_ask_question("Bir?")
            assert o.user_question_count == 1
            o.user_ask_question("İki?")
            assert o.user_question_count == 2


class TestSummaryStreaming:
    def test_generate_summary_calls_on_chunk(self):
        with _patch_stream(prof_responses=["Açıklama."], student_responses=["Soru?"]):
            o = DebateOrchestrator("Test", max_rounds=3)
            o.start_debate()
            o.messages.append(__import__("agents.models", fromlist=["Message"]).Message(role="student", content="Soru?"))

        chunks_received = []

        def fake_stream(system_prompt, history, **kwargs):
            yield "Kavram "
            yield "özeti "
            yield "burada."

        with patch("agents.orchestrator.chat_stream", side_effect=fake_stream):
            result = o.generate_summary(
                on_chunk=lambda role, chunk: chunks_received.append(chunk)
            )

        assert len(chunks_received) == 3
        assert result == "Kavram özeti burada."

    def test_generate_summary_without_callback(self):
        with _patch_stream(prof_responses=["Açıklama."], student_responses=[]):
            o = DebateOrchestrator("Test", max_rounds=3)
            o.start_debate()
            o.messages.append(__import__("agents.models", fromlist=["Message"]).Message(role="student", content="Soru?"))

        def fake_stream(system_prompt, history, **kwargs):
            yield "Özet metni."

        with patch("agents.orchestrator.chat_stream", side_effect=fake_stream):
            result = o.generate_summary()

        assert result == "Özet metni."

    def test_generate_summary_empty_messages(self):
        o = DebateOrchestrator("Test", max_rounds=3)
        assert o.generate_summary() is None

    def test_generate_summary_stores_result(self):
        with _patch_stream(prof_responses=["A."], student_responses=[]):
            o = DebateOrchestrator("Test", max_rounds=3)
            o.start_debate()
            o.messages.append(__import__("agents.models", fromlist=["Message"]).Message(role="student", content="B."))

        def fake_stream(system_prompt, history, **kwargs):
            yield "Sonuç."

        with patch("agents.orchestrator.chat_stream", side_effect=fake_stream):
            o.generate_summary()

        assert o.summary == "Sonuç."
        assert o.summary_error is None


class TestKeywordMatching:
    """FIX: Token bazlı keyword matching testleri."""

    def test_exact_match(self):
        assert _matches_any("türev nedir", _MATH_KEYWORDS)

    def test_turkish_suffix_match(self):
        """'integrali' → 'integral' keyword'ünü yakalamalı."""
        assert _matches_any("integrali anlat", _MATH_KEYWORDS)

    def test_uppercase_insensitive(self):
        assert _matches_any("TÜREV NEDİR", _MATH_KEYWORDS)

    def test_no_false_positive_unrelated(self):
        assert not _matches_any("fotosentez nedir", _MATH_KEYWORDS)

    def test_cs_keyword_with_suffix(self):
        assert _matches_any("handshake'i açıkla", _CS_KEYWORDS)

    def test_opening_prompt_routes_correctly(self):
        math_prompt = get_opening_prompt("integrali anlat")
        assert "Sokratik" in math_prompt

        cs_prompt = get_opening_prompt("TCP protokolünü açıkla")
        assert "benzetme" in cs_prompt

        generic_prompt = get_opening_prompt("bilinç nedir")
        assert "sade" in generic_prompt


class TestErrorRecovery:
    def test_api_error_sets_last_error(self):
        with patch("agents.orchestrator.chat_stream", side_effect=Exception("Bağlantı kesildi")):
            o = DebateOrchestrator("Test", max_rounds=3)
            success = o.start_debate()

        assert not success
        assert o.last_error is not None
        assert "Bağlantı kesildi" in o.last_error or "Beklenmeyen" in o.last_error
        assert o.is_finished

    def test_session_state_consistent_after_error(self):
        with _patch_stream(prof_responses=["İlk açıklama."], student_responses=[]):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()

        with patch("agents.orchestrator.chat_stream", side_effect=Exception("Timeout")):
            o.user_skip_turn()

        assert o.is_finished
        assert not o.waiting_for_user