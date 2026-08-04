# OS Upgrade Impact Analyzer 🐧

Ubuntu LTS yükseltmelerinin (ör. 22.04 → 24.04) etkisini **resmi kaynaklara
dayanarak** ve **makineye özel** analiz eden RAG + agent sistemi.

**Ana kural: uydurma yok.** Her iddia kaynak atıflıdır (`[URL, çekilme tarihi]`);
kaynağı doğrulanamayan iddialar mekanik olarak reddedilir ve raporda
"kaynak bulunamadı" olarak görünür.

## Ne yapar?

1. Sistemini otomatik tespit eder (`/etc/os-release`) — **uzak sunucuları da**
   (SSH, agentless: hedefe hiçbir şey kurulmaz)
2. Elle kurduğun paketleri çıkarır (`apt-mark showmanual`) — lokalde ya da uzakta
3. Hedef sürümün resmi release notes'unu çeker (bayatsa otomatik yeniler — TTL)
4. Değişiklikleri vektör araması ile bulur (Chroma + MiniLM)
5. **Senin paketlerinle kesiştirir** ("SENİN apache2'n şöyle etkilenecek")
6. Lokal LLM (qwen2.5:7b) kaynak atıflı rapor yazar
7. Grounding katmanı her iddiayı ÜÇ seviyede doğrular (kaynak atfı + sözcüksel
   varlıklar + kosinüs) — kaynaksız iddia rapora giremez; şüpheli detaylar
   ⚠️ FLAG ile işaretlenir

## Mimari

```
hedef seçimi (lokal / SSH host) ─► validate_host ─► is_reachable (değilse dur)
detect_os(host) ────────┐
apt-mark (host) ────────┤
hedef sürüm ────────────┼─► LangGraph agent ─► grounding ─► FastAPI ─► Streamlit
                         │     │ freshness → (gerekirse scrape)
                         │     │ RAG retrieval (Chroma, 328 chunk)
                         │     │ paket kesiştirme (sözcüksel → RAG)
                         │     ▼
                         │   qwen2.5:7b (Ollama, lokal) → iddialar + chunk atıfları
```

Desteklenen sürümler: **18.04, 20.04, 22.04, 24.04** (LTS zinciri;
`config/versions.json`'a satır ekleyerek genişletilir).

## Kurulum

```bash
# 1) Python ortamı
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2) Lokal LLM
# https://ollama.com adresinden Ollama kur, sonra:
ollama pull qwen2.5:7b

# 3) Ayarlar (opsiyonel)
cp .env.example .env    # TTL, model adları, portlar
```

## Kullanım

```bash
# 1) Veriyi çek + indeksle (ilk sefer; embedding modeli otomatik iner ~90MB)
python -c "from src.scraper.freshness import get_versions_data; get_versions_data(['18.04','20.04','22.04','24.04'])"
python -m src.rag.vector_store

# 2) API'yi başlat (Swagger: http://localhost:8010/docs)
uvicorn src.api.main:app --port 8010

# 3) Arayüzü başlat (http://localhost:8501)
streamlit run src/ui/app.py
```

Arayüzsüz hızlı deneme:
```bash
curl -X POST http://localhost:8010/analyze \
  -H 'Content-Type: application/json' \
  -d '{"target_version": "24.04"}'

# Uzak sunucu analizi (SSH anahtarı kurulu olmalı; hedefe hiçbir şey kurulmaz):
curl -X POST http://localhost:8010/analyze \
  -H 'Content-Type: application/json' \
  -d '{"target_version": "24.04", "host": "kullanici@192.168.1.10"}'
```

Uzak hedefler için: SSH anahtarını `ssh-copy-id kullanici@ip` ile kur; isteğe
bağlı olarak `config/hosts.json.example` dosyasını `config/hosts.json` olarak
kopyalayıp kendi sunucularını etiketli ekle — UI dropdown'ında görünür
(`hosts.json` kişisel olduğu için git'e girmez).

## Testler

```bash
python -m pytest -q                # tümü (lab VM'leri kapalıysa lab testleri
                                   # otomatik SKIP — suite yeşil kalır)
python -m pytest -m "not lab" -q   # sadece birim testleri (lab'sız hızlı tur)
python -m pytest -m lab -q         # sadece gerçek lab entegrasyonu (SSH)
python tests/embedding_comparison.py          # model kıyası (recall@5 tablosu)
python tests/calibrate_lexical.py             # grounding sözcüksel kalibrasyonu
```

## Proje yapısı

| Dizin | İçerik |
|---|---|
| `src/detector/` | Sistem tespiti + paket envanteri (çift-mod: lokal/SSH, deterministik) |
| `src/remote/` | SSH çalıştırma katmanı + host doğrulama (enjeksiyon koruması) |
| `src/scraper/` | Resmi kaynak scraping (2 format: Sphinx + eski wiki) + TTL cache |
| `src/rag/` | Token-bazlı chunking, embeddings, Chroma store + retrieval |
| `src/agent/` | LangGraph akışı, tool'lar, LLM raporu, grounding |
| `src/api/` | FastAPI (`/detect`, `/packages`, `/versions`, `/analyze`) |
| `src/ui/` | Streamlit arayüzü |
| `docs/` | Mimari kararlar, changelog, senaryo sonuçları, demo akışı |

Ayrıntılar: [docs/architecture.md](docs/architecture.md) ·
[docs/CHANGELOG.md](docs/CHANGELOG.md) ·
[docs/scenario-results.md](docs/scenario-results.md) ·
[docs/demo.md](docs/demo.md)
