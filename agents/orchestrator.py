,"""
Münazara — Orchestrator

İki ajanın tartışma akışını yönetir.
Profesör → Öğrenci → Profesör → Öğrenci ... (N tur)
Kişi A bu dosyayı yönetir.
"""

from agents.gemini_client import chat
from agents.personas import PROFESSOR_PROMPT, STUDENT_PROMPT, get_opening_prompt


# Sıcaklık ayarları — karakter farklılığı için
PROF_TEMP = 0.3   # Tutarlı, akademik
STUDENT_TEMP = 0.7  # Değişken, meraklı


def run_debate(topic: str, num_rounds: int = 4, on_message=None):
    """
    Tartışmayı başlat ve yürüt.

    Args:
        topic: Tartışılacak kavram (ör. "Türev nedir")
        num_rounds: Kaç tur dönsün (1 tur = Prof + Öğrenci)
        on_message: Her mesajda çağrılacak callback fonksiyonu
                    on_message(role, name, content) şeklinde
                    role: "professor" | "student"
                    name: Görünen isim
                    content: Mesaj metni

    Returns:
        Tüm mesajların listesi [{"role": str, "name": str, "content": str}]
    """
    # Tartışma geçmişi — tüm mesajlar burada
    debate_history = []

    # Profesörün Gemini geçmişi (user/model formatında)
    prof_gemini_history = []

    # Öğrencinin Gemini geçmişi (user/model formatında)
    student_gemini_history = []

    # --- TUR 0: Profesör tartışmayı açar ---
    opening = get_opening_prompt(topic)
    prof_gemini_history.append({"role": "user", "content": opening})

    prof_response = chat(
        system_prompt=PROFESSOR_PROMPT,
        history=prof_gemini_history,
        temperature=PROF_TEMP,
    )
    
    # Hata kontrolü
    if prof_response is None:
        error_msg = {"role": "system", "name": "Sistem ⚠️", "content": "API hatası: Tartışma başlatılamadı. Lütfen API key'inizi kontrol edin veya farklı bir model deneyin."}
        debate_history.append(error_msg)
        if on_message:
            on_message(**error_msg)
        return debate_history
    
    prof_gemini_history.append({"role": "model", "content": prof_response})

    msg = {"role": "professor", "name": "Profesör Gültekin 🎓", "content": prof_response}
    debate_history.append(msg)
    if on_message:
        on_message(**msg)

    # --- TURLAR ---
    for round_num in range(num_rounds):
        # Öğrenci, Profesörün söylediğini duyuyor ve cevap veriyor
        student_gemini_history.append({"role": "user", "content": prof_response})

        student_response = chat(
            system_prompt=STUDENT_PROMPT,
            history=student_gemini_history,
            temperature=STUDENT_TEMP,
        )
        
        # Hata kontrolü
        if student_response is None:
            error_msg = {"role": "system", "name": "Sistem ⚠️", "content": f"API hatası: Tartışma {round_num+1}. turda durdu."}
            debate_history.append(error_msg)
            if on_message:
                on_message(**error_msg)
            return debate_history
        
        student_gemini_history.append({"role": "model", "content": student_response})

        msg = {"role": "student", "name": "Kamil 🙋", "content": student_response}
        debate_history.append(msg)
        if on_message:
            on_message(**msg)

        # Son turda Profesör tekrar cevap vermesin (istersen ver)
        if round_num < num_rounds - 1:
            # Profesör, Öğrencinin söylediğini duyuyor ve cevap veriyor
            prof_gemini_history.append({"role": "user", "content": student_response})

            prof_response = chat(
                system_prompt=PROFESSOR_PROMPT,
                history=prof_gemini_history,
                temperature=PROF_TEMP,
            )
            
            # Hata kontrolü
            if prof_response is None:
                error_msg = {"role": "system", "name": "Sistem ⚠️", "content": f"API hatası: Tartışma {round_num+1}. turda durdu."}
                debate_history.append(error_msg)
                if on_message:
                    on_message(**error_msg)
                return debate_history
            
            prof_gemini_history.append({"role": "model", "content": prof_response})

            msg = {"role": "professor", "name": "Profesör Gültekin 🎓", "content": prof_response}
            debate_history.append(msg)
            if on_message:
                on_message(**msg)

    return debate_history


def inject_user_question(
    question: str,
    debate_history: list,
    prof_gemini_history: list,
    student_gemini_history: list,
    on_message=None,
):
    """
    Kullanıcı tartışmaya soru sokar.
    Profesör kullanıcının sorusuna cevap verir.

    Bu fonksiyon ileride Kişi A tarafından UI'ya bağlanacak.
    """
    # Profesöre kullanıcının sorusunu ilet
    user_q = f"[Bir öğrenci araya girip şunu sordu: \"{question}\"] Bu soruyu cevapla."
    prof_gemini_history.append({"role": "user", "content": user_q})

    prof_response = chat(
        system_prompt=PROFESSOR_PROMPT,
        history=prof_gemini_history,
        temperature=PROF_TEMP,
    )
    
    if prof_response is None:
        return None  # Hata sinyali
    
    prof_gemini_history.append({"role": "model", "content": prof_response})

    msg = {"role": "professor", "name": "Profesör Gültekin 🎓", "content": prof_response}
    debate_history.append(msg)
    if on_message:
        on_message(**msg)

    return prof_response


# ========== HIZLI TEST ==========
if __name__ == "__main__":
    print("=" * 60)
    print("  MÜNAZARA — Test Tartışması")
    print("=" * 60)

    topic = input("\nKavram girin (ör: Türev nedir): ").strip()
    if not topic:
        topic = "Türev nedir"

    print(f"\n📚 Konu: {topic}\n")
    print("-" * 60)

    def print_message(role, name, content):
        if role == "system":
            print(f"\n⚠️ {content}")
        else:
            color = "\033[94m" if role == "professor" else "\033[92m"
            reset = "\033[0m"
            print(f"\n{color}{name}{reset}")
            print(f"{content}")
        print("-" * 60)

    run_debate(topic, num_rounds=3, on_message=print_message)
    print("\n✅ Tartışma tamamlandı!")