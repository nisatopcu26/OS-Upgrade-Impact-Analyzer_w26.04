# Changelog

Bu dosya, projenin ana rapor(lar)ında ("her anlamlı adımı tarih-saatiyle
docs/CHANGELOG.md'ye işledim") atıfta bulunulan kayıt defteridir. Dosya
2026-08-21 tarihine kadar fiilen tutulmamış — geriye dönük olarak, çalışma
günlüğü (session_log.md) ve bu tarihten sonraki oturumlar birleştirilerek
oluşturulmuştur. Her giriş: ne yapıldı, neden yapıldı, kanıtı ne, kod
değişti mi.

---

## 2026-08-14 – 2026-08-18 — Ubuntu 26.04 LTS Desteği Eklendi

**Ne yapıldı:**

**Test ortamı kuruldu:** UTM (QEMU, ARM64) ile 3 ayrı Ubuntu VM'i
(26.04, 24.04, 22.04), her birine Mac'ten anahtar tabanlı SSH erişimi
sağlandı (projenin agentless mimarisine uygun). Kurulum sırasında yanlış
mimarili ISO, boot döngüsü ve klavye düzeni sorunları çözüldü.

**26.04 desteği eklendi:** `config/versions.json`'a ilk kayıt (`sphinx`
formatı) eklendi.

**5 gerçek hata bulundu ve düzeltildi:**

| # | Bulgu | Çözüm |
|---|-------|-------|
| 1 | `build_index()` hiçbir yerde otomatik tetiklenmiyordu — yeni sürüm eklense bile chunk üretilmiyordu (LLM 0 kaynakla uyduruyordu). | `node_refresh`'e otomatik kontrol eklendi: chunk yoksa kendiliğinden indeksler. |
| 2 | 26.04'ün asıl release notes içeriği ayrı bir sayfaya (`summary-for-lts-users/`) taşınmıştı; scraper görmüyordu (yalnız 5 chunk). | `extra_urls` desteği eklendi. Chunk sayısı 5→126. |
| 3 | Chunk kimliğinin `p1-` öneki modelin atıf başarısını düşürüyordu. | Önek → `-src1` soneğine çevrildi. Kaynak sadakati %71→%88 (9 tekrar). |
| 4 | `.env` hiç okunmuyordu (`load_dotenv()` çağrısı yoktu). | `src/api/main.py` başına eklendi. |
| 5 | Rapordaki `"model"` alanı her zaman global `LLM_MODEL`'i gösteriyordu, senaryo-bazlı seçim olsa bile. | `AgentState`'e `used_model` eklendi. |

**Metodoloji (ölçülmeden karar verilmedi):**
1. Prompt'a "detay uydurma" yasağı → test edildi (3 tekrar): %75→%71 → **geri alındı**.
2. `section_id` önek→sonek → 9 tekrar: %71→%88 → **tutuldu**.
3. qwen2.5:7b vs llama3.1:8b karşılaştırması (9'ar tekrar): llama3.1
   24.04→26.04'te daha iyi, ama 22.04→24.04'te chunk_id önekini
   tutarsız kopyaladığı görüldü.
4. Kök neden (Bulgu #5) bulundu, düzeltildi.
5. **Senaryo-bazlı model seçimi** (`MODEL_OVERRIDES`) eklendi: 24.04→26.04
   için llama3.1:8b, diğerleri için qwen2.5:7b → zincir testiyle doğrulandı.

**Model performansı (düzeltme sonrası):**
- 22.04→24.04: qwen2.5:7b, 8/8, ~34s
- 24.04→26.04: llama3.1:8b, 11/11 (%100, 9 tekrarda tutarlı), ~30-32s
- Tam zincir 22.04→24.04: 7/7 (%100); tam zincir 24.04→26.04: 11/11 (%100)
- Not: qwen kaynakta olmayan terim/versiyon uyduruyor, llama3.1 zaman
  zaman chunk kimliğinin sürüm önekini atlıyor — model aileleri farklı
  tarzda başarısız oluyor.

**Test tabanı doğrulaması:** 112 testlik pytest seti macOS'ta (102 passed,
3 failed — host bekleyen testler, doğal) ve gerçek Ubuntu VM'inde (105
passed, 0 failed) ayrı ayrı koşuldu; başarısızlıkların ortam farkından
kaynaklandığı kanıtlandı.

**Neden yapıldı:** Ubuntu 26.04 LTS resmi yayınlandığı için projeye destek
eklenmesi ve gerçek ortamda uçtan uca doğrulanması gerekiyordu.

**Kanıt:** `session_log.md` (14-18 Ağustos 2026 çalışma günlüğü).

**Kod değişti mi:** Evet.
- `config/versions.json` — 26.04 kaydı + `extra_urls`
- `src/agent/nodes.py` — `node_refresh` otomatik indeksleme, `MODEL_OVERRIDES`, `used_model`
- `src/agent/graph.py` — `AgentState`'e `used_model` alanı
- `src/agent/grounding.py` — rapor `"model"` alanı `used_model`'den okunuyor
- `src/scraper/base_scraper.py` — `save_raw_html`'e `suffix` parametresi
- `src/scraper/ubuntu_scraper.py` — çoklu URL desteği, `section_id` sonek çözümü
- `src/api/main.py` — `load_dotenv()` eklendi
- `.env` — `LLM_MODEL=llama3.1:8b` denemesi, sonra `MODEL_OVERRIDES`'a taşındı

**Açık kalan konular (bu turda ele alınmadı):**
- `MODEL_OVERRIDES` şu an sadece 24.04→26.04 için tanımlı.
- llama3.1'in chunk_id önek atlama eğilimi daha büyük örneklemle araştırılmadı.
- 18.04→20.04 zinciri (eski wiki formatı) test edilmedi.
- Golden set + bootstrap CI metodolojisinin 26.04'e uyarlanması planlandı
  (sonraki oturumda ele alındı — bkz. 2026-08-21).

---

## 2026-08-21 — Ubuntu 26.04 Golden Set Doğrulaması + Grounding Kalibrasyonu

**Ne yapıldı:**
1. 26.04'ün 126 chunk'ı üzerinde, ana rapordaki 50-soruluk golden-set
   metodolojisiyle (Bölüm 13.1) birebir aynı disiplinde bir doğrulama seti
   kuruldu: 50 anchor (22 lexical / 28 semantic — ana setle aynı oran),
   kaynaktan birebir alınmış, her biri kendi chunk'ında benzersizliği
   doğrulanmış. (Bir önceki turun "sonraki adımlar" listesindeki açık
   maddenin karşılığı.)
2. Retrieval kalitesi ölçüldü: recall@1=0.960, recall@5=0.980, MRR=0.970
   (1000 tekrarlı bootstrap, %95 CI). Tek top-5-dışı kayıp (Linux kernel
   sorgusu) analiz edildi; 5 ek çok-parçalı bölüm probu ile bu önyargının
   izole bir vaka olduğu (sistematik olmadığı) doğrulandı.
3. Grounding katmanı, 26.04 hedefiyle sahte bir envanterle (M8 yöntemi)
   `analyze()` zincirinden uçtan uca geçirildi: 16 taslak iddia, 14
   doğrulandı, 1 FLAG, 2 RED. İki RED elle denetlendi (PDF'teki 35 RED /
   10 PASS denetim disiplinine sadık):
   - Postfix (unknown_chunk_id): model var olmayan bir chunk_id'ye
     (`26.04_postfix-src1_1`) atıf yaptı; içerik doğruydu, kimlik
     uydurulmuştu. Doğru RED — önceki turda bulunan "llama3.1 chunk
     kimliğini tutarsız kopyalıyor" bulgusuna yeni bir varyant.
   - RabbitMQ (fabricated_term: 'mitigation'): kaynak 'mitigate' (fiil),
     iddia 'mitigation' (isim) dedi. İçerik sadıktı ama sistem uydurma
     saydı. Yanlış-RED — kök nedeni aşağıda.

**Neden yapıldı:** 26.04 desteğinin, projenin kendi ölçüm disipliniyle
(mekanik ground truth, bootstrap CI, elle RED denetimi) doğrulanması
gerekiyordu; önceki turda yalnız chunk sayısının artması (5→126) ve
tekil senaryo ölçümleri (7/8, 11/11) vardı, sistematik bir golden-set
ölçümü henüz yapılmamıştı.

**Kanıt:** `data/eval/golden_set_26_04.json`, `data/eval/eval_results_26_04.json`,
`data/eval/grounding_report_26_04.json`, `data/eval/multi_chunk_probe.json`.

**Kod değişti mi:** Hayır (bu adımda) — yalnız ölçüm/doğrulama.

---

## 2026-08-21 — Kalibrasyon: -ate Fiil → -ion/-ation İsim Türetmesi

**Ne yapıldı:** RabbitMQ vakasının kök nedeni izole edildi: `_morph_variants()`
yalnız ÇEKİM tolere ediyor (çoğul, -ing, daemon-d); TÜRETME (fiilden isim
yapma, -ion/-ation eki) kapsam dışı. 5 çift test edildi (mitigate→mitigation,
optimize→optimization, authenticate→authentication, automate→automation,
generate→generation) — hiçbiri morph motoru tarafından yakalanmıyordu.
Bunlardan deprecation/configuration/integration/migration/isolation zaten
COMMON_WORDS'te olduğu için etkilenmemişti (tesadüfi kapsama, sistematik
değil).

Proje disiplinine (test-önce) sadık kalınarak düzeltildi:
1. Önce mitigation vakasını yakalayan adversarial test yazıldı
   (`test_ion_ation_derivation_not_flagged`) — beklendiği gibi KIRMIZI
   çıktı (0 verified, fabricated_term RED'i).
2. 5 kelime (mitigation, optimization, authentication, automation,
   generation) `COMMON_WORDS`'e dar ekleme olarak eklendi — önceki turdaki
   "made + compiler" kalibrasyonuyla aynı desen.
3. Test yeniden koşuldu: YEŞİL.

**Neden yapıldı:** Sadık bir iddia (RabbitMQ/mitigation) haksız yere
reddediliyordu; kaynağın söylediğini paraphrase eden meşru bir iddia,
morfoloji katmanının bilinçli sınırının (çekim ≠ türetme) dışında kaldığı
için "uydurma" sayılıyordu.

**Kanıt:**
- Regresyon: `tests/test_grounding.py` 29/29 yeşil (28 mevcut + 1 yeni).
- Platform doğrulaması: macOS'ta VE gerçek Ubuntu 24.04 VM'inde
  (nisa4@192.168.64.3) ayrı ayrı çalıştırıldı, ikisinde de 29/29.
- Proje geneli: `pytest -q` → 103 passed, 3 failed (macOS'a özgü
  host-testleri, önceki turdaki 102/3/7 referansıyla tutarlı), 7 skipped.
  Regresyon yok.

**Kod değişti mi:** Evet.
- `src/agent/_common_words.py`: 5 kelime eklendi (dar ekleme).
- `tests/test_grounding.py`: `test_ion_ation_derivation_not_flagged` eklendi.

---

## 2026-08-21 — Ana Rapora (OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor.docx) İki Yeni Bölüm Eklendi

**Ne yapıldı:** Docx formatındaki 26.04 raporu iki ayrı düzenleme turunda
güncellendi (mevcut stil/tablo formatına birebir uyularak, "Sonraki Adımlar"
başlığından hemen önce eklendi):

1. **"26.04 Golden Set Doğrulaması (Retrieval Kalitesi)"** — 50 soruluk
   golden-set metriklerini (recall@1/@5, MRR, %95 CI — genel/lexical/semantic
   kırılımıyla), Linux kernel top-5-kaybı vakasının kök neden analizini, ve
   5 parçalı çok-chunk probunun sonucunu (izole vaka, sistematik değil)
   içeren tablo + metin bölümü.
2. **"Grounding Testi: 26.04 Üzerinde Uçtan Uca"** + **"Kalibrasyon: -ate
   Fiil → -ion/-ation İsim Türetmesi"** — sahte envanterle çalıştırılan
   `analyze()` zincirinin sonuçları (16 taslak / 14 doğrulanan / 1 FLAG /
   2 RED), iki RED'in elle denetimi (Postfix=doğru RED, RabbitMQ=yanlış-RED),
   ve `mitigation` kalibrasyon düzeltmesinin tam anlatısı (test-önce →
   düzeltme → regresyon doğrulaması).

Her iki tur da doğrudan `word/document.xml` düzenlemesiyle yapıldı
(`unzip → merge_runs → XML düzenle → zip` iş akışı); XSD doğrulaması
(`validate.py`) ve görsel render kontrolü (`soffice --convert-to pdf` +
`pdftoppm`) her turda koşuldu.

**Neden yapıldı:** Bu oturumdaki ölçüm/test bulgularının (golden set,
grounding, kalibrasyon) kalıcı, paylaşılabilir bir kayda dönüşmesi için —
sözlü/chat-içi bulgular olarak kalmayıp raporun kendisinin bir parçası
olması.

**Kanıt:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v2.docx` (ilk tur),
`..._v3.docx` (ikinci tur) — ikisi de XSD doğrulamasından geçti
("All validations PASSED"), paragraf sayısı artışı izlenebilir
(76→106→126).

**Kod değişti mi:** Hayır — yalnız rapor dosyası (docx) güncellendi.

---

## 2026-08-21 — GitHub'a Aktarım (Kendi Fork)

**Ne yapıldı:** Proje `origin`'inin (`3RAV0/OS-Upgrade-Impact-Analyzer`)
başkasına ait olduğu fark edildi — oraya doğrudan push yapılmadı. Bunun
yerine kendi GitHub hesabında bir fork oluşturuldu
(`nisatopcu26/OS-Upgrade-Impact-Analyzer_w26.04`), yerel `origin` remote'u
buna yönlendirildi, tüm 2026-08-21 değişiklikleri (`_common_words.py`,
`tests/test_grounding.py`, ve öncesindeki commit edilmemiş 26.04 çalışması)
tek bir commit'te push edildi.

**Neden yapıldı:** Değişikliklerin kalıcı ve paylaşılabilir olması
gerekiyordu, ama orijinal repo sahibinin izni/yazma yetkisi olmadan
`3RAV0`'ın reposuna push yapmak uygun olmazdı.

**Kanıt:** `git push origin main` çıktısı — `8473ee9..d15bf1b main -> main`,
`https://github.com/nisatopcu26/OS-Upgrade-Impact-Analyzer_w26.04`.

**Kod değişti mi:** Hayır — yalnız remote/versiyon kontrolü işlemi.

---

## 2026-08-21 — CHANGELOG.md Oluşturuldu ve Konsolide Edildi

**Ne yapıldı:** Bu dosya oluşturuldu. Ana raporda "docs/CHANGELOG.md'ye
işledim" denmesine rağmen dosyanın fiilen hiç var olmadığı tespit edildi
(`git log --all -- docs/CHANGELOG.md` boş döndü, upstream repoda da yok).
İlk sürümü yalnız 2026-08-21 çalışmalarını kapsıyordu; ardından
14-18 Ağustos 2026 tarihli çalışma günlüğü (`session_log.md` — 26.04
desteğinin ilk eklenmesi, 5 hata düzeltmesi, model karşılaştırması,
test doğrulaması) geriye dönük olarak bu dosyaya işlenip tek, kronolojik
bir kayda konsolide edildi.

**Neden yapıldı:** Projenin kendi belgelediği disiplinin (tarih-saatli,
gerekçeli kayıt tutma) hem geçmiş hem gelecek çalışmalar için fiilen
uygulanabilir, tek bir kaynaktan okunabilir olması için.

**Kanıt:** Bu dosyanın kendisi; `session_log.md` (konsolidasyonun kaynağı).

**Kod değişti mi:** Hayır — yalnız dokümantasyon.

---

## 2026-08-24 — Arastirma: Linux Kernel Kaybinin Gercek Kok Nedeni

**Ne yapildi:** "Baslik seyrelmesi" hipotezini (coklu-chunk'li bolumlerin
devam chunk'larinda tekrarlanan baslik oneginin haksiz avantaj yarattigi)
test etmek icin `_embed_text_for()` fonksiyonu yazildi (yalniz embedding
girdisinden onek cikarma), 26.04 yeniden indekslendi, golden set tekrar
calistirildi. Sonuc: hicbir olculebilir degisiklik yok (recall@1/@5/MRR
birebir ayni, hedef chunk hala rank 7'de). Izole embedding testiyle onek
cikarmanin gercekten uygulandigi ama siralamayi degistirmeye yetmedigi
dogrulandi -- hipotez YANLISTI.

Gercek kok neden arastirildi: hedef chunk'ta "26.04" hic gecmiyordu (yalniz
gercek kernel surum numaralari: 6.8, 6.17, 7.0). Kardes chunk (_2) iki kez
"Added in version 26.04" diyordu -- sorgudaki "Ubuntu 26.04" ile yuzeysel
sayisal cakisma. Korpus capinda kontrol edildi: 126 chunk'in 21'i (%17)
kelimenin tam anlamiyla "version 26.04" iceriyor (cogunlukla release-metadata
etiketi, gercek surum bilgisi degil). Bu, daha once bulunan Intel GPU
vakasiyla (top-1'in alakasiz google-cloud chunk'i olmasi) ortusuyor.

Proje disiplinine sadik kalinarak (ise yaramayan geri alinir): etkisiz
duzeltme `git checkout` ile geri alindi, 26.04 orijinal embedding'lerle
yeniden indekslendi, golden set ayni sonucu verdigi dogrulanip kod/veri
baslangic durumuna dondu.

**Neden yapildi:** Onceki turda bulunan Linux kernel top-5-kaybi vakasinin
kok nedenini gercekten cozmek (sadece belgelemekle yetinmeyip).

**Kanit:** Izole embedding karsilastirmasi (query vs _0: 0.7149, query vs
_2 orig: 0.7456, query vs _2 stripped: 0.7318); korpus capinda "version
26.04" sayimi (21/126); `data/eval/eval_results_26_04.json` (once/sonra
birebir ayni).

**Kod degisti mi:** Hayir (net etki) -- bir degisiklik denendi, olculebilir
fayda saglamadigi icin geri alindi. `src/rag/vector_store.py` baslangic
durumuna ozdes.

**Acik konu:** Daha kapsamli bir duzeltme -- TUM chunk'lardan
"Added/Changed/Removed in version X.XX" bicimindeki release-metadata
boilerplate'ini embedding girdisinden cikarmak -- daha genis test
gerektiriyor (126 chunk'in %17'sini etkileyen bir degisiklik, tum golden
set uzerinde dikkatli olculmeli). Bu turda uygulanmadi.

---

## 2026-08-24 — Linux Kernel Kok Nedeni: Ikinci Deneme (Genis Duzeltme), Yine Basarisiz

**Ne yapildi:** Ilk denemenin (baslik seyrelmesi hipotezi) yanlis ciktigini
gosterdikten sonra, gercek teshise (126 chunk'in 21'i/%17 "version 26.04"
gibi release-metadata boilerplate iceriyor) dayanan ikinci, daha genis bir
duzeltme denendi: TUM chunk'lardan "Added/Changed/Removed in version X.XX."
kalibini (yalniz 26.04 degil tum surumler) embedding girdisinden cikaran
bir regex (`_VERSION_ANNOTATION_RE`) yazildi. 126 chunk'in 69'unu (%55)
etkiledi -- beklenenden fazla, cunku kalip tum surum etiketlerini
yakaliyordu.

**Sonuc:** Daha da kotu -- MRR 0.970->0.968, Linux kernel sorusu rank 7->8'e
dustu. Izole embedding testiyle nedeni bulundu: boilerplate cikarma hem
hedef hem kardes chunk'in benzerligini dusurdu (kardes: 0.7456->0.7418,
hedef: 0.6680->0.6599) -- ama hedef ORANTILI olarak daha fazla kaybetti,
cunku cikarilan etiketlerin cevresindeki baglamsal yogunluk da zayifladi.
Aradaki fark daralmak yerine genisledi.

**Ders:** "Gurultu azaltma" sezgisi, embedding benzerliginin cok boyutlu
dogasi nedeniyle her zaman beklenen yonde calismiyor -- bir chunk'tan metin
cikarmak, o chunk'i sorguya yaklastirmak yerine uzaklastirabiliyor da.

Proje disiplinine sadik kalinarak (ise yaramayan geri alinir, ikinci kez):
`git checkout` ile geri alindi, 26.04 orijinal embedding'lerle yeniden
indekslendi, golden set ayni sonucu (recall@1=0.960, recall@5=0.980,
MRR=0.970, rank 7) verdigi dogrulanip kod/veri baslangic durumuna dondu.

**Neden yapildi:** Ilk (dar) duzeltmenin basarisiz olmasi, teshisin kendisini
degil, duzeltme stratejisini sorgulamayi gerektiriyordu -- gercek teshis
(boilerplate cakismasi, %17 chunk) olcumle dogrulanmisti, o yuzden daha
genis bir uygulamasi denenmeye deger goruldu.

**Kanit:** Izole embedding karsilastirmasi (hedef: 0.6680->0.6599, kardes:
0.7456->0.7418); `data/eval/eval_results_26_04.json` (once/sonra); 69/126
chunk'in embedding girdisinin degistigi dogrulamasi.

**Kod degisti mi:** Hayir (net etki) -- ikinci deneme de geri alindi.
`src/rag/vector_store.py` baslangic durumuna ozdes (iki ayri hipotez
denendi, ikisi de olcumle elendi).

**Acik konu (iki tur sonrasi hala cozulmedi):** Linux kernel vakasinin kok
nedeni dogru teshis edildi ama embedding-girdisi duzeltmeleri (dar ve genis)
ikisi de ise yaramadi. Olasi sonraki yontemler: reranking katmani eklemek
(PDF Bolum 18'de projenin kendi 4-reranker karsilastirmasi kaydi var, ama
alan-spesifik korpusta zarar verdigi bulunmustu), ya da chunk sonek/onek
stratejisini degistirmek (bu turda denenmedi, chunk sinirlarina dokunmak
riskli bulundu).

**Rapor guncellemesi:** Bu ikinci tur, docx raporuna da islendi
(`OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v5.docx`); ilk turdan kalan
guncelligini yitirmis "acik konu" maddesi kaldirildi, tek guncel madde
birakildi.

---

## 2026-08-24 — Sert-Bolme Regresyon Testi

**Not:** Bu girisin ilk yazimi yanlislikla hosts.json bulgusuyla (2026-08-21, asagidaki ayri girise tasindi) tek baslik altinda birlestirilmisti; 2026-08-24'te tarih duzeltmesi yapildi, iki ayri gun/olay ayri girislere bolundu.

## 2026-08-24 — hosts.json Zincirleme Bulgusu

**Ne yapildi:**
1. Daha once ad-hoc dogrulanan "263>256" sert-bolme senaryosu (bkz. onceki
   giris), gercek MiniLM tokenizer'iyla calisan kalici bir pytest testine
   donusturuldu: `test_real_tokenizer_hard_split_never_exceeds_budget`
   (tests/test_rag.py). 13/13 test yesil, regresyon yok.
2. Bu turda hosts.json'daki placeholder host'lar (onceki giriste) gercek
   IP'lerle degistirilmisti. Bu, daha once hic calismamis bir lab testini
   (test_inventory_web_vm_profile) ilk kez fiilen calistirdi -- ve test,
   22.04 VM'inin apache2/nginx/php/postgresql icerdigi varsayimiyla
   basarisiz oldu.
3. SSH ile dogrudan kontrol edildi (`dpkg -l`, `apt-mark showmanual`):
   VM gercekten 28 paketlik minimal bir kurulumdu (ubuntu-server-minimal),
   hicbir web-sunucu bileseni kurulu degildi. Test, belirli yazilim
   varsaymak yerine mekanizmayi (kaynak, sayac tutarliligi, cekirdek
   paketlerin varligi) dogrulayacak sekilde yeniden yazildi.

**Neden yapildi:** (1) Sert-bolme senaryosu daha once yalniz elle
dogrulanmisti, kalici test kapsamina hic girmemisti. (2) hosts.json
duzeltmesi (onceki giris) beklenmedik bir yan etki yaratti -- kucuk,
masum bir altyapi duzeltmesi, daha once gizli kalan (hic calismadigi icin)
bir testin gecersiz varsayimini ortaya cikardi.

**Kanit:**
- `tests/test_rag.py`: 13 passed (12 mevcut + 1 yeni).
- `tests/test_remote_lab.py`: 5 passed, 4 skipped (20.04/18.04 kapali,
  dogal skip).
- Proje geneli `pytest -q`: 108 passed, 3 failed (yalniz macOS'a ozgu
  host-testleri), 4 skipped -- onceki turdaki 103'e gore +5 test artik
  gercekten kosuyor ve geciyor.
- `dpkg -l` / `apt-mark showmanual` ciktisi (192.168.64.4 uzerinde,
  28 paket, hepsi ubuntu-server-minimal cekirdegi).

**Kod degisti mi:** Evet.
- `tests/test_rag.py`: `test_real_tokenizer_hard_split_never_exceeds_budget`
  eklendi.
- `tests/test_remote_lab.py`: `test_inventory_web_vm_profile` yeniden
  yazildi (hardcoded paket listesi kaldirildi, mekanizma dogrulamasi
  eklendi).

**Ders:** Sessizce atlanan (skip) testler, calismaya basladiklarinda
supriz bulgular verebilir -- bu, projenin "sessizce atlama, acikca
goster" ilkesinin test altyapisindaki karsiligi. Kucuk bir duzeltme
(hosts.json) baska bir katmanda gizli kalmis bir sorunu acikca gosterdi.

**Rapor guncellemesi:** Bu bulgu docx raporuna da islendi
(`OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v6.docx`).

---

## 2026-08-24 — Ikinci Kanit Katmani: APT Breaks/Conflicts/Replaces/Provides

**Ne yapildi:** Release notes'un anlatmadigi ama gercek paket iliskilerinde
birebir var olan uyumluluk bilgilerini yakalamak icin yeni bir deterministik
kanit katmani eklendi (PDF'teki postgresql-12 bulgusunun genellestirilmis
hali). Once izole kesif yapildi: 26.04 VM'inde golden-set'teki 15 pakete
apt-cache show calistirildi, 10/15 (%67) gercekten faydali iliski verisi
tasidigi olculdu.

Uygulama: `src/detector/apt_relations.py` (cift modlu, host=None/host=str SSH)
gercek iliskileri ceker; `render_apt_relations_chunk()` bunu release-notes
chunk'lariyla AYNI sekilde (id, text, metadata) bicimlendirir, source_url'e
'apt-cache:paket' oneki eklenerek kaynagin serffafligi korunur.
`node_package_intersect`'e entegre edildi: hedef surumun referans VM'i
(config/hosts.json) SSH ile sorgulanir; erisilemezse SESSIZCE atlanir, yalniz
warnings'e eklenir (cokme yok).

4 test yazildi (`tests/test_apt_relations.py`): 3 saf mantik + 1 gercek 26.04
VM'ine karsi dogrulama. Tumu yesil.

**Bulgu (beklenmedik):** Ucdan uca dogrulandi -- node_package_intersect
gercekten apt-relations chunk'lari uretiyor ve package_hits'e ekliyor
(samba/postgresql/openssh-server/systemd/gcc/chrony/python3 icin). Ama
grounding testinde (llama3.1:8b) hicbir dogrulanan iddia bu yeni chunk turune
atif yapmadi -- veri pipeline'i sorunsuz calisiyordu ama model kullanmadi.
Prompt'a acik talimat eklendi ("APT metadata iceren kaynaklar icin mutlaka
iddia uret"), yine sonuc degismedi.

Kok neden arastirildi: ayni prompt qwen2.5:7b'ye gonderildiginde 12 iddianin
5'i apt-relations'a atif yapti -- biri (Samba/AD-DC uyari) YALNIZ apt
verisine dayaniyordu, release notes'ta hic olmayan bir bulgu uretti. Bu,
PDF'in "model aileleri farkli tarzda basarili/basarisiz oluyor" bulgusunun
somut yeni bir ornegi.

**Neden yapildi:** PDF'in postgresql-12 anekdotunu (release notes'un
soylemedigi ama gercek yukseltmeyi durduran paket) sistematik, tekrar
kullanilabilir bir kanit katmanina donusturmek icin.

**Kanit:** Izole `apt-cache show` probu (10/15 paket, %67 kapsama);
`tests/test_apt_relations.py` (4/4 yesil); izole `node_package_intersect`
cagrisi (7 apt-relations chunk uretildi); llama3.1 vs qwen2.5 karsilastirma
scripti ciktisi (5/12 iddia apt-relations atifli, qwen ile).

**Kod degisti mi:** Evet.
- `src/detector/apt_relations.py`: yeni dosya (`get_apt_relations`,
  `render_apt_relations_chunk`).
- `tests/test_apt_relations.py`: yeni dosya (4 test).
- `src/agent/nodes.py`: `_reference_host_for()` eklendi; `node_package_intersect`
  apt-relations katmanini cagiracak sekilde guncellendi; `PROMPT_TEMPLATE`'e
  apt metadata talimati eklendi.

**Acik konu:** llama3.1:8b'nin 24.04->26.04 senaryosundaki genel ustunlugu
(MODEL_OVERRIDES'in mevcut gerekcesi) bu bulguyla degismiyor, ama
paket-spesifik uyumluluk uyarilari icin secici model kullanimi (ucuncu
boyutlu MODEL_OVERRIDES) ileride arastirilabilir -- bu turda uygulanmadi.

**Rapor guncellemesi:** Bu bulgu docx raporuna da islendi
(`OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v7.docx`).

---

## 2026-08-24 — Ucuncu Kanit Katmani (NEWS.Debian) + Model-Bazli Kullanim Farkinin Kesin Kaniti

**Ne yapildi:**

1. **Quirk listesi incelendi, entegre edilmedi**: `DistUpgradeQuirks.py`
   (1538 satir, 40 fonksiyon) golden-set paketleriyle hic ortusmedi --
   fonksiyonlar dosya sistemi durumuna (`/snap/pc-kernel` varligi gibi) ve
   canli apt cache nesnesine bakiyor, paket-adi listesiyle temsil
   edilemiyor. Mevcut mimariyle uyumsuz, entegre edilmedi.

2. **Ucuncu kanit katmani eklendi (NEWS.Debian)**: `src/detector/news_debian.py`
   (.deb indirip kurmadan icini acar, en guncel girdiyi cikarir) +
   `tests/test_news_debian.py` (4/4 yesil, biri gercek 26.04 VM'ine karsi).
   Samba'nin NEWS.Debian'i AD-DC bolunmesini dogal dilde anlatiyordu --
   ayni gercegi (release notes + apt Breaks) ucuncu bagimsiz kaynaktan da
   dogrulayan bir capraz-dogrulama ornegi.

3. **Model-bazli kullanim farki kesin olarak olculdu**: 26.04 grounding
   testinde (llama3.1:8b) sonuc mukemmeldi (15/15, 0 RED, 0 FLAG) ama
   yine hicbir iddia apt-relations/news-debian'a atif yapmadi (ucuncu
   ardisik deneme, ayni sonuc). Bunu kesin test etmek icin MODEL_OVERRIDES
   disindaki 22.04->24.04 senaryosu (varsayilan qwen2.5:7b) ayni katmanlarla
   test edildi: **5/12 iddia (%42)** apt-relations/news-debian'a atif yapti,
   biri iki kaynagi birden sentezledi (Chrony).

**Ornek deger (qwen2.5:7b, 22.04->24.04):**
- "Upgrade to 24.04 will break samba-ad-provision if its version is older
  than 2:4.19.5+dfsg" (apt-relations) -- release notes'ta olmayan kesin
  surum esigi.
- "Chrony now requires each line of a source file to be terminated by a
  trailing newline" (news-debian) -- tamamen NEWS.Debian'dan gelen
  operasyonel tuzak bilgisi.

**Neden yapildi:** Ikinci kanit katmaninin (apt-relations) ilk turda
kullanilmama bulgusunu daha genis test etmek -- format farkinin (kisa/teknik
vs dogal dil) sonucu degistirip degistirmedigini, ve model secimiyle
iliskisini kesinlestirmek.

**Kanit:**
- `data/eval/grounding_report_26_04.json` (llama3.1, 15/15, apt/news atifi yok).
- `data/eval/grounding_report_22_24.json` (qwen2.5, 12/12 draft, 5 apt/news atifli).
- `tests/test_news_debian.py` (4/4 yesil).
- Izole `dpkg-deb -x` incelemesi (samba/squid/dovecot-core'da NEWS.Debian
  gercekten var, icerik dogrulandi).

**Kod degisti mi:** Evet.
- `src/detector/news_debian.py`: yeni dosya (`get_news_debian`,
  `render_news_debian_chunk`).
- `tests/test_news_debian.py`: yeni dosya (4 test).
- `src/agent/nodes.py`: `node_package_intersect`'e news-debian cagrisi
  eklendi (apt-relations'in hemen ardindan, ayni ref_host uzerinden).
- `scripts/test_grounding_22_24.py`: yeni dosya (22.04->24.04 icin
  karsilastirma script'i).

**Sonuc:** Iki yeni kanit katmani (apt-relations + news-debian) projenin
COGU senaryosunda (qwen2.5:7b varsayilan model oldugu icin) gercek deger
uretiyor; yalniz MODEL_OVERRIDES'la override edilen tek senaryoda
(24.04->26.04, llama3.1:8b) su an kullanilmiyor. Bu, llama3.1:8b'nin genel
kaynak sadakati ustunlugunun (mevcut MODEL_OVERRIDES gerekcesi) olculmus
bir odunlesim tasidigini gosteriyor -- karar hala gecerli ama artik bu
odunlesim acikca belgeleniyor.

**Acik konu:** Uçuncu boyutlu bir model secimi (paket-spesifik uyumluluk
uyarilari icin secici olarak qwen'e basvurma) ileride arastirilabilir --
bu turda uygulanmadi.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v8.docx`.

---

## 2026-08-24 — Quirk Listesi: Donanim Profili Dogrulamasi (Ek Bulgu)

**Ne yapildi:** Quirk fonksiyonlarinin kontrol ettigi dosya/donanim yollari
(`/run/snapd.socket`, `/usr/bin/flatpak`, `/snap/pc-kernel`,
`/proc/device-tree`, `/boot/firmware`) uc lab VM'inde (26.04, 24.04, 22.04)
salt-okunur olarak kontrol edildi (yalniz `test -e`, hicbir degisiklik yok).

**Bulgu:** En riskli/ilginc quirk'lerin (Raspberry Pi boot duzeni, TPM disk
sifrelemesi, RISC-V/IBM Z mimarisi kontrolleri) tetikleyicisi olan
donanim-spesifik yollarin (`pc-kernel`, `device-tree`, `boot/firmware`)
HICBIRI uc VM'de de bulunmadi. Snapd soketleri her yerde aktifti, flatpak
hicbirinde kurulu degildi, `xdg-screensaver` yalniz masaustu VM'lerinde
(26.04/24.04) vardi, sunucu-etiketli 22.04'te yoktu.

**Neden yapildi:** Onceki turda quirk listesinin mevcut mimariyle uyumsuz
oldugu (paket-listesi degil dosya sistemi/donanim durumuna baktigi) bulunmus,
entegre edilmemisti. Bu, o kararin bizim OZEL test ortamimiz icin de
gecerliligini ek kanitla dogruluyor: lab VM'lerimiz genel amacli QEMU/ARM64
sanal makineler, gercek Raspberry Pi ya da TPM-FDE donanimi degil -- yani
quirk katmani gercek bir yukseltmede bile bizim ortamimizda dogal olarak
"bos" kalirdi.

**Kanit:** Uc VM'de calistirilan `test -e` dogrulama komutlari (bu mesajin
kendisi -- terminal ciktisi kanit).

**Kod degisti mi:** Hayir -- yalniz salt-okunur dogrulama, hicbir dosya/VM
degistirilmedi.

**Onemli not:** Bu, quirk listesinin DEGERSIZ oldugu anlamina gelmiyor --
gercek kullanicilarin (Raspberry Pi, TPM-FDE kullananlar) bu kaynaktan fayda
gorebilecegi sonucu degismiyor. Yalniz bizim spesifik lab donanim profilimiz
icin bu katmanin dogal olarak devre disi kalacagi netlesti.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v9.docx`
(mevcut quirk bolumune ek not olarak islendi).

---

## 2026-08-25 — Dorduncu Kaynak: Gercek do-release-upgrade Yurutumesi

**Ne yapildi:** Listedeki dorduncu kaynagi (do-release-upgrade log'u) test
etmek icin, 24.04 VM'inin bir kopyasi alindi (orijinal VM'e hic dokunulmadan
-- UTM Duplicate ozelligiyle), gercek bir 24.04->26.04 yukseltmesi
calistirildi. Varsayilan `Supported: 0` bayragi (Canonical'in 26.04'u henuz
resmi olarak "yukseltmeye acik" isaretlememis olmasi -- LTS'lerde standart,
ilk point-release'e kadar suren bir politika) `-d` (developer/test)
bayragiyla asildi.

**Sonuc:** Yukseltme sorunsuz tamamlandi: 206 yeni paket, 1405 guncelleme,
19+166 kaldirma, hicbir hata/uyari log'da gorulmedi. `VERSION_ID="26.04"`
dogrulamasiyla gercek gecis teyit edildi. Log dosyalari (`main.log`,
`history.log`, `apt.log` vb.) `/var/log/dist-upgrade/`'den indirilip
projeye kaydedildi (`data/raw/dist_upgrade_history_24_26.log`,
`data/raw/dist_upgrade_main_24_26.log`).

**Karar:** Bu log'u besinci bir kanit katmanina (apt-relations, news-debian
gibi) donusturme karari supervizor geri bildirimine birakildi -- iki nedenle:
(1) tahmini sure 3-5 saat, sunum oncesi 5 gunluk butcede ciddi bir pay;
(2) bu spesifik VM minimal bir kurulum oldugu icin (hosts.json bulgusunda
da gorulmustu) gercek bir "postgresql-12 tarzi" kritik blocker cikmadi --
parser yazilsa bile sonuc muhtemelen zayif olacak.

**Neden yapildi:** Supervizorun onerdigi dorduncu kaynagi (release notes'un
anlatmadigi, gercek yukseltme surecinde ortaya cikan bilgi) test etmek;
onceki uc kaynagin (apt-relations, news-debian, quirk listesi) ayni
metodolojisini tamamlamak.

**Kanit:** `/var/log/dist-upgrade/` gercek log dosyalari (indirilip
kaydedildi); `VERSION_ID="26.04"` dogrulamasi; terminal ciktisi (bu
oturumun kendisi).

**Kod degisti mi:** Hayir -- yalniz gercek sistem testi + log toplama.
Kod tabaninda degisiklik yok.

**Acik konu:** do-release-upgrade log parser'i -- gercek log alindi ve
dogrulandi, ama kanit-katmanina donusturme (candidate paketlerle
eslestirme, chunk formatina getirme, pipeline entegrasyonu) bu turda
uygulanmadi. Supervizor geri bildirimine gore oncelik verilebilir.

**Supervizore soruldu:** RHEL distro genislemesi kapsami (tam entegrasyon
mu, fizibilite analizi mi) ve bu dorduncu katmanin onceligi hakkinda
supervizore mesaj gonderildi, cevap bekleniyor.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v10.docx`.

---

## 2026-08-26 — RHEL-Ailesi Genislemesi: Ilk Somut Ilerleme

**Ne yapildi:** Supervizor geri bildirimiyle (RHEL ailesi gercekten
calistirilacak, Sali sunumuna kadar somut ilerleme gerekiyor), gercekci ve
asamali bir plan baslatildi. Rocky Linux 10.2 (RHEL 10 ile birebir uyumlu,
ucretsiz, ARM64 destekli) VM'i UTM'de kuruldu, SSH erisimi diger lab
VM'leriyle tutarli sekilde saglandi.

**Bulgu 1 (detect_os):** Mevcut `detect_os()` fonksiyonu HICBIR kod
degisikligi yapilmadan Rocky'yi dogru tespit etti:
`detect_os(host='nisa@192.168.64.5')` -> `{'distro': 'rocky', 'version':
'10.2', 'source': 'os-release(remote)'}`. Mimarinin bastan dagitimdan
bagimsiz tasarlandiginin somut kaniti.

**Bulgu 2 (package_inventory):** Bu modul Debian-ailesine ozgu komutlara
(apt-mark, dpkg-query) bagliydi. RHEL karsiliklari once gercek VM'e karsi
dogrulandi: `dnf repoquery --userinstalled --qf '%{name}'` (sudo
gerektirmez) ve `rpm -q --qf '%{VERSION}'`. Modul distro tespitine gore
dogru komutu sececek sekilde genisletildi (`_is_rhel_family()` yardimci
fonksiyonu, `detect_os()`'a basvurarak).

**Kalite kontrolu:** Kod incelemesi sirasinda bir hata yakalandi ve
duzeltildi: `get_inventory()`'nin `source` alani RHEL'de bile hep
"apt-mark" yaziyordu (kopyala-yapistir kalintisi). Duzeltildi:
`source` artik "dnf(remote)" ya da "apt-mark(remote)", duruma gore dogru.

**Kalici testler:** `tests/test_rhel_family.py` yazildi (5 test,
test_remote_lab.py deseniyle, lab-isaretli): Rocky tespiti, dnf kaynak
etiketi, minimal kurulumun cekirdek paketleri, rpm surum sorgusu, Ubuntu
ailesinin regresyona ugramadigi. Tumu yesil.

**Regresyon kontrolu:** `pytest -m "not lab" -q`: 109 passed, 3 failed
(yalniz macOS'a ozgu, bilinen), 17 deselected (5 yeni RHEL lab testi + 12
eski Ubuntu lab testi). Sifir regresyon.

**Neden yapildi:** Supervizorun RHEL ailesi icin talep ettigi somut
ilerlemeyi, 5 gunluk sunum butcesi icinde gerceklestirilebilir, olculmus
adimlarla saglamak.

**Kanit:** Terminal ciktilari (bu oturumun kendisi); `tests/test_rhel_family.py`
(5/5 yesil); `config/hosts.json` guncellemesi (Rocky girdisi eklendi).

**Kod degisti mi:** Evet.
- `src/detector/package_inventory.py`: `_is_rhel_family()`, RHEL/Debian
  dallanmasi `list_manual_packages` ve `get_package_version`'a eklendi;
  `get_inventory()`'deki source hatasi duzeltildi.
- `tests/test_rhel_family.py`: yeni dosya (5 test).
- `config/hosts.json`: Rocky Linux 10.2 girdisi eklendi.

**Acik konu:** Paket envanteri seviyesinde RHEL destegi tamamlandi.
Sonraki adimlar (surum-ustu kapsam): scraper'in Red Hat/Rocky release
notes formatina genisletilmesi (fizibilite henuz degerlendirilmedi) ve
RAG/grounding katmanlarinin RHEL hedef surumleri icin icerik indekslemesi
-- bu turda yapilmadi.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v11.docx`.

---

## 2026-08-27 — RHEL-Ailesi RAG Hatti Uctan Uca Calisir Hale Geldi

**Ne yapildi:** Supervizorden hala cevap gelmedigi icin (5 gunden 4'u gecmisti),
kendi kararimizla projenin asil degeri olan RAG/rapor katmanina baslandi.
RHEL'in resmi docs.redhat.com sayfasi incelendi ama RHEL'e ozgu ozellikler
(RHEL Lightspeed gibi) icerdigi icin Rocky VM'imize karsi kullanilmadi --
bunun yerine Rocky'nin GitHub reposundaki saf markdown release notes'u
(HTML parse gerektirmeyen, dosya yolu ongorulebilir: release_notes/{surum}.md)
kaynak olarak secildi.

**Onemli bulgu:** Rocky Linux, major surum gecisini (leapp ile) resmi olarak
desteklemiyor ("perform a fresh install" deniyor) -- RHEL'in aksine. Bu,
"gercek yukseltme testi" is parcasini kapsam disi birakmak icin saglam bir
gerekce oldu.

**Uygulama:** `src/scraper/rocky_scraper.py` yazildi -- GitHub'dan markdown
cekip Ubuntu'nun ayni JSON semasiyla (version, section, section_id, content,
source_url) uyumlu cikti uretiyor. Kod incelemesi sirasinda bir hata onceden
yakalandi: section_id'yi None birakmak, mevcut extra_urls disambiguation
mekanizmasinin (scrape_version() icinde) hic devreye girmemesine yol
aciyordu -- 10.0/10.1/10.2'de ayni basdikli bolumler (orn. "Kernel") chunk
kimligi cakismasi yaratirdi. section_id, basliktan turetilen bir slug'a
cevrilerek duzeltildi.

Mevcut mimariye tamamen eklemeli sekilde entegre edildi: `ubuntu_scraper.py`'nin
PARSERS sozlugune "rocky" eklendi; `config/versions.json`'a `rocky-10.2`
girisi (10.0'i ana kaynak, 10.1/10.2'yi extra_urls olarak birlestiren)
eklendi. Hicbir Ubuntu kodu ya da yapilandirmasi degismedi.

**Sonuc (uctan uca gercek test):**
- `scrape_version("rocky-10.2")` -> 75 bolum (10.0'dan 35, 10.1'den 27, 10.2'den 13)
- extra_urls disambiguation dogru calisti: 75/75 benzersiz section_id, hic cakisma yok
- `chunk_release_notes()` -> 81 chunk, dogru kimliklendirme
- `build_index()` -> vektor veritabanina basariyla eklendi (Ubuntu'nun 301
  kaydina ek olarak toplam 382)

**Retrieval dogrulamasi:** Ilk sorgu denemesi ("PostgreSQL version Rocky
Linux") yaniltici gorunmustu -- dogru chunk top-15'in disinda kalmisti.
Ama bu, sorgunun kendisinde "Rocky Linux" ifadesinin gereksiz tekrarindan
kaynaklanan yuzeysel bir cakismaydi (Ubuntu'daki "version 26.04" boilerplate
cakismasina benzer -- sistem kusuru degil, kotu sorgu secimi). Dogal bir
soruyla ("What PostgreSQL version does the new release include?") tekrar
test edildiginde, dogru chunk (benzerlik 0.7905 ile) 1. sirada cikti; ikinci
alakali chunk da 2. sirada.

**Neden yapildi:** RHEL-ailesi destegini yalniz tespit/envanter katmaninda
degil, projenin asil degeri olan kaynak gosteren rapor uretimi katmaninda
da gercek bir temele oturtmak.

**Kanit:** Terminal ciktilari (bu oturumun kendisi); vektor veritabani
kayit sayisi (301->382); retrieval benzerlik skorlari.

**Kod degisti mi:** Evet.
- `src/scraper/rocky_scraper.py`: yeni dosya.
- `src/scraper/ubuntu_scraper.py`: PARSERS sozlugune "rocky" eklendi.
- `config/versions.json`: rocky-10.2 girisi eklendi.

**Acik konu:** grounding/draft_report adimlarinin Rocky ile uctan uca
(`agent.analyze()`) test edilmesi; gercek bir Rocky paket envanterine karsi
tam bir rapor uretimi; scraper icin kalici testler yazilmasi -- bu turda
henuz yapilmadi.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v12.docx`.

---

## 2026-08-27 (Devam) — Uctan Uca Gercek Rapor Uretimi Kanitlandi

**Ne yapildi:** RAG hattinin (scraper->chunking->embedding->retrieval)
dogrulanmasinin ardindan, projenin asil urununu -- kaynak gosteren,
halusinasyonsuz etki raporunu -- RHEL ailesinde gercekten uretip
uretemeyecegimizi test ettik. `agent/graph.py` ve `agent/nodes.py` incelendi:
`node_refresh`'in hem `current_version` hem `target_version` icin
`config/versions.json`'da bir giris bekledigi bulundu.

`config/versions.json`'a gercek bir `rocky-10.0` girisi eklendi -- bu,
"10.0'dan 10.2'ye" anlamli, gercek bir Rocky ic-major yukseltme senaryosu
kurmayi sagladi.

**Sonuc:** `analyze(target_version="rocky-10.2", current_version="rocky-10.0",
host="nisa@192.168.64.5")` cagrisi calistirildi -- ve BASARILI oldu. Sistem,
hicbir RHEL-ozel kod degisikligi gerektirmeden, tam pipeline'i
(detect->refresh->retrieve_general->package_intersect->draft_report->grounding)
uctan uca calistirdi. Varsayilan model (qwen2.5:7b) kullanildi.

Uretilen rapor gercek ve kaynakliydi: ozet ("The upgrade from Rocky Linux
10.0 to 10.2 will involve several changes, including the deprecation of DNF
modularity and updates to chrony and the kernel.") ve besin uzerinde iddia,
her biri gercek chunk kimligine, gercek GitHub kaynak URL'sine, ve
support_score ile grounding dogrulamasina (0.654-0.94 arasi, hicbir RED/FLAG
yok) sahipti. Dogru paket tespitleri: chrony (4.8), kernel, postgresql (18),
mariadb (11.8), frr (10.4.1), DNF modularity kaldirma uyarisi.

**Neden yapildi:** RHEL-ailesi destegini yalniz alt-katmanlarda (tespit, RAG
retrieval) degil, kullanicinin gorecegi NIHAI URUNDE (kaynak gosteren rapor)
da dogrulamak.

**Kanit:** Terminal ciktisi (bu oturumun kendisi) -- tam JSON rapor,
chunk_ids, support_score, sources alanlariyla.

**Kod degisti mi:** Evet (kucuk).
- `config/versions.json`: `rocky-10.0` girisi eklendi.

**Sonuc:** RHEL-ailesi icin projenin ASIL urunu -- sadece tespit/envanter
degil, kaynak gosteren gercek bir "ne bozulacak?" raporu -- uctan uca,
gercek bir Rocky sistemine karsi, hicbir mimari degisiklik gerektirmeden
basariyla calisti. Bu, RHEL genislemesi calismasinin bugune kadarki en
guclu kaniti.

**Acik konu:** grounding katmaninin RED/FLAG uretme davranisinin Rocky'de
de (Ubuntu'daki gibi) dogru calistigi ayrica dogrulanmali (bu calistirmada
hicbiri tetiklenmedi); kalici bir test (`test_rocky_analyze_end_to_end`)
yazilmasi -- bu turda yapilmadi.

**Rapor guncellemesi:** `OS_Upgrade_Analyzer_26_04_Kapsamli_Rapor_v13.docx`.
