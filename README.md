# 🎓 Münazara — Çoklu Ajan Öğrenme Sahnesi

Bir kavram girin, **Profesör Gültekin** ve **Kamil** tartışsın — siz izleyin, araya girin, öğrenin.

> Hackathon 2026 · BTK Akademi × Google × GİRVAK

---

## 🚀 Hızlı Başlangıç

### 1. Repo'yu klonlayın
```bash
git clone https://github.com/ravzaatasdemir/munazara.git
cd munazara
```

### 2. Bağımlılıkları kurun
```bash
pip install -r requirements.txt
```

### 3. API key'inizi ekleyin
```bash
cp .env.example .env
# .env dosyasını açıp GEMINI_API_KEY değerini yazın
```

### 4. API'yi test edin
```bash
python agents/gemini_client.py
```

### 5. Terminalde tartışma testi
```bash
python -m agents.orchestrator
```

### 6. Streamlit arayüzünü başlatın
```bash
streamlit run ui/app.py
```

---

## 🏗️ Mimari

```
Kullanıcı (kavram girer)
    ↓
Orchestrator (Python)
    ↓           ↓
Profesör     Öğrenci
    ↓           ↓
    └→ Gemini API ←┘
    ↓
Streamlit UI (sohbet ekranı)
```

- **Profesör Gültekin 🎓** — Antik Yunan ve Osmanlı medrese geleneğinden beslenen nihrir bir akademisyen. Sokratik yöntemle muhatabını kendi çelişkisine düşürür, yanlışı doğrudan düzeltir, kavramı köküne kadar söker. Zaman zaman Latince, Osmanlıca veya Arap felsefesinden terimler serpiştirerek derinlik katar.
- **Kamil 🙋** — Cahil cesaretine sahip, atılgan ve eleştirel bir öğrenci. Başta eksik bilgiyle gelir, sorgulamaktan çekinmez. Ama nihayetinde öğrenmeye açıktır — Profesör ikna ettikçe gerçekten anlar, her turda soruları olgunlaşır ve karakter gelişimi yaşar.

---

## 📁 Dosya Yapısı

```
munazara/
├── agents/
│   ├── gemini_client.py    # Gemini API wrapper
│   ├── orchestrator.py     # Tartışma akış yöneticisi
│   └── personas.py         # Ajan karakter tanımları
├── ui/
│   └── app.py              # Streamlit arayüzü
├── docs/                   # Dokümanlar
├── tests/                  # Testler
├── .env.example            # API key şablonu
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🛠️ Teknoloji

| Bileşen | Teknoloji |
|---------|-----------|
| LLM | Google Gemini 2.0 Flash |
| Backend | Python 3.11+ |
| Arayüz | Streamlit |
| Mimari | Multi-agent orchestration |

---

## 👥 Takım

| Rol | Sorumluluk |
|-----|-----------|
| Backend | Gemini API + orkestrasyon + state yönetimi |
| Frontend | Streamlit UI + deploy |
| İçerik + Teslim | Prompt mühendisliği + test + video |

---

*Münazara — Ezberden kavrayışa, tartışarak öğren.*
