"""
Münazara — Integration Testler

Gerçek API çağrısı yapmadan, mock ile ajan davranışlarını doğrular.
Çalıştırmak için: pytest tests/test_integration.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.orchestrator import DebateOrchestrator


# ===== Mock helpers =====

def _make_stream(text: str):
    """chat_stream'i taklit eden generator."""
    for word in text.split():
        yield word + " "


def _patch_stream(prof_responses: list[str], student_responses: list[str]):
    """
    chat_stream'i patch'le.
    prof_responses ve student_responses sırayla dönecek yanıtlar.
    """
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
        """start_debate sonrası messages'a profesör mesajı eklenmiş olmalı."""
        with _patch_stream(
            prof_responses=["Türev, anlık değişim hızıdır. Siz ne düşünüyorsunuz?"],
            student_responses=[],
        ):
            o = DebateOrchestrator("Türev nedir", max_rounds=3)
            success = o.start_debate()

        assert success
        assert len(o.messages) == 1
        assert o.messages[0]["role"] == "professor"

    def test_professor_response_in_shared_history(self):
        """Profesör mesajı shared_history'ye 'professor' speaker ile eklenmeli."""
        with _patch_stream(
            prof_responses=["Kavramı açıklayayım."],
            student_responses=[],
        ):
            o = DebateOrchestrator("Fotosentez", max_rounds=3)
            o.start_debate()

        speakers = [m["speaker"] for m in o.shared_history]
        assert "professor" in speakers

    def test_professor_sees_student_history(self):
        """
        Profesör, öğrencinin önceki mesajlarını görebilmeli.
        _build_history_for("professor") öğrenci mesajlarını 'user' olarak içermeli.
        """
        with _patch_stream(
            prof_responses=["İlk açıklama.", "İkinci açıklama."],
            student_responses=["Anlamadım hocam, neden öyle?"],
        ):
            o = DebateOrchestrator("Newton", max_rounds=3)
            o.start_debate()
            o.user_skip_turn()

        prof_view = o._build_history_for("professor")
        all_content = " ".join(m["content"] for m in prof_view)
        assert "Anlamadım" in all_content, "Profesör öğrencinin mesajını görmüyor"

    def test_user_question_reaches_professor(self):
        """Kullanıcı sorusu profesörün geçmişine ulaşmalı."""
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
        """user_skip_turn sonrası messages'ta student mesajı olmalı."""
        with _patch_stream(
            prof_responses=["Açıklama.", "Devam."],
            student_responses=["Peki hocam ama neden?"],
        ):
            o = DebateOrchestrator("Limit", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        roles = [m["role"] for m in o.messages]
        assert "student" in roles

    def test_student_sees_professor_history(self):
        """
        Öğrenci, profesörün önceki mesajlarını görebilmeli.
        _build_history_for("student") profesör mesajlarını 'user' olarak içermeli.
        """
        with _patch_stream(
            prof_responses=["Türev şöyle çalışır."],
            student_responses=[],
        ):
            o = DebateOrchestrator("Türev", max_rounds=3)
            o.start_debate()

        student_view = o._build_history_for("student")
        all_content = " ".join(m["content"] for m in student_view)
        assert "Türev şöyle çalışır" in all_content, "Öğrenci profesörün mesajını görmüyor"

    def test_student_sees_user_question_context(self):
        """
        Kullanıcı sorusu sonraki turda öğrencinin geçmişinde olmalı.
        Bu shared history'nin _pending_context'e göre avantajı.
        """
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
        assert "Handshake neden 3 adım" in all_content, \
            "Öğrenci kullanıcı sorusunu görmüyor — shared history bozuk"


class TestDebateFlow:
    def test_full_round_increments(self):
        """Her user_skip_turn sonrası current_round artmalı."""
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
        """max_rounds dolduğunda is_finished True olmalı."""
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
        """Mesaj sırası: prof → student → prof olmalı."""
        with _patch_stream(
            prof_responses=["Prof 1.", "Prof 2."],
            student_responses=["Student 1."],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        roles = [m["role"] for m in o.messages]
        assert roles == ["professor", "student", "professor"]

    def test_shared_history_grows_correctly(self):
        """shared_history doğru büyümeli: system + prof + student + prof."""
        with _patch_stream(
            prof_responses=["Prof 1.", "Prof 2."],
            student_responses=["Student 1."],
        ):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()
            o.user_skip_turn()

        speakers = [m["speaker"] for m in o.shared_history]
        assert speakers == ["system", "professor", "student", "professor"]

    def test_no_skip_when_not_waiting(self):
        """waiting_for_user False iken user_skip_turn False dönmeli."""
        o = DebateOrchestrator("Test", max_rounds=3)
        # start_debate çağrılmadı, waiting_for_user = False
        result = o.user_skip_turn()
        assert result is False

    def test_no_question_when_not_waiting(self):
        """waiting_for_user False iken user_ask_question False dönmeli."""
        o = DebateOrchestrator("Test", max_rounds=3)
        result = o.user_ask_question("Soru?")
        assert result is False


class TestErrorRecovery:
    def test_api_error_sets_last_error(self):
        """API hatası durumunda last_error dolu, is_finished True olmalı."""
        with patch("agents.orchestrator.chat_stream", side_effect=Exception("Bağlantı kesildi")):
            o = DebateOrchestrator("Test", max_rounds=3)
            success = o.start_debate()

        assert not success
        assert o.last_error is not None
        assert "Bağlantı kesildi" in o.last_error or "Beklenmeyen" in o.last_error
        assert o.is_finished

    def test_session_state_consistent_after_error(self):
        """Hata sonrası waiting_for_user tutarlı kalmalı."""
        with _patch_stream(prof_responses=["İlk açıklama."], student_responses=[]):
            o = DebateOrchestrator("Test", max_rounds=5)
            o.start_debate()

        # İkinci çağrıda hata
        with patch("agents.orchestrator.chat_stream", side_effect=Exception("Timeout")):
            o.user_skip_turn()

        assert o.is_finished
        assert not o.waiting_for_user