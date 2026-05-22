# Münazara — Çoklu Ajan Öğrenme Platformu

> **Ezberden kavrayışa, tartışarak öğren.**

Münazara, Sokratik yöntemle kavram öğretimi yapan interaktif bir eğitim platformudur. Kullanıcı bir kavram girer, iki AI ajan — **Profesör Gültekin** ve öğrenci **Kamil** — tartışmaya başlar. Kullanıcı istediği zaman araya girip soru sorabilir veya Kamil'e bırakabilir.

**Hackathon 2026 · BTK Akademi × Google × GİRVAK**

**Takım:** Dijital Dervişler

**Canlı Demo:** [huggingface.co/spaces/arcuray/munazara](https://huggingface.co/spaces/arcuray/munazara)

---

## Neden Münazara?

Geleneksel chatbot'lar tek yönlü bilgi aktarır — kullanıcı sorar, bot cevaplar. Münazara'da ise kullanıcı bir **canlı tartışmanın içine** girer. Profesör açıklar, öğrenci sorgular, yanlış anlar, itiraz eder. Kullanıcı bu sürece istediği anda müdahale edebilir. Bu yaklaşım, bilişsel psikolojideki **aktif öğrenme** ve **Sokratik yöntem** ilkelerine dayanır.

---

## Özellikler

**Çoklu Ajan Mimarisi**
- Profesör Gültekin: Sokratik yöntemle öğreten, benzetmeler kullanan, felsefi derinlik katan akademisyen
- Kamil: Yanlış anlayan, sorgulayan, her turda olgunlaşan öğrenci
- Kullanıcı: Tartışmaya aktif katılımcı (max 3 soru hakkı)

**Akıllı Orkestrasyon**
- Shared history mimarisi — her ajan tüm konuşmayı görür
- Otomatik role sequence koruması (Gemini API uyumu)
- Tur bazlı olgunlaşma sistemi (yüzeysel → orta → derin)
- Konuya göre adaptif açılış stratejisi (matematik, fen, tarih, ekonomi, bilgisayar bilimi)

**Gerçek Zamanlı Streaming**
- SSE (Server-Sent Events) ile kelime kelime yanıt
- FastAPI backend, React frontend
- generate_content_stream API kullanımı

**Güvenlik**
- Prompt injection koruması (keyword tabanlı input sanitization)
- API key lazy loading (thread-safe)
- Custom exception hiyerarşisi (APIQuotaError, APIConnectionError, APIKeyError)

**UX**
- Pixel-art sınıf teması (React + Tailwind CSS)
- Demo modu (API key gerektirmez)
- Tartışma sonunda AI öğrenme özeti
- Tartışma indirme (.txt)
- Geçmiş tartışmalar paneli
- Ayarlanabilir tur sayısı
- Streamlit alternatif arayüzü

**Test ve Kalite**
- 30+ birim test (pytest + mock)
- Dataclass modelleri (Message, HistoryEntry)
- Type hints, YAML tabanlı prompt yönetimi
- Mid-stream retry koruması (içerik duplikasyonu önlenir)

---

## Mimari

```
Kullanıcı
    ↓
React Frontend (pixel-art UI)
    ↓ SSE
FastAPI Backend (api.py)
    ↓
DebateOrchestrator
    ├── shared_history (tek kaynak)
    ├── _build_history_for("professor")  → Gemini API
    └── _build_history_for("student")    → Gemini API
    ↓
Gemini 2.5 Flash (streaming)
    ↓
Yanıt → SSE → Frontend
```

**Shared History Yaklaşımı:** Her mesaj ortak bir listeye yazılır. API çağrısı öncesinde `_build_history_for()` ilgili ajanın perspektifini oluşturur — ajanın kendi mesajları `model`, diğerleri `user` olarak etiketlenir. Ardışık aynı role mesajlar otomatik birleştirilir.

---

## Teknoloji

| Bileşen | Teknoloji |
|---------|-----------|
| LLM | Google Gemini 2.5 Flash |
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | React 19, Tailwind CSS 4, Vite |
| Alternatif UI | Streamlit |
| Test | pytest, pytest-cov |
| Deploy | Docker, Hugging Face Spaces |
| Prompt Yönetimi | YAML (personas.yaml) |

---

## Kurulum

### Gereksinimler
- Python 3.11+
- Node.js 20+ (frontend için)
- Gemini API key ([aistudio.google.com](https://aistudio.google.com))

### Backend

```bash
git clone https://github.com/ravzaatasdemir/munazara.git
cd munazara/backend
pip install -r requirements.txt
cp .env.example .env
# .env dosyasını açıp GEMINI_API_KEY değerini yazın
```

**API'yi başlatın:**
```bash
python api.py
# http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
# http://localhost:3000
```

### Streamlit (alternatif)

```bash
cd backend
streamlit run ui/app.py
# http://localhost:8501
```

### Docker

```bash
docker build -t munazara .
docker run -p 8501:8501 -e GEMINI_API_KEY=your_key munazara
```

---

## Test

```bash
cd backend
pytest -v
```

30+ test: ajan davranışları, tartışma akışı, role sequence, keyword matching, science routing, error recovery, transcript trimming, summary streaming, soru limiti, retry politikası.

---

## Dosya Yapısı

```
munazara/
├── backend/
│   ├── agents/
│   │   ├── demo_data.py          # Demo tartışma verisi
│   │   ├── exceptions.py         # Custom exception hiyerarşisi
│   │   ├── gemini_client.py      # Gemini API wrapper (lazy, thread-safe)
│   │   ├── models.py             # Dataclass: Message, HistoryEntry
│   │   ├── orchestrator.py       # Tartışma orkestratörü (v5)
│   │   ├── personas.py           # YAML'dan prompt yükleme
│   │   └── personas.yaml         # Karakter tanımları + keyword setleri
│   ├── tests/
│   │   └── test_basic.py         # 30+ birim test
│   ├── ui/
│   │   └── app.py                # Streamlit arayüzü
│   ├── api.py                    # FastAPI REST backend (SSE)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # React ana bileşen
│   │   ├── index.css             # Pixel-art tema
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | /api/start | Tartışma başlat (SSE stream) |
| POST | /api/skip | Turu atla — Kamil sorar (SSE) |
| POST | /api/ask | Kullanıcı soru sorar (SSE) |
| GET | /api/status/{id} | Oturum durumu |
| POST | /api/summary/{id} | Özet üret (SSE) |
| DELETE | /api/session/{id} | Oturumu sil |
| GET | /api/demo | Demo verisi (API key gereksiz) |

---

## Takım

| Üye | Sorumluluk |
|-----|-----------|
| Kişi A | Backend: Gemini API, orkestrasyon, FastAPI, test |
| Kişi B | Frontend: React UI, Streamlit, deploy |
| Kişi C | Prompt mühendisliği, karakter tasarımı, test, dokümantasyon |

---

*Münazara — Ezberden kavrayışa, tartışarak öğren.*
