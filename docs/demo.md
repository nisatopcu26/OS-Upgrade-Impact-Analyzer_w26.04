# Demo Akışı (5 dakika) — Sunum Kılavuzu

## Hazırlık (sunumdan önce)

```bash
cd OS_Analyzer && source .venv/bin/activate
ollama list                                   # qwen2.5:7b görünmeli
for vm in ubuntu18.04 ubuntu20.04 ubuntu22.04 ubuntu24.04; do virsh start $vm; done
uvicorn src.api.main:app --port 8010 &        # API
streamlit run src/ui/app.py &                 # UI → http://localhost:8501
```
Yedek: canlı demo çökerse `docs/scenario-results.md` tablosu + ekran görüntüleri.
Lab VM'leri `config/hosts.json`'da etiketli; IP'ler MAC bazında sabitlendi.

## Akış

**1. Problem (30 sn).** "Ubuntu sürüm yükseltmek riskli — hangi paketim
bozulacak? Release notes yüzlerce satır. Bu sistem, resmi kaynakları okuyup
BENİM makineme özel rapor çıkarıyor ve asla uydurmuyor."

**2. Arayüz (1 dk).** localhost:8501 aç:
- Sürüm otomatik tespit edildi (22.04) — kullanıcı hiçbir şey girmedi
- 163 kurulu paket bulundu (`apt-mark showmanual`)
- Hedef "24.04" seç → **Analiz et**

**3. Analiz beklerken mimariyi anlat (1.5 dk).** Spinner dönerken:
- Freshness: veri 7 günden eskiyse otomatik yeniden scrape (TTL)
- RAG: 328 chunk, token-bazlı bölme, Chroma'da sürüm filtreli arama
- Paket kesiştirme: 163 paket → sözcüksel ön-eleme → ~12 aday → hedefli arama
- LLM lokal (qwen2.5:7b) — veri dışarı çıkmıyor

**4. Rapor (1.5 dk).** Şunları göster:
- ⚠️ "Senin makinende etkilenen: apache2, gcc, openssh, php"
- Bir iddiayı aç → kaynak linki + **çekilme tarihi** (grounding kanıtı)
- "Doğrulanmış / Reddedilen" sayaçları

**5. Uzaktan analiz (1 dk) — v2 yeteneği.** Dropdown'dan "Lab: Ubuntu 22.04
(web sunucu)" seç:
- 🟢 "Bağlandı" göstergesi + sunucunun KENDİ envanteri (29 paket, apache2/nginx/
  php/postgresql) — hedefe hiçbir şey kurulmadı (agentless, SSH ile okundu)
- Rapor başlığında hedef host görünüyor; etkilenenler O sunucunun paketleri
- Ekstra vuruş: "Lab: Ubuntu 24.04" seç → "zaten en güncel LTS" kartı
  (downgrade önermiyor); bir VM'i kapat → 🔴 "erişilemedi", analiz kilitli

**5b. Zincir analizi (1 dk) — yeni yetenek.** "Lab: Ubuntu 18.04 (legacy)" seç,
hedef 24.04:
- Seçim anında uyarı kartı: "Resmi yol 18.04 → 20.04 → 22.04 → 24.04 —
  doğrudan atlanamaz" (sistem kendi kapsam sınırını söylüyor)
- "🔗 Zinciri analiz et (3 bacak)" işaretle → bacak bacak sekmeli rapor;
  her bacak KENDİ envanteriyle analiz edilir
- Vuruş cümlesi: envanter bacaklar arasında release notes'a dayalı evrilir —
  pptpd 24.04 bacağında düşer, kanıtı da yanında ("pptpd and bcrelay have
  been removed") — tahmin değil, kaynaklı model

**6. Uydurmama kanıtı (1 dk) — en güçlü an.** İki şey:
- `pytest tests/test_grounding.py -v` → sahte chunk_id RED, kaynaksız iddia RED,
  uydurma terim RED, aşırı-hassas sürüm FLAG
- Senaryo 2 hikâyesi: "sahte sunucu envanteriyle 20.04→22.04 sordum; release
  notes o paketleri anlatmıyor → sistem BOŞ döndü, uydurmadı"

## Dört güçlü anekdot (sunuma serpiştir)

**1. "Tailscale şüphesi":** Raporda "Apache mod_md, tailscale daemon ile
sertifika yönetimi destekliyor" iddiası uydurma gibi görünüyordu (mod_md ACME
işi, tailscale VPN aracı — alakasız duruyor). Kaynak atıfına gidildi: ifade
Ubuntu'nun resmi sayfasında BİREBİR var — Apache 2.4.58, mod_md'ye gerçekten
Tailscale sertifika desteği ekledi. Ders: *kaynak atıfı sayesinde şüpheli
iddia 30 saniyede doğrulanabiliyor.* Uydurma sanılan şey gerçek çıktı.

**2. "GCC süslemesi yakalandı":** LLM, GCC 14 iddiasına kaynakta olmayan
"security-hardening features" süslemesi ekledi. Kosinüs kontrolü 0.543 ile
geçirdi; sözcüksel varlık katmanı (`unverified_entity`) yakalayıp RED'ledi —
rapor bunu "kaynak bulunamadı" notunda dürüstçe gösterdi. Ders: *sistem kendi
LLM'inin kısmi halüsinasyonunu üretimde yakalıyor.* Kanıt:
`docs/accuracy-audit.md` (20/20 sadık).

**3. "Kalibre etmeden eşik koymadım" (grounding v2.1):** Yeni sözcüksel
kuralları koda bağlamadan önce 20 elle-doğrulanmış gerçek iddiada ölçtüm —
üç iterasyonda "long-term" gibi tire-varyantı yanlış alarmları ayıkladım
("security-hardening" yakalaması testle korunarak). Sonuç: 60 iddialık final
denetimde 0 yanlış alarm, sentetik uydurmaların tamamı yakalanıyor. Canlıda
yeni bir kabiliyet de doğdu: kaynak "Python 3.8" derken LLM "3.8.2" yazdı —
sistem iddiayı silmedi ama detayı ⚠️ FLAG'ledi (`overprecise_version`):
*kanıt gücü kademeliyse ceza da kademeli olmalı.*

**4. "Uydurma yok, ağda da güvenlikte de" (uzaktan analiz):** Dört VM'lik
lab'da agentless analiz: web sunucusunun kendi envanterinden apache2/nginx/
php/postgresql yakalandı — hedefe hiçbir şey kurulmadı. Bir VM'i kapatınca
sistem rapor uydurmak yerine LLM'i hiç çağırmadan 502 "bağlanılamadı" dedi.
Host alanına `-oProxyCommand=...` enjeksiyonu denendiğinde istek API sınırında
422 ile öldü — testte enjeksiyonun subprocess'e HİÇ ulaşmadığı da kanıtlı.
Bonus: 18.04 VM'inde 469 paketlik "kirli" gerçek envanter sorunsuz analiz
edildi (aday sınırı 15'e dayandı — bilinçli, belgeli sınır).

## Muhtemel sorular

- **Neden MiniLM?** Kendi verimde ölçtüm: recall@5 1.00 vs bge 0.90
  (`tests/embedding_comparison.py`). Genel benchmark değil, deneysel kanıt.
- **LLM yanlış bir şey yazarsa?** Grounding her iddiayı mekanik doğrular:
  atıf yok → RED, atıf uydurma → RED, atıf iddiayı desteklemiyor
  (kosinüs < 0.30) → RED. Eşik körlemesine değil, skor gözlemiyle seçildi
  (alakalı ≥ 0.34, alakasız ≤ 0.28).
- **Yeni sürüm nasıl eklenir?** `config/versions.json`'a bir satır +
  `build_index()` — kod değişikliği yok.
- **Neden iki parser?** 20.04 ve öncesi eski MoinMoin wiki'de, 22.04+
  yeni Sphinx sitesinde — iki farklı HTML dünyası.
- **Uzak sunucuya bir şey kuruyor musun?** Hayır — agentless. SSH ile sadece
  iki şey OKUNUR (`/etc/os-release`, `apt-mark showmanual`); RAG/LLM/grounding
  kontrol düğümünde. Sunucu envanteri de makinede kalır (lokal LLM).
- **host alanına zararlı bir şey yazılırsa?** `-` ile başlayan/boşluklu her
  string hem API sınırında (pydantic, 422) hem `run_remote` içinde reddedilir —
  OpenSSH'in argüman enjeksiyonu yüzeyi kapalı; subprocess'e ulaşmadığı testli.
- **VM'ler kapalıyken testler?** Lab testleri `pytest -m lab` marker'lı ve
  erişilemeyince otomatik SKIP — 56 testlik suite lab'sız da yeşil.
