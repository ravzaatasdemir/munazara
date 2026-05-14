"""
Münazara — Streamlit Arayüzü

Çalıştırmak için: streamlit run ui/app.py
Kişi B bu dosyayı yönetir.
"""

import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from agents.orchestrator import run_debate

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
    .professor-msg {
        background-color: #e8f0fe;
        border-left: 4px solid #1a73e8;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .student-msg {
        background-color: #e6f4ea;
        border-left: 4px solid #0a8754;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ===== BAŞLIK =====
st.title("🎓 Münazara")
st.caption("Kavramı yaz, Profesör ve Öğrenci tartışsın, sen izle ve araya gir!")

# ===== STATE =====
if "messages" not in st.session_state:
    st.session_state.messages = []
if "debate_running" not in st.session_state:
    st.session_state.debate_running = False
if "debate_done" not in st.session_state:
    st.session_state.debate_done = False

# ===== MEVCUT MESAJLARI GÖSTER =====
for msg in st.session_state.messages:
    if msg["role"] == "professor":
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown(f"**Profesör Aydın**\n\n{msg['content']}")
    elif msg["role"] == "student":
        with st.chat_message("assistant", avatar="🙋"):
            st.markdown(f"**Öğrenci**\n\n{msg['content']}")
    elif msg["role"] == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(msg["content"])

# ===== KAVRAM GİRİŞİ =====
if not st.session_state.debate_done:
    topic = st.chat_input(
        "Bir kavram yazın (ör: Türev nedir, Fotosentez, Arz ve Talep...)"
    )

    if topic and not st.session_state.debate_running:
        st.session_state.debate_running = True

        # Kullanıcının girdiği kavramı göster
        st.session_state.messages.append({
            "role": "user",
            "content": f"📚 **Konu:** {topic}"
        })
        with st.chat_message("user", avatar="🧑"):
            st.markdown(f"📚 **Konu:** {topic}")

        # Tartışmayı başlat
        with st.spinner("Tartışma başlıyor..."):
            results = run_debate(topic, num_rounds=3)

        # Sonuçları ekrana bas
        for msg in results:
            st.session_state.messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

            if msg["role"] == "professor":
                with st.chat_message("assistant", avatar="🎓"):
                    st.markdown(f"**Profesör Aydın**\n\n{msg['content']}")
            elif msg["role"] == "student":
                with st.chat_message("assistant", avatar="🙋"):
                    st.markdown(f"**Öğrenci**\n\n{msg['content']}")

        st.session_state.debate_running = False
        st.session_state.debate_done = True
        st.rerun()

# ===== TARTIŞMA BİTTİYSE: YENİ KONU VEYA SORU =====
if st.session_state.debate_done:
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Yeni konu", use_container_width=True):
            st.session_state.messages = []
            st.session_state.debate_done = False
            st.session_state.debate_running = False
            st.rerun()
    with col2:
        st.button("❓ Soru sor (yakında)", disabled=True, use_container_width=True)

# ===== SIDEBAR =====
with st.sidebar:
    st.header("Münazara Hakkında")
    st.markdown("""
    **Münazara**, bir kavramı iki farklı bakış açısıyla
    öğrenmenizi sağlayan bir AI tartışma platformudur.

    🎓 **Profesör Aydın** — Kavramı açıklar, derinleştirir

    🙋 **Öğrenci** — Soru sorar, yanlış anlar, itiraz eder

    ---

    **Nasıl kullanılır?**
    1. Bir kavram yazın
    2. Tartışmayı izleyin
    3. (Yakında) Araya girip soru sorun

    ---

    *Hackathon 2026 · BTK Akademi × Google × GİRVAK*
    """)
