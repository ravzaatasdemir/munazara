---
title: Munazara
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.45.0
app_file: ui/app.py
pinned: false
---

# Münazara — Çoklu Ajan Öğrenme Sahnesi

Bir kavram girin, **Profesör Gültekin** ve **Kamil** tartışsın — siz izleyin, araya girin, öğrenin.

> Hackathon 2026 · BTK Akademi × Google × GİRVAK

---

## Hızlı Başlangıç

### 1. Repo'yu klonlayın
\\ash
git clone https://github.com/ravzaatasdemir/munazara.git
cd munazara
\
### 2. Bağımlılıkları kurun
\\ash
pip install -r requirements.txt
\
### 3. API key'inizi ekleyin
\\ash
cp .env.example .env
# .env dosyasını açıp GEMINI_API_KEY değerini yazın
\
**Hugging Face Space'te:** Settings → Secrets → \GEMINI_API_KEY\ ekleyin.

### 4. Streamlit arayüzünü başlatın
\\ash
streamlit run ui/app.py
\
---

## Mimari

\Kullanıcı (kavram girer)
    ↓
Orchestrator (Python)
    ↓           ↓
Profesör     Öğrenci
    ↓           ↓
    └→ Gemini API ←┘
    ↓
Streamlit UI
\
- **Profesör Gültekin** — Sokratik yöntemle öğreten nihrir akademisyen
- **Kamil** — Eleştirel, sorgulamacı öğrenci
- **Sen** — İstediğin zaman araya girip soru sorabilirsin (max 3 soru/tartışma)

---

## Teknoloji

| Bileşen | Teknoloji |
|---------|-----------|
| LLM | Google Gemini 2.0 Flash |
| Backend | Python 3.11+ |
| Arayüz | Streamlit |
| Mimari | Multi-agent orchestration |

---

*Münazara — Ezberden kavrayışa, tartışarak öğren.*
