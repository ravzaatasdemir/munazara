"""
Münazara — Streamlit Arayüzü (İnteraktif Mod)

Çalıştırmak için: streamlit run ui/app.py
Kişi B bu dosyayı yönetir.
"""

import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from agents.gemini_client import chat
from agents.personas import PROFESSOR_PROMPT, STUDENT_PROMPT, get_opening_prompt

# ===== SAYFA AYARLARI =====
st.set_page_config(
    page_title="Münazara — Çoklu Ajan Öğrenme",
    page_icon="🎓",
    layout="centered",
)

# ===== STILLER =====
st.markdown("""
<style>
    .stApp {
        max-width: 800px;
        margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

# ===== BAŞLIK =====
st.title("🎓 Münazara")
st.caption("Kavramı yaz, Profesör açıklar, sen araya gir veya Kamil'e bırak!")

# ===== STATE =====
if "messages" not in st.session_state:
    st.session_state.messages = []
if "debate_started" not in st.session_state:
    st.session_state.debate_started = False
if "waiting_for_user" not in st.session_state:
    st.session_state.waiting_for_user = False
if "current_round" not in st.session_state:
    st.session_state.current_round = 0
if "prof_history" not in st.session_state:
    st.session_state.prof_history = []
if "student_history" not in st.session_state:
    st.session_state.student_history = []
if "topic" not in st.session_state:
    st.session_state.topic = ""
if "user_asking" not in st.session_state:
    st.session_state.user_asking = False

# Profesör ve Öğrenci sıcaklıkları
PROF_TEMP = 0.3
STUDENT_TEMP = 0.7
MAX_ROUNDS = 5

# ===== MEVCUT MESAJLARI GÖSTER =====
for msg in st.session_state.messages:
    if msg["role"] == "professor":
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown(f"**Profesör Gültekin**\n\n{msg['content']}")
    elif msg["role"] == "student":
        with st.chat_message("assistant", avatar="🙋"):
            st.markdown(f"**Kamil**\n\n{msg['content']}")
    elif msg["role"] == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(msg["content"])
    elif msg["role"] == "system":
        with st.chat_message("assistant", avatar="⚠️"):
            st.warning(msg["content"])


# ===== FONKSİYONLAR =====
def add_message(role, content):
    """Mesaj ekle ve ekranda göster"""
    st.session_state.messages.append({"role": role, "content": content})
    
    if role == "professor":
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown(f"**Profesör Gültekin**\n\n{content}")
    elif role == "student":
        with st.chat_message("assistant", avatar="🙋"):
            st.markdown(f"**Kamil**\n\n{content}")
    elif role == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(content)
    elif role == "system":
        with st.chat_message("assistant", avatar="⚠️"):
            st.warning(content)


def professor_speaks(is_opening=False):
    """Profesörün konuşması"""
    if is_opening:
        # İlk açılış
        prompt = get_opening_prompt(st.session_state.topic)
        st.session_state.prof_history.append({"role": "user", "content": prompt})
    
    response = chat(
        system_prompt=PROFESSOR_PROMPT,
        history=st.session_state.prof_history,
        temperature=PROF_TEMP,
    )
    
    if response is None:
        add_message("system", "⚠️ API hatası - Profesör cevap veremedi.")
        return False
    
    st.session_state.prof_history.append({"role": "model", "content": response})
    add_message("professor", response)
    return response


def student_speaks(prof_last_message, current_round, max_rounds):
    """AI Öğrencinin konuşması"""
    # Soru seviyesi belirle
    if current_round < 2:
        level = "yüzeysel — merak ettiğin temel şeyleri sor"
    elif current_round < 4:
        level = "orta — kavramları birbirine bağlamaya başla"
    else:
        level = "derin — eleştirel düşün, farklı senaryolar sor"
    
    # Context ekle
    context = f"[Tur {current_round}/{max_rounds}. Soru seviyen: {level}]\n\n{prof_last_message}"
    
    st.session_state.student_history.append({"role": "user", "content": context})
    
    response = chat(
        system_prompt=STUDENT_PROMPT,
        history=st.session_state.student_history,
        temperature=STUDENT_TEMP,
    )
    
    if response is None:
        add_message("system", "⚠️ API hatası - Kamil cevap veremedi.")
        return False
    
    st.session_state.student_history.append({"role": "model", "content": response})
    add_message("student", response)
    return response


# ===== KAVRAM GİRİŞİ =====
if not st.session_state.debate_started:
    topic = st.chat_input("Bir kavram yazın (ör: Türev nedir, Fotosentez, Arz ve Talep...)")
    
    if topic:
        st.session_state.topic = topic
        st.session_state.debate_started = True
        
        # Kullanıcının girdiği konuyu göster
        add_message("user", f"📚 **Konu:** {topic}")
        
        # Profesör açılış konuşması yapsın
        with st.spinner("Profesör açıklıyor..."):
            prof_response = professor_speaks(is_opening=True)
        
        if prof_response:
            st.session_state.waiting_for_user = True
            st.session_state.current_round = 1
        else:
            # İlk açılışta hata - tartışma başlamadı
            st.session_state.debate_started = False
        
        st.rerun()

# ===== KULLANICI SIRASI =====
elif st.session_state.waiting_for_user and not st.session_state.user_asking:
    st.divider()
    st.markdown("### 💬 Sıra sende!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏭️ Turumu atla (Kamil sorsun)", use_container_width=True):
            # AI Öğrenci konuşsun
            with st.spinner("Kamil soruyor..."):
                # Profesörün son mesajını al
                prof_last = st.session_state.prof_history[-1]["content"]
                student_response = student_speaks(
                    prof_last,
                    st.session_state.current_round,
                    MAX_ROUNDS
                )
            
            if student_response:
                # Profesör öğrenciye cevap versin
                with st.spinner("Profesör cevaplıyor..."):
                    st.session_state.prof_history.append({"role": "user", "content": student_response})
                    prof_response = professor_speaks()
                
                if prof_response:
                    st.session_state.current_round += 1
                    
                    # Max tura ulaştıysa bitir
                    if st.session_state.current_round >= MAX_ROUNDS:
                        st.session_state.waiting_for_user = False
                        add_message("system", "✅ Tartışma tamamlandı!")
                else:
                    # Profesör cevap veremedi - tartışmayı bitir
                    st.session_state.waiting_for_user = False
                    add_message("system", "❌ API hatası nedeniyle tartışma sonlandırıldı.")
            else:
                # Kamil cevap veremedi - tartışmayı bitir
                st.session_state.waiting_for_user = False
                add_message("system", "❌ API hatası nedeniyle tartışma sonlandırıldı.")
            
            st.rerun()
    
    with col2:
        if st.button("❓ Ben soru soracağım", use_container_width=True):
            st.session_state.user_asking = True
            st.rerun()

# ===== KULLANICI SORU SORUYOR =====
elif st.session_state.user_asking:
    st.divider()
    st.markdown("### 💬 Sorunuzu yazın:")
    
    user_question = st.chat_input("Profesöre sormak istediğiniz soruyu yazın...")
    
    if user_question:
        # Kullanıcı sorusunu göster
        add_message("user", f"❓ **Soru:** {user_question}")
        
        # Profesör cevaplasın
        with st.spinner("Profesör cevaplıyor..."):
            # Kullanıcı sorusunu context ile Profesör'e ilet
            st.session_state.prof_history.append({
                "role": "user", 
                "content": f"[Tartışma sırasında sınıftaki başka bir öğrenci (insan kullanıcı) araya girip şunu sordu: '{user_question}']\n\nÖnceki tartışmayı ve bu konuda söylediklerini dikkate alarak bu soruyu yanıtla. Daha önce açıkladığın kavramlara referans verebilirsin."
            })
            prof_response = professor_speaks()
        
        if prof_response:
            # Kamil'in history'sine ekleme - role sequence hatası önlenir
            st.session_state.current_round += 1
            st.session_state.user_asking = False
            
            # Max tura ulaştıysa bitir
            if st.session_state.current_round >= MAX_ROUNDS:
                st.session_state.waiting_for_user = False
                add_message("system", "✅ Tartışma tamamlandı!")
            else:
                st.session_state.waiting_for_user = True
        else:
            # API hatası - state'i temizle, tartışmayı bitir
            st.session_state.user_asking = False
            st.session_state.waiting_for_user = False
            add_message("system", "❌ API hatası nedeniyle tartışma sonlandırıldı. Yeni konu başlatabilirsiniz.")
        
        st.rerun()

# ===== TARTIŞMA BİTTİYSE =====
elif st.session_state.debate_started and not st.session_state.waiting_for_user:
    st.divider()
    
    if st.button("🔄 Yeni konu başlat", use_container_width=True):
        # Tüm state'i sıfırla
        st.session_state.messages = []
        st.session_state.debate_started = False
        st.session_state.waiting_for_user = False
        st.session_state.current_round = 0
        st.session_state.prof_history = []
        st.session_state.student_history = []
        st.session_state.topic = ""
        st.session_state.user_asking = False
        st.rerun()

# ===== SIDEBAR =====
with st.sidebar:
    st.header("Münazara Hakkında")
    st.markdown("""
    **Münazara**, interaktif bir AI öğrenme platformudur.

    🎓 **Profesör Gültekin** — Nihrir akademisyen, felsefi derinlik

    🙋 **Kamil** — Eleştirel öğrenci, sorgulamacı

    🧑 **Sen** — Araya girip soru sorabilirsin!

    ---

    **Nasıl çalışır?**
    1. Bir kavram yazın
    2. Profesör açıklar
    3. Her turda karar ver:
       - "Turumu atla" → Kamil sorar
       - "Ben soru soracağım" → Sen sorarsın
    4. Profesör cevaplar, döngü devam eder

    ---

    *Hackathon 2026 · BTK Akademi × Google × GİRVAK*
    """)
    
    # Debug bilgisi
    if st.session_state.debate_started:
        st.divider()
        st.caption(f"**Tur:** {st.session_state.current_round}/{MAX_ROUNDS}")