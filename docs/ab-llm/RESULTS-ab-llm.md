# S4 — LLM A/B: qwen2.5:7b (kilitli) vs llama3.1:8b (2026-07-29)

**Düzenek:** 3 M8 senaryosu × 2 model × 3 tekrar = 18 koşu, `tests/ab_llm.py`
(subprocess izolasyonu, `ollama stop` disiplini, RAM bekçisi). Envanter:
araştırma koşularının dondurduğu liste (rag_layer_bench/data/inventory_real.json).
**Konfigürasyon: GÜNCEL varsayılanlar** — bge-small + eşik 0.60 + S3 sözcükseli.
Bu yüzden mutlak sayılar araştırma koşularıyla (MiniLM + 0.30 + S3-öncesi)
bire bir kıyaslanamaz; A/B içsel olarak geçerli (iki modelde tek değişken LLM).
Donanım: RTX 3050 Laptop 4 GB VRAM / 15 GB RAM.

## Özet tablo

| Metrik | qwen2.5:7b (845dbda0ea48) | llama3.1:8b (46e0c10c039e) |
|---|---|---|
| Koşu (ok/fail) | 9/0 | 9/0 |
| Toplam taslak iddia | 67 | 68 |
| Doğrulanan | 61 | 62 |
| **Geçme oranı** | **0.910** | **0.912** |
| **Doğrulanan/dakika** | **5.76** | **2.50** |
| Ortalama süre/koşu | 70.6 s | 165.2 s (~2.3×) |
| RED dağılımı | 2 unverified_entity + 4 fabricated_term | 6 fabricated_term |
| **0-iddia koşusu (JSON çökmesi)** | **0/9** | **2/9** (s3 legacy #1, #2) |

## Bulgular

1. **Geçme oranı farkı yeni konfigde KAPANDI:** araştırmada (eski konfig)
   llama 0.885 vs qwen 0.818 idi (Δ+0.067). Yeni konfigde ikisi de ~0.91 —
   S2 eşik kalibrasyonu + S3 sözcüksel yumuşatma, araştırmadaki denetimin
   "yanlış-RED ~%17, tamamı sözcüksel katılık" bulgusuyla tutarlı biçimde
   her iki modelin haksız RED'lerini temizledi ve qwen'in açığını kapattı.
2. **Hız farkı aynen duruyor:** llama ~2.3× yavaş (VRAM'e sığmıyor);
   doğrulanan/dakika qwen 5.76 vs llama 2.50.
3. **Yeni güvenilirlik sinyali:** llama, legacy senaryosunun (18.04→20.04,
   469 paketlik gürültülü girdi değil — sahte legacy listesi ama en uzun
   prompt) 3 tekrarının 2'sinde parse edilemeyen çıktı üretti → 0 taslak
   iddia (elle tamir yok ilkesi: parse hatası da veridir). qwen 9/9 geçerli
   JSON üretti. temp=0'a rağmen tekrarlar arası fark Ollama nondeterminizmi.
4. **`model` alanı (S4 şema ekesi) sahada doğrulandı:** 18 koşunun 18'inde
   rapor, env ile istenen modeli beyan etti (0 uyuşmazlık uyarısı).

## Karar

**qwen2.5:7b kilitli karar OLARAK KALIR — artık ölçülmüş gerekçeyle:**
yeni konfigde grounding kalitesi eşit (0.910 vs 0.912), hız 2.3× üstün,
JSON güvenilirliği tam (9/9 vs 7/9). Araştırmadaki "llama daha yüksek geçme
oranı" avantajı, gürültü kaynağı (sözcüksel katılık) giderilince kayboldu.

*Damga notu: qwen özet dosyasındaki digest, `model_digest()`'in startswith
hatası yüzünden ilk yazımda q8_0 satırını yakalamıştı; düzeltildi
(digest_note alanı). Koşuların doğru modelle yapıldığı her koşuda raporun
`model` alanıyla doğrulanmıştı.*
