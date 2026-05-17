"""
Münazara — Streamlit Arayüzü

Çalıştırmak için: streamlit run ui/app.py

Değişiklikler (v2):
- Double render hatası düzeltildi: on_complete callback'lerinden show_message kaldırıldı.
  Tek kaynak of truth = st.session_state.messages; st.rerun() render'ı halleder.
- Sidebar'a tur sayısı slider'ı eklendi.
- Tartışma bitince öğrenme özeti gösteriliyor (generate_summary).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from agents.orchestrator import DebateOrchestrator

# ===== SAYFA AYARLARI =====
st.set_page_config(
    page_title="Münazara — Çoklu Ajan Öğrenme",
    page_icon="🎓",
    layout="centered",
)

st.markdown("""
<style>
    .stApp { max-width: 800px; margin: 0 auto; }
</style>
""", unsafe_allow_html=True)


class StreamState:
    """Streaming callback'lerinde ajan yanıtlarını biriktirir."""
    def __init__(self):
        self.full_response: str = ""
        self.student_response: str = ""
        self.prof_response: str = ""


# ===== DEMO VERİSİ =====
DEMO_TOPIC = "Türev nedir"
DEMO_MESSAGES = [
    {
        "role": "professor",
        "content": (
            "Türev, bir fonksiyonun belirli bir noktadaki anlık değişim hızıdır. "
            "Arabayı düşünün: hız göstergesi size o anki türevi gösteriyor — "
            "ne kadar hızlı değiştiğinizi. Peki siz bana söyleyin: araba sabit "
            "hızda gidiyorsa, hızın türevi ne olur?"
        ),
    },
    {
        "role": "student",
        "content": (
            "Hocam yani türev hız mı? Ben sanıyordum bir şeylerin mesafesini "
            "hesaplıyordu. Sabit hızda türev... sıfır mı olur?"
        ),
    },
    {
        "role": "professor",
        "content": (
            "Yaklaştınız ama tam değil, Kamil. Türev mesafe değil, değişim hızıdır. "
            "Hız sabitken sıfır olan türev değil — ivmedir, yani hızın türevi sıfırdır. "
            "Her türev sorusunda 'neyin türevi' diye sormak zorundasınız. "
            "Peki pozisyonun türevi nedir?"
        ),
    },
    {
        "role": "student",
        "content": (
            "Aa yani her şeyin türevi ayrı mı? Pozisyonun türevi hız mı oluyor o zaman? "
            "Peki hızın türevi de ivme mi — zincir gibi mi gidiyor bu?"
        ),
    },
    {
        "role": "professor",
        "content": (
            "İşte şimdi konuşuyoruz! Buna türev zinciri diyebiliriz: konum → hız → ivme. "
            "Newton bu bağlantıyı keşfetmeden önce kimse bu tabloyu görmemişti. "
            "Şimdi size bir soru: ivmenin de türevi var mıdır, "
            "ve fiziksel anlamı ne olabilir?"
        ),
    },
    {
        "role": "student",
        "content": (
            "İvmenin türevi... jerk mi? Bir yerde duymuştum. "
            "Arabanın aniden frene basması gibi bir şey mi? "
            "Ama hocam bütün bunlar nasıl hesaplanıyor — sezgisel anladım "
            "ama formül kısmı hâlâ muğlak."
        ),
    },
    {
        "role": "professor",
        "content": (
            "Evet, jerk — Türkçesiyle sarsıntı. Mühendisler onu da ölçer. "
            "Formül kısmına gelince: f'(x) = lim[h→0] (f(x+h) - f(x)) / h. "
            "Bu bir limit tanımıdır. Sizi şuraya çekeyim: bu formülde h sıfıra "
            "yaklaşırken ne olduğunu düşünün — neden tam sıfır yapmıyoruz?"
        ),
    },
]


# ===== SESSION STATE =====
def _init_state():
    defaults = {
        "orchestrator": None,
        "messages": [],
        "user_asking": False,
        "history": [],
        "demo_mode": False,
        "current_topic": None,
        "max_rounds": 5,
        "debate_summary": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_state()


# ===== YARDIMCI FONKSİYONLAR =====
def add_message(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})


def show_message(role: str, content: str) -> None:
    avatar_map = {"professor": "🎓", "student": "🙋", "user": "🧑", "system": "⚙️"}
    label_map = {"professor": "**Profesör Gültekin**\n\n", "student": "**Kamil**\n\n"}

    if role in ("professor", "student"):
        with st.chat_message("assistant", avatar=avatar_map[role]):
            st.markdown(f"{label_map[role]}{content}")
    elif role == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(content)
    elif role == "system":
        with st.chat_message("assistant", avatar="⚙️"):
            st.info(content)


def reset_session(save_to_history: bool = True) -> None:
    if (
        save_to_history
        and st.session_state.messages
        and st.session_state.current_topic
    ):
        st.session_state.history.append({
            "topic": st.session_state.current_topic,
            "messages": list(st.session_state.messages),
        })
    st.session_state.messages = []
    st.session_state.orchestrator = None
    st.session_state.user_asking = False
    st.session_state.demo_mode = False
    st.session_state.current_topic = None
    st.session_state.debate_summary = None


def get_download_text() -> str:
    label_map = {
        "professor": "PROFESÖR GÜLTEKİN",
        "student": "KAMİL",
        "user": "SİZ",
        "system": "---",
    }
    lines = []
    for msg in st.session_state.messages:
        label = label_map.get(msg["role"], msg["role"].upper())
        lines.append(f"[{label}]\n{msg['content']}\n")

    if st.session_state.debate_summary:
        lines.append("\n" + "="*40)
        lines.append("[ÖĞRENME ÖZETİ]")
        lines.append(st.session_state.debate_summary)

    return "\n".join(lines)


# ===== BAŞLIK =====
st.title("🎓 Münazara")
st.caption("Kavramı yaz, Profesör açıklar, sen araya gir veya Kamil'e bırak!")


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
3. Her turda: Kamil'e bırak veya sen sor  

---
*Hackathon 2026 · BTK Akademi × Google × GİRVAK*
""")

    # Tartışma başlamadan tur ayarı
    if st.session_state.orchestrator is None and not st.session_state.demo_mode:
        st.divider()
        st.session_state.max_rounds = st.slider(
            "Tartışma turu sayısı",
            min_value=3,
            max_value=8,
            value=st.session_state.max_rounds,
            help="Daha fazla tur = daha derin tartışma, daha fazla API çağrısı",
        )

    # Aktif tartışma araçları
    if st.session_state.orchestrator or st.session_state.demo_mode:
        st.divider()

        if st.session_state.orchestrator:
            orch = st.session_state.orchestrator
            st.caption(f"**Tur:** {orch.current_round} / {orch.max_rounds}")
            progress = orch.current_round / orch.max_rounds
            st.progress(progress)

        if st.session_state.messages:
            raw_name = st.session_state.current_topic or "tartisma"
            safe_name = (
                "".join(c for c in raw_name if c.isalnum() or c in " _-")[:30]
                .strip()
                .replace(" ", "_")
            )
            st.download_button(
                label="📥 Tartışmayı indir (.txt)",
                data=get_download_text(),
                file_name=f"munazara_{safe_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        if st.button("🔄 Yeni konu başlat", use_container_width=True):
            reset_session(save_to_history=True)
            st.rerun()

    # Geçmiş tartışmalar
    if st.session_state.history:
        st.divider()
        st.subheader("📚 Geçmiş Tartışmalar")
        for past in reversed(st.session_state.history):
            with st.expander(f"📖 {past['topic']}"):
                for msg in past["messages"]:
                    if msg["role"] not in ("professor", "student", "user"):
                        continue
                    emoji = {"professor": "🎓", "student": "🙋", "user": "🧑"}[msg["role"]]
                    snippet = msg["content"]
                    if len(snippet) > 120:
                        snippet = snippet[:120] + "..."
                    st.caption(f"{emoji} {snippet}")


# ===== MEVCUT MESAJLARI GÖSTER =====
for msg in st.session_state.messages:
    show_message(msg["role"], msg["content"])

# Özet göster
if st.session_state.debate_summary:
    with st.expander("📋 Öğrenme Özeti", expanded=True):
        st.markdown(st.session_state.debate_summary)


# ===== DEMO MODU =====
is_idle = (
    st.session_state.orchestrator is None
    and not st.session_state.demo_mode
    and not st.session_state.messages
)

if is_idle:
    st.divider()
    col_btn, col_info = st.columns([1, 2])
    with col_btn:
        if st.button("🎬 Demo'yu Göster", use_container_width=True):
            st.session_state.demo_mode = True
            st.session_state.current_topic = DEMO_TOPIC
            for m in DEMO_MESSAGES:
                st.session_state.messages.append(m)
            st.rerun()
    with col_info:
        st.caption("API key gerektirmez. Örnek bir tartışmayı izleyin.")

if st.session_state.demo_mode and st.session_state.messages:
    st.divider()
    st.info(
        "🎬 **Demo modu** — Bu konuşma gerçek API kullanmamaktadır. "
        "Kendi konunuzu denemek için sol menüden 'Yeni konu başlat'a tıklayın."
    )


# ===== KAVRAM GİRİŞİ =====
if st.session_state.orchestrator is None and not st.session_state.demo_mode:
    topic = st.chat_input("Bir kavram yazın (ör: Türev nedir, Fotosentez, Arz ve Talep...)")

    if topic:
        st.session_state.current_topic = topic
        add_message("user", f"📚 **Konu:** {topic}")
        show_message("user", f"📚 **Konu:** {topic}")

        st.session_state.orchestrator = DebateOrchestrator(
            topic,
            max_rounds=st.session_state.max_rounds,
        )

        placeholder = st.empty()
        state = StreamState()

        def on_chunk_open(role: str, chunk: str) -> None:
            state.full_response += chunk
            with placeholder.container():
                with st.chat_message("assistant", avatar="🎓"):
                    st.markdown(f"**Profesör Gültekin**\n\n{state.full_response}▌")

        def on_complete_open(role: str, message: str) -> None:
            placeholder.empty()  # sadece placeholder temizle, state yazma yok

        try:
            with st.spinner("Profesör açıklıyor..."):
                success = st.session_state.orchestrator.start_debate(
                    on_chunk_open, on_complete_open
                )
            # State yazımı spinner bittikten sonra, rerun öncesinde — güvenli bölge
            if success:
                prof_msg = st.session_state.orchestrator.messages[-1]["content"]
                add_message("professor", prof_msg)
            else:
                err = st.session_state.orchestrator.last_error or "Bilinmeyen hata"
                add_message("system", f"❌ {err}")
        except Exception as e:
            placeholder.empty()
            add_message("system", f"❌ Beklenmeyen hata: {e}")
            st.session_state.orchestrator.is_finished = True
            st.session_state.orchestrator.waiting_for_user = False

        st.rerun()


# ===== KULLANICI SIRASI =====
elif (
    not st.session_state.demo_mode
    and st.session_state.orchestrator is not None
    and st.session_state.orchestrator.waiting_for_user
    and not st.session_state.user_asking
):
    st.divider()
    st.markdown("### 💬 Sıra sende!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⏭️ Turumu atla (Kamil sorsun)", use_container_width=True):
            student_ph = st.empty()
            prof_ph = st.empty()
            state = StreamState()

            def on_chunk_skip(role: str, chunk: str) -> None:
                if role == "student":
                    state.student_response += chunk
                    with student_ph.container():
                        with st.chat_message("assistant", avatar="🙋"):
                            st.markdown(f"**Kamil**\n\n{state.student_response}▌")
                elif role == "professor":
                    state.prof_response += chunk
                    with prof_ph.container():
                        with st.chat_message("assistant", avatar="🎓"):
                            st.markdown(f"**Profesör Gültekin**\n\n{state.prof_response}▌")

            def on_complete_skip(role: str, message: str) -> None:
                # placeholder'ı temizleme — içerik st.rerun()'a kadar görünür kalsın,
                # rerun zaten sayfayı sıfırdan render eder, göz kırpma olmaz
                pass

            # API çağrısından ÖNCE mevcut mesaj sayısını sabitle — kırılgan indeksten kaçın
            orch_msg_count_before = len(st.session_state.orchestrator.messages)

            try:
                with st.spinner("Kamil ve Profesör konuşuyor..."):
                    success = st.session_state.orchestrator.user_skip_turn(
                        on_chunk_skip, on_complete_skip
                    )
                # State yazımı spinner bittikten sonra — güvenli bölge
                if success:
                    new_msgs = st.session_state.orchestrator.messages[orch_msg_count_before:]
                    for m in new_msgs:
                        add_message(m["role"], m["content"])
                else:
                    err = st.session_state.orchestrator.last_error or "Bilinmeyen hata"
                    add_message("system", f"❌ {err}")
                if st.session_state.orchestrator.is_finished:
                    add_message("system", "✅ Tartışma tamamlandı!")
            except Exception as e:
                add_message("system", f"❌ Beklenmeyen hata: {e}")
                st.session_state.orchestrator.is_finished = True
                st.session_state.orchestrator.waiting_for_user = False

            st.rerun()

    with col2:
        if st.button("❓ Ben soru soracağım", use_container_width=True):
            st.session_state.user_asking = True
            st.rerun()


# ===== KULLANICI SORU SORUYOR =====
elif not st.session_state.demo_mode and st.session_state.user_asking:
    st.divider()
    st.markdown("### 💬 Sorunuzu yazın:")

    user_question = st.chat_input("Profesöre sormak istediğiniz soruyu yazın...")

    if user_question:
        add_message("user", f"❓ **Soru:** {user_question}")
        show_message("user", f"❓ **Soru:** {user_question}")

        placeholder = st.empty()
        state = StreamState()

        def on_chunk_q(role: str, chunk: str) -> None:
            state.full_response += chunk
            with placeholder.container():
                with st.chat_message("assistant", avatar="🎓"):
                    st.markdown(f"**Profesör Gültekin**\n\n{state.full_response}▌")

        def on_complete_q(role: str, message: str) -> None:
            placeholder.empty()  # sadece placeholder temizle

        # API çağrısından ÖNCE mevcut mesaj sayısını sabitle
        orch_msg_count_before = len(st.session_state.orchestrator.messages)

        try:
            with st.spinner("Profesör cevaplıyor..."):
                success = st.session_state.orchestrator.user_ask_question(
                    user_question, on_chunk_q, on_complete_q
                )
            # State yazımı spinner bittikten sonra — güvenli bölge
            if success:
                new_msgs = st.session_state.orchestrator.messages[orch_msg_count_before:]
                for m in new_msgs:
                    if m["role"] == "professor":
                        add_message("professor", m["content"])
                        break
            else:
                err = st.session_state.orchestrator.last_error or "Bilinmeyen hata"
                add_message("system", f"❌ {err}")
        except Exception as e:
            placeholder.empty()
            add_message("system", f"❌ Beklenmeyen hata: {e}")
            st.session_state.orchestrator.is_finished = True
            st.session_state.orchestrator.waiting_for_user = False

        st.session_state.user_asking = False

        if st.session_state.orchestrator.is_finished:
            add_message("system", "✅ Tartışma tamamlandı!")

        st.rerun()


# ===== TARTIŞMA BİTTİYSE =====
elif (
    not st.session_state.demo_mode
    and st.session_state.orchestrator is not None
    and st.session_state.orchestrator.is_finished
):
    # Özet henüz üretilmediyse üret
    if st.session_state.debate_summary is None and st.session_state.orchestrator.summary is None:
        with st.spinner("📋 Öğrenme özeti hazırlanıyor..."):
            summary = st.session_state.orchestrator.generate_summary()
            if summary:
                st.session_state.debate_summary = summary
                st.rerun()
            else:
                err = getattr(st.session_state.orchestrator, "summary_error", None)
                if err:
                    st.session_state.debate_summary = f"__HATA__{err}"
                else:
                    st.session_state.debate_summary = "__HATA__Tartışma verisi boş."

    st.divider()

    # Özeti göster — hata ve başarı durumları ayrı
    if st.session_state.debate_summary and st.session_state.debate_summary.startswith("__HATA__"):
        hata_detay = st.session_state.debate_summary.replace("__HATA__", "")
        st.warning(f"📋 Öğrenme özeti üretilemedi: {hata_detay}")
    elif st.session_state.debate_summary:
        with st.expander("📋 Öğrenme Özeti", expanded=True):
            st.markdown(st.session_state.debate_summary)

    st.success("✅ Tartışma tamamlandı! Yeni bir konu başlatabilirsiniz.")

    if st.button("🔄 Yeni konu başlat", use_container_width=True):
        reset_session(save_to_history=True)
        st.rerun()