# Mimari Kararlar (M9)

Bu doküman, projedeki mimari kararların gerekçelerini kısaca açıklar.

## Hedef: makineye özel uyumluluk raporu (2026-07-07 kararı)
Sistem yalnızca genel bir "sürüm farkı raporu" üretmez; kullanıcının makinesindeki
kurulu paketleri de hesaba katar ("SENİN kullandığın pptpd 24.04'te kaldırıldı" gibi).

- **Paket envanteri:** `apt-mark showmanual` ile kullanıcının bilinçli kurduğu
  paketler alınır (~50-300 adet; `dpkg -l`'in binlerce kütüphanesi değil).
  Deterministik modül, detector'a eklenecek.
- **Kesiştirme (M4):** iki aşamalı — önce ucuz sözcüksel eşleme (paket adı
  chunk'larda geçiyor mu), sonra yalnızca eşleşenler için RAG + LLM değerlendirmesi.
- **Dürüst sınır:** release notes her paketi kapsamaz. Kaynakta olmayan paket için
  sistem "bilgi bulunamadı" der — uydurma yok (grounding kuralıyla tutarlı).
- **Kapsam dışı (ileride):** packages.ubuntu.com'dan paket-bazlı sürüm farkı
  çekmek deterministik bir genişletme olabilir.

## Neden scraper bir "tool"?
Agent, scraper'ı bağımsız bir script değil kendi çağırabileceği bir tool olarak
kullanır. Böylece "veri bayat mı?" kararını agent kendisi verip gerekirse yeniden
veri çeker.

## Neden freshness/TTL katmanı?
Bayat veriyle yanlış rapor üretmeyi engellemek için. TTL aşıldığında ilgili sayfa
yeniden scrape edilip Chroma güncellenir.

## Neden grounding katmanı?
"Uydurmama" kuralını mimari olarak garanti altına almak için. Kaynağı olmayan
iddialar rapora girmez.

## Neden modül = milestone?
`src/` altındaki her klasör bir milestone'a karşılık gelir; her modül diğerlerinden
bağımsız test edilebilsin ve bir sorunun hangi katmanda olduğu hızlı ayırt edilsin
diye.

## Neden iki parser? (M2 kararı)
Ubuntu release notes iki farklı dünyada yaşıyor: 22.04+ yeni Sphinx sitesinde
(`documentation.ubuntu.com`, düzenli `<section id>` yapısı), 20.04 ve öncesi eski
MoinMoin wiki'de (kapatılmamış `<p>`'lerle iç içe geçmiş düzensiz HTML).
Sphinx için section-bazlı, wiki için belge-sıralı (document-order) parser yazıldı;
`versions.json`'daki `format` alanı doğru parser'ı seçer.

## Neden token-bazlı chunking? (M3 kararı)
Kelime sayısı token'ı sistematik olarak eksik tahmin eder: teknik metinde
`libgtk-3-0 postgresql-14 python3.10-venv` 3 kelime ama **23 token**. Kelime
bazlı bölme, MiniLM'in 256-token sınırında sessiz kırpmaya (bilgi kaybına) yol
açar. Çözüm: modelin KENDİ tokenizer'ıyla sayım + cümle sınırından paketleme +
taşan tek cümle için sert bölme. Doğrulama: 328 chunk'ın en uzunu 250 token.
Sayaç, chunking'e parametre olarak enjekte edilir — modül modelsiz test edilir.

## Neden MiniLM? (M3/R5 kararı — deneysel)
Genel benchmark'lar bge'yi önerir; kendi verimizde 10 soruluk altın setle
ölçtük: MiniLM recall@5 = 1.00 / MRR 0.88, bge = 0.90 / 0.70. Adil kıyas için
iki model AYNI chunk'ları indeksledi. Kanıt: `tests/embedding_comparison.py`.

## Grounding nasıl çalışır? (M5 + v2 sözcüksel katman + v2.1 kademeli politika)
LLM'e "sadece kaynak kullan" demek yetmez; her iddia mekanik doğrulanır:
1. `chunk_ids` boş → RED (kaynaksız iddia)
2. Atıf, LLM'e verilen bağlamda yok → RED (uydurulmuş atıf)
3. **Sert sözcüksel varlık kontrolü:** iddiadaki teknik varlıklar (sürüm
   numaraları, `mod_md`/`pcre2` gibi ayraçlı-rakamlı adlar, GCC/TLS gibi
   kısaltmalar) atıf yapılan chunk metninde KELİME SINIRLI aranır; biri yoksa
   → RED (`unverified_entity`). Bu, "genel olarak kaynağa benzeyen ama içine
   uydurma detay sıkıştırılmış" KISMİ halüsinasyonu yakalar — kosinüs tek
   başına yakalayamaz. Kanıt: GCC iddiasına eklenen "security-hardening
   features" süslemesi kosinüsten 0.543 ile geçmişti; sözcüksel katman
   yakalayıp RED'ledi (bkz. accuracy-audit).
4. **Yumuşak sözcüksel kontrol (v2.1):** düz küçük-harf terimler
   ("tailscale" sınıfı — v2'nin belgeli kör noktası) yaygın-İngilizce
   listesinden (`_common_words.py`, ~2400 kelime, gerçek iddialarla kalibre)
   ayıklanıp iki seviyede aranır: atıf chunk'ında var → OK; yoksa ama hedef
   sürümün TÜM korpusunda var → **FLAG** (`term_not_in_cited_source` —
   yanlış atıf olabilir, iddia kalır ama detay işaretlenir); korpusta da yok
   → **RED** (`fabricated_term` — hiçbir kaynağa dayanamaz, uydurma).
5. İddia ↔ chunk kosinüs benzerliği < 0.30 → RED (kaynak desteklemiyor)
Eşik körlemesine seçilmedi: R4 skor gözleminde alakalı sorgular ≥ 0.34,
alakasızlar ≤ 0.28 — 0.30 tam aradaki boşluk. RED'ler sessizce silinmez,
raporda "kaynak bulunamadı" notuna + `rejected_claims` detayına dönüşür.

**Eşleşme motoru (v2.1):** substring değil, lookaround'lu kelime sınırı —
"php" artık "phpmyadmin" içinde "bulunmuş" sayılmaz (kaçan-uydurma kapatıldı).
Sağda-rakam toleransı: "apache"↔"apache2", "php"↔"php8.1" meşru (Ubuntu paket
adları ek-rakamlı). Sürüm esnekliği: "v255.4"↔"255.4" ve "255"↔"255.4" eşleşir;
iddia kaynaktan DAHA hassassa ("6.8.4" vs "6.8") uydurma denemez ama detay da
doğrulanamaz → FLAG (`overprecise_version`). "long-term" gibi tüm parçaları
yaygın kelime olan bileşikler varlık sayılmaz (tire varyantı haksız RED
üretiyordu — kalibrasyonla bulundu).

**Morfoloji ve yazım toleransları (2026-07-09 tur bulguları):** Ubuntu'nun
"v.24.1.3" yazımı (v'den sonra nokta) tanınır — sadık cloud-init iddiası bu
yüzden haksız RED yiyordu. Tekil/çoğul farkı iki yönde tolere edilir
("stages"↔"stage"; sağda-rakam toleransının morfolojik kardeşi) — hem eşleşme
motorunda hem korpus sözlüğü üyeliğinde, ve yaygın-kelime listesi üyeliği de
çoğul-bilinçlidir ("stage" yaygınsa "stages" da yaygındır). Tolerans yazıma ve
çekime tanınır, rakamlara TANINMAZ: "6.9"≠"6.8" RED kalır.

**Neden kademeli politika (RED/FLAG)?** Kanıt gücü kademeli: rakamlı/ayraçlı
varlığın kaynakta olmaması güçlü sinyal (→ RED), düz kelime eşleşmesi gürültülü
sinyal (→ FLAG). FLAG'li iddia rapora girer ama UI'da ⚠️ ile işaretlenir —
"sessizce silme yok" ilkesinin simetriği: sessizce aklama da yok. Kalibrasyon
disiplini: tüm kurallar önce 20 elle-doğrulanmış gerçek iddiada 0 yanlış alarm
verecek şekilde ayarlandı (`tests/calibrate_lexical.py`), sonra sentetik
uydurma vakalarıyla yakalama gücü kanıtlandı (`tests/test_grounding.py`).

Mevcut/hedef sürüm numaraları muaf tutulur (iddiada meşru, chunk'ta
olmayabilir). Kalan bilinen sınır: çok-kelimeli uydurma İFADELER (her kelimesi
tek tek korpusta olan ama birlikte anlamsız kombinasyonlar) — kosinüs katmanına
emanet; bigram kontrolü v2.2 adayı.

## Uzaktan analiz (SSH) — agentless mimari (roadmap v2)
Araç, merkezi bir kontrol düğümünden ağdaki sunucuları analiz eder. Hedef
sunuculara HİÇBİR ŞEY kurulmaz: SSH ile yalnızca iki şey okunur —
`/etc/os-release` (sürüm) ve `apt-mark showmanual` (envanter). RAG, LLM,
grounding kontrol düğümünde kalır ve DEĞİŞMEDİ.

- **Tek kapı:** tüm SSH işleri `src/remote/ssh_runner.py::run_remote`'tan
  geçer; `host=None` ise aynı arayüz lokalde çalışır (çift-mod). Detector'da
  parse I/O'dan ayrıldı (`_parse_os_release`) — lokal `open()` yolu ve testleri
  aynen korunurken uzak `cat` çıktısı aynı parser'dan geçer.
- **Güvenlik — host doğrulama:** `host` API/UI'dan serbest metin gelir; OpenSSH
  `-` ile başlayan argümanı SEÇENEK sayar, yani `-oProxyCommand=...` biçiminde
  bir "host" kontrol düğümünde keyfî komut çalıştırırdı (argüman enjeksiyonu).
  `validate_host` kalıba uymayan her string'i subprocess'e ULAŞMADAN reddeder;
  aynı doğrulama pydantic validator'la API sınırında 422 üretir. Kanıt:
  `tests/test_ssh_runner.py::test_injection_never_reaches_subprocess`.
- **"Uydurma yok" ağa uzanır:** erişilemeyen hedefte `analyze()` LLM'i hiç
  çağırmadan `ConnectionError` fırlatır → API 502 (Ollama ön-kontrol deseninin
  simetriği; graph'a "aborted" node'u eklemek yerine ön-kontrol seçildi —
  koşullu edge tesisatı gerekmez, graph sade kalır).
- **İki katmanlı test:** mock'lu birim testler her zaman koşar; gerçek lab
  testleri `lab` marker'lı ve VM kapalıysa otomatik SKIP — suite lab'a
  bağımlı olmadan yeşil kalır (`pytest -m lab` = lab kanıtı).
- **Lab:** 4 KVM/libvirt VM (18.04/20.04/22.04/24.04), MAC→IP sabitlenmiş
  (`virsh net-update`), kayıtları `config/hosts.json`'da (UI dropdown ve lab
  testlerinin tek kaynağı). 18.04 VM'i 469 manuel paketli "gürültülü envanter"
  stres vakası (eski kurulumlarda taban sistem manual işaretlidir).

## Zincir analizi ve envanter evrimi (Aşama 1 + 2)
Ubuntu'nun resmi upgrade yolu sıralı LTS zinciridir; `do-release-upgrade`
atlama yapmaz. İki katman:

**Aşama 1 — dürüst yol bilgisi (deterministik, LLM'siz):** `src/upgrade_path/
path.py::compute_path` yolu `versions.json`'dan türetir (hardcode yok;
okunamazsa RuntimeError — sessiz bayat-liste fallback'i yeni bir LTS'i
gizlerdi). Çok-bacaklı hedefte `/analyze` yanıtına `upgrade_path` alanı ve
raporun `warnings`'ına kapsam sınırı eklenir; UI hedef seçilir seçilmez uyarı
kartı gösterir. "Uydurma yok"un kapsam yüzü: rapor neyi BİLMEDİĞİNİ de söyler.

**Aşama 2 — bacak-bacak analiz (`/analyze-chain`):** her bacak mevcut
`analyze()`'dan ayrı geçer (graph'a dokunulmadı); bacağın envanteri
`inventory_evolution` modeliyle gelir. Tasarım kararları:
- **Envanter evrimi kaynağa dayanır, tahmine değil:** yalnız release notes'ta
  paket adının HEMEN ardından (≤50 karakter; virgül pencereyi keser) katı
  pasif kalıp gelen paketler düşürülür ("has/have been removed", "was/were
  removed", "is/are no longer available", "removal of X"). Her düşürme
  chunk_id + birebir alıntı kanıtı taşır.
- **Neden bu kadar dar:** ilk gerçek-veri koşusu iki yanlış pozitif yakaladı —
  "Since nginx-core dropped the dependency... libnginx-mod-http-geoip can be
  removed" (kalkan bağımlılık, nginx değil) ve "legacy python... might be
  removed... being replaced by the **python2** packages" (python2 kaldırılan
  değil YERİNE GELEN). Aynı-cümle eş-geçişi yetmez; özne-bitişiklik şart.
  "deprecated"/"no longer supported"/geniş-zaman "removes"/spekülatif "might
  be removed" bilinçli dışarıda. Kalibrasyon: gerçek VM upgrade'i (Sprint 6).
- **Rename v1'de yok:** release notes yeniden adlandırmayı parse edilebilir
  vermez; çıkarım = uydurma riski. `renamed` hep boş, sınır belgeli.
- **Kısmi-hata dürüstlüğü:** ilk bacak patlarsa hata aynen yükselir (502/422/
  500); sonraki bir bacak patlarsa tamamlanan bacaklar döner + `error` alanı
  işaretlenir — bitmiş bacaklar bağımsız geçerli kaynaklı raporlardır.
- **Senkron v1:** 3 bacak ≈ 5-6 dk; UI timeout 1800s. Gerçek dağıtımda proxy
  arkasında job-queue gerekir — kapsam dışı, bilinen sınır.
- Eşleşme sınır semantiği grounding motoruyla AYNI (php≠phpmyadmin,
  apache↔apache2) — parite adversarial testle korunur.

## Neden lokal LLM (qwen2.5:7b / Ollama)?
Paket envanteri ve sistem bilgisi makineye ait hassas veri — dışarı çıkmaz.
`temperature=0` + `format=json` + katı prompt, iddiaların şemaya ve kaynaklara
sadık kalmasını sağlar; M8'de üç senaryoda 20/20 iddia doğrulamadan geçti.

## Bilinen sınırlar
- Release notes her paketi anlatmaz → bazı kurulu paketler için "bilgi yok"
  normaldir (Senaryo 2: sahte sunucu envanterinde aday çıkmadı — sistem boş
  döndü, uydurmadı; bu bir başarı sayılır).
- Zincir envanter evrimi bir MODELDİR: release notes'ta yazmayan paket
  değişiklikleri görünmez → kaldırma tespitinde recall düşüktür ve bu belgeli
  bir sınırdır, bug değil. Ayrıca `do-release-upgrade` manuel/otomatik
  işaretlerini de değiştirir — VM doğrulamasında her "kaybolan" paket gerçek
  kaldırma değildir (kıyas metriğine not düşülür).
- Cümle bölme kısaltmalarda mükemmel değildir (`e.g.`) — bilgi kaybı yok,
  sadece ara sıra kısa chunk oluşur.
- Çoğul toleransı yalnız `-s`/`-es` çekimlerini kapsar; kökü değiştiren
  çekimler ("libraries"↔"library") kapsam dışı — gerçek veride görülürse
  kalibrasyonla genişletilir (stem'leme bilinçli olarak eklenmedi: her
  gevşetme yakalama gücünü düşürür).
