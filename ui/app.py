"""
Münazara — Streamlit Arayüzü (İnteraktif Mod)

Çalıştırmak için: streamlit run ui/app.py
Orchestrator kullanarak basitleştirilmiş versiyon.
Kişi B bu dosyayı yönetir.
"""

import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from agents.orchestrator import DebateOrchestrator

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
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_asking" not in st.session_state:
    st.session_state.user_asking = False

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


def show_streaming_message(role, content):
    """Streaming mesajı göster"""
    if role == "professor":
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown(f"**Profesör Gültekin**\n\n{content}")
    elif role == "student":
        with st.chat_message("assistant", avatar="🙋"):
            st.markdown(f"**Kamil**\n\n{content}")


# ===== KAVRAM GİRİŞİ =====
if st.session_state.orchestrator is None:
    topic = st.chat_input("Bir kavram yazın (ör: Türev nedir, Fotosentez, Arz ve Talep...)")
    
    if topic:
        # Kullanıcının girdiği konuyu göster
        add_message("user", f"📚 **Konu:** {topic}")
        with st.chat_message("user", avatar="🧑"):
            st.markdown(f"📚 **Konu:** {topic}")
        
        # Orchestrator oluştur
        st.session_state.orchestrator = DebateOrchestrator(topic, max_rounds=5)
        
        # Streaming için placeholder ve state
        message_placeholder = st.empty()
        
        # Closure için container class kullan
        class StreamState:
            def __init__(self):
                self.full_response = ""
        
        stream_state = StreamState()
        
        def on_chunk(role, chunk):
            stream_state.full_response += chunk
            
            with message_placeholder.container():
                with st.chat_message("assistant", avatar="🎓"):
                    st.markdown(f"**Profesör Gültekin**\n\n{stream_state.full_response}▌")
        
        def on_complete(role, message):
            message_placeholder.empty()
            add_message("professor", stream_state.full_response)
            show_streaming_message("professor", stream_state.full_response)
        
        # Profesör açılış konuşması yapsın
        with st.spinner("Profesör açıklıyor..."):
            success = st.session_state.orchestrator.start_debate(on_chunk, on_complete)
        
        if not success:
            add_message("system", "⚠️ API hatası - Tartışma başlatılamadı.")
            st.session_state.orchestrator = None
        
        st.rerun()

# ===== KULLANICI SIRASI =====
elif st.session_state.orchestrator.waiting_for_user and not st.session_state.user_asking:
    st.divider()
    st.markdown("### 💬 Sıra sende!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏭️ Turumu atla (Kamil sorsun)", use_container_width=True):
            # Streaming placeholders
            student_placeholder = st.empty()
            prof_placeholder = st.empty()
            
            # State için container class
            class StreamState:
                def __init__(self):
                    self.student_response = ""
                    self.prof_response = ""
                    self.current_speaker = None
            
            stream_state = StreamState()
            
            def on_chunk(role, chunk):
                if role == "student":
                    stream_state.current_speaker = "student"
                    stream_state.student_response += chunk
                    with student_placeholder.container():
                        with st.chat_message("assistant", avatar="🙋"):
                            st.markdown(f"**Kamil**\n\n{stream_state.student_response}▌")
                elif role == "professor":
                    if stream_state.current_speaker == "student":
                        # Kamil bitti, placeholder'ı temizle
                        student_placeholder.empty()
                        add_message("student", stream_state.student_response)
                        show_streaming_message("student", stream_state.student_response)
                        stream_state.current_speaker = "professor"
                    
                    stream_state.prof_response += chunk
                    with prof_placeholder.container():
                        with st.chat_message("assistant", avatar="🎓"):
                            st.markdown(f"**Profesör Gültekin**\n\n{stream_state.prof_response}▌")
            
            def on_complete(role, message):
                if role == "professor":
                    prof_placeholder.empty()
                    add_message("professor", stream_state.prof_response)
                    show_streaming_message("professor", stream_state.prof_response)
            
            with st.spinner("Kamil soruyor..."):
                success = st.session_state.orchestrator.user_skip_turn(on_chunk, on_complete)
            
            if not success:
                add_message("system", "❌ API hatası nedeniyle tartışma sonlandırıldı.")
            
            if st.session_state.orchestrator.is_finished:
                add_message("system", "✅ Tartışma tamamlandı!")
            
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
        with st.chat_message("user", avatar="🧑"):
            st.markdown(f"❓ **Soru:** {user_question}")
        
        # Streaming için placeholder
        message_placeholder = st.empty()
        
        # State için container class
        class StreamState:
            def __init__(self):
                self.full_response = ""
        
        stream_state = StreamState()
        
        def on_chunk(role, chunk):
            stream_state.full_response += chunk
            
            with message_placeholder.container():
                with st.chat_message("assistant", avatar="🎓"):
                    st.markdown(f"**Profesör Gültekin**\n\n{stream_state.full_response}▌")
        
        def on_complete(role, message):
            message_placeholder.empty()
            add_message("professor", stream_state.full_response)
            show_streaming_message("professor", stream_state.full_response)
        
        # Profesör cevaplasın
        with st.spinner("Profesör cevaplıyor..."):
            success = st.session_state.orchestrator.user_ask_question(
                user_question, 
                on_chunk, 
                on_complete
            )
        
        if not success:
            add_message("system", "❌ API hatası nedeniyle tartışma sonlandırıldı.")
        
        st.session_state.user_asking = False
        
        if st.session_state.orchestrator.is_finished:
            add_message("system", "✅ Tartışma tamamlandı!")
        
        st.rerun()

# ===== TARTIŞMA BİTTİYSE =====
elif st.session_state.orchestrator and st.session_state.orchestrator.is_finished:
    st.divider()
    
    if st.button("🔄 Yeni konu başlat", use_container_width=True):
        # Tüm state'i sıfırla
        st.session_state.messages = []
        st.session_state.orchestrator = None
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
    if st.session_state.orchestrator:
        st.divider()
        st.caption(f"**Tur:** {st.session_state.orchestrator.current_round}/{st.session_state.orchestrator.max_rounds}")