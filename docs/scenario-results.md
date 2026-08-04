# M8 — Gerçek Senaryo Test Sonuçları

*Koşum tarihi: 2026-07-07. Tümü canlı FastAPI (`POST /analyze`) üzerinden,
qwen2.5:7b (lokal Ollama) ile. — 2026-07-08 eklemeleri için aşağıya bak:
"Grounding v2.1 regresyonu" ve "Uzak senaryolar (SSH)".*

## Özet tablo

| Senaryo | Envanter | Taslak iddia | Doğrulanan | Reddedilen | Etkilenen paketler | Süre |
|---|---|---|---|---|---|---|
| 22.04 → 24.04 | **gerçek makine** (163 paket) | 6 | 6 | 0 | apache2, gcc, openssh, php | 64s |
| 20.04 → 22.04 | sahte sunucu (php, postgresql, mysql, docker, nginx...) | 6 | 6 | 0 | — (aday çıkmadı) | 56s |
| 18.04 → 20.04 | sahte legacy (python2, php, chrony, corosync, samba) | 8 | 8 | 0 | chrony, corosync, php, python, samba | 90s |

## Elle doğrulama (kabul kriteri: 5+ iddia / rapor)

Senaryo 1 ve 3'ten toplam **10 iddia**, atıf yaptıkları chunk metniyle yan yana
karşılaştırıldı — **10/10 kaynağına sadık**. Örnekler:

| İddia (kısaltılmış) | Kaynak chunk | Sadık mı? |
|---|---|---|
| "GCC updated to 14 ... security-hardening" | `24.04_toolchain-upgrades_0`: "GCC is updated to the 14, binutils 2.42, glibc 2.39..." | ✅ |
| "OpenSSH uses systemd socket activation by default" | `24.04_openssh_0`: aynı ifade | ✅ |
| "Python 3.8 default; /usr/bin/python → python2 devam" | `20.04_Python3_by_default_0` | ✅ |
| "Pacemaker 2.0 removes deprecated syntax, requires Corosync 2+" | `20.04_Pacemaker_0` | ✅ |
| "PHP paketi güncellenince apache2 otomatik restart" | `24.04_php_1` | ✅ |

## Gözlemler (sunum notları)

1. **Senaryo 2'de aday paket çıkmadı — bu bir başarı.** 22.04 release notes
   görece ince (50 chunk) ve o paketleri anmıyor. Sistem "bilgi yok" deyip
   BOŞ döndü; UYDURMADI. "Release notes her paketi kapsamaz" sınırının
   (architecture.md) canlı kanıtı.
2. **Reddedilen iddia 0 çıktı** — `temperature=0` + `format=json` + katı prompt,
   LLM'i kaynaklara sadık tutuyor. Red mekanizmasının çalıştığı ayrıca
   `tests/test_grounding.py`'deki 5 adversarial testle kanıtlı (sahte chunk_id
   → RED, kaynaksız → RED, alakasız atıf → low_support RED).
3. **Makineye-özel değer:** Senaryo 1 gerçek envanterden apache2/gcc/openssh/php
   yakaladı; Senaryo 3'te pacemaker iddiası (kullanıcıda kurulu değil)
   "etkilenen paketlerin" listesinden gevşek eşlemeyle doğru şekilde elendi,
   python↔python2 eşleşmesi korundu.
4. **Süreler** CPU'da 55-90s — lokal 7B model için makul; API timeout'u 600s.

---

# Grounding v2.1 Regresyonu (2026-07-08)

*Aynı üç M8 senaryosu, üç-katmanlı yeni grounding ile (`analyze()` doğrudan,
qwen2.5:7b). Raporlar: `docs/sample-reports/*-v21.json`.*

| Senaryo | Envanter | Taslak | Doğrulanan | RED | FLAG | Etkilenen | Süre |
|---|---|---|---|---|---|---|---|
| 22.04 → 24.04 | gerçek makine (163) | 6 | 5 | **1** | 0 | apache2, openssh, php | 59s |
| 20.04 → 22.04 | sahte sunucu | 7 | 7 | 0 | 0 | docker | 62s |
| 18.04 → 20.04 | sahte legacy | 8 | 8 | 0 | 0 | chrony, corosync, php, python, samba | 71s |

**Tek RED, olması gereken RED:** *"The GCC compiler ... includes significant
improvements and **security-hardening** features"* — kaynak chunk'ta olmayan
süsleme (`unverified_entity`, eksik=security-hardening). v2 anekdotundaki
yakalamanın yeni motorla aynen tekrarı; artık `rejected_claims` alanında tam
metniyle raporlanıyor.

## Kalibrasyon disiplini (v2.1'in yöntemi)

Yeni sözcüksel kurallar koda bağlanmadan önce 20 elle-doğrulanmış gerçek
iddiada ölçüldü (`tests/calibrate_lexical.py`), üç iterasyonda yanlış alarmlar
sıfırlandı:

1. Stopword eksikleri ("both", "removing", "promotion", "resumed"...) →
   `_common_words.py` ~2400 kelimeye genişletildi
2. **"long-term" tire-varyantı** haksız RED üretiyordu (kaynak "long term"
   yazıyor) → tüm parçaları yaygın-kelime olan bileşikler varlık sayılmaz;
   "security-hardening" varlık KALIR (hardening yaygın değil) — GCC yakalaması
   testle korundu
3. Ara koşumda 3 `fabricated_term` yanlış pozitifi ("lead", "initiated",
   "ensuring"...) yakalandı ve stopword'e eklendi — final koşum temiz

Sentetik doğrulama: "zephyrnet daemon" (korpusta yok) → RED `fabricated_term`;
korpusta olup yanlış chunk'a atfedilen terim → FLAG; "6.8.7" (kaynak "6.8") →
FLAG `overprecise_version`; "php" ↔ yalnız "phpmyadmin" içeren kaynak → RED
(substring açığı kapandı). Tamamı `tests/test_grounding.py`'de (15 test).

---

# Uzak Senaryolar — SSH/Agentless (2026-07-08)

*Canlı FastAPI üzerinden; `current_version` GÖNDERİLMEDİ — sürüm ve envanter
uzak VM'den SSH ile otomatik tespit edildi. Hedeflere hiçbir şey kurulmadı.
Raporlar: `docs/sample-reports/remote-*.json`.*

| Hedef VM | Senaryo | Envanter (SSH) | Aday | Taslak | Doğrulanan | RED | FLAG | Etkilenen | Süre |
|---|---|---|---|---|---|---|---|---|---|
| labuser@lab-vm-2204 | 22.04→24.04 | 29 | 8 | 8 | 8 | 0 | 0 | apache2, nginx, openssh-server, php, postgresql | 74s |
| labuser@lab-vm-2004 | 20.04→22.04 | 29 | 5 | 7 | 5 | 2 | 0 | gcc | 65s |
| labuser@lab-vm-1804 | 18.04→20.04 | **469** | **15 (sınır!)** | 7 | 7 | 0 | 1 | cloud-init, php, python3, python | 77s |

**Davranış kanıtları (dört farklı davranış):**

1. **Web profili tam isabet:** 22.04 VM'in gerçek envanterinden apache2/nginx/
   php/postgresql/openssh-server yakalandı — makineye-özel analizin uzak kanıtı.
2. **İki haklı RED (20.04→22.04):** LLM, cloud-init iddiasına kaynakta olmayan
   `...0ubuntu0~` sürüm eki uydurdu → `unverified_entity`; "hostname paketi
   güncellenecek" spekülasyonu → `fabricated_term`. İkisi de rapora girmedi,
   `rejected_claims`'te şeffaf.
3. **overprecise_version canlıda ilk kez:** 18.04 senaryosunda "Python 3.8.2"
   iddiası (kaynak yalnız "3.8" diyor) → iddia KALDI ama detay ⚠️ FLAG'lendi.
4. **Hedefsiz sürüm:** 24.04 VM'e hedef 24.04 → **HTTP 422** ("downgrade/aynı
   sürüm desteklenmez") — UI'da "zaten en güncel LTS" kartı.

**Kapalı sunucu senaryosu ("uydurma yok" ağ katmanında):**
`virsh shutdown ubuntu20.04` → `POST /analyze` → **HTTP 502**
*"Hedef sunucuya bağlanılamadı"* (LLM hiç çağrılmadı, ~3s); `GET /detect?host=`
→ sözleşme gereği `error` alanlı dürüst cevap. VM yeniden başlatıldı →
**aynı IP'de** (lab-vm-2004) geri geldi — Sprint 0'ın MAC→IP sabitleme
kabul kriteri de böylece güç-döngüsüyle kanıtlandı.

**Gözlemler / v2.2 adayları:**

- **469 paketlik stres:** sözcüksel ön-eleme sorunsuz; ama aday listesi
  `MAX_PACKAGE_CANDIDATES=15` sınırına DAYANDI ve kesme alfabetik (apparmor..
  python3). Skor-bazlı önceliklendirme v2.2 adayı.
- Korpus sözlüğü tokenizasyonu bileşik token'ların alt-parçalarını saymıyor
  (ör. korpusta yalnız "set-hostname" biçiminde geçen "hostname" sözlükte yok
  sayılır → FLAG yerine RED'e kayabilir). Gözlemlenen vakada RED zaten özünde
  haklıydı (spekülatif iddia); alt-token sözlüğü v2.2 inceliği.
- LLM ara sıra iki paketi tek `affected_package` alanına yazıyor
  ("php, python3") — kozmetik, gevşek eşleme yine de doğru filtreliyor.
- SSH ek maliyeti ihmal edilebilir (~1-2s / VM); süreler lokalle aynı bantta.

**Güvenlik kabulleri (API sınırı):** `host="-oProxyCommand=x"` → **422**
(hem query hem body; enjeksiyon subprocess'e ulaşmadan ölür —
`test_injection_never_reaches_subprocess` ile birim kanıtı da var).

**Test durumu:** 56/56 pytest (48 birim + 8 lab; lab testleri VM kapalıyken
otomatik SKIP → suite lab'sız da yeşil).

---

# Zincir Analizi (Aşama 1+2) — 2026-07-10

**Duman koşusu (gerçek LLM, 8011'de geçici API; envanter enjekte:
python2/php/pptpd/nginx/samba/chrony):**

## Aşama 1 kabulleri (2026-07-09 koşusu)

| Senaryo | Beklenen | Sonuç |
|---|---|---|
| `/analyze` 22.04→24.04 | `is_direct: true`, kapsam uyarısı YOK | ✅ (79.6s, 7 doğrulanan) |
| `/analyze` 18.04→24.04 | yol 4 sürüm + `warnings`'ta kapsam sınırı | ✅ (73.7s, 7 doğrulanan) |

## Tam zincir: `/analyze-chain` 18.04→24.04 (2026-07-10, 243.1s, error: None)

| Bacak | Giren envanter | Kalkan (kanıtlı) | Doğrulanan | Reddedilen | Süre |
|---|---|---|---|---|---|
| 18.04→20.04 | 6 | — | 6 | 3 | 117.9s |
| 20.04→22.04 | 6 | — | 6 | 0 | 53.1s |
| 22.04→24.04 | 6 | **pptpd** | 7 | 1 | 71.9s |

- **pptpd kanıtı:** `24.04_pptpd-removed_0` — "pptpd and bcrelay have been
  removed from the archive for this release." (birebir alıntı raporda).
- **Kısmi-hata dürüstlüğü canlıda kanıtlandı (2026-07-09 ilk koşu):** Ollama
  bacak 2'de gerçek CUDA hatasıyla çöktü → sistem tamamlanan bacak 1'i döndürdü
  (5 doğrulanan, 87s), hatayı `error` alanında işaretledi, uydurmadı. HTTP 200
  + `error` sözleşmesi TestClient testiyle de kilitli.

## Envanter evrimi kalibrasyonu (gerçek-veri bulgusu — tasarımı değiştirdi)

Planlanan "kaldırma kelimesi + paket aynı cümlede" kuralı ilk gerçek-korpus
koşusunda İKİ yanlış pozitif üretti:
1. nginx — "Since nginx-core dropped the dependency on libnginx-mod-http-geoip,
   an 'apt autoremove' might suggest that libnginx-mod-http-geoip can be
   removed." (kalkan şey bağımlılık, nginx değil)
2. python2 — "...legacy python and python-minimal packages might be removed...
   being replaced by the **python2** and python2-minimal packages..."
   (python2 kaldırılan değil, YERİNE GELEN paket)

Kural özne-bitişikliğine sıkılaştırıldı (paket + ≤50 karakter + katı pasif
kalıp; virgül pencereyi keser; spekülatif "might/can be removed" dışarıda).
İki gerçek cümle adversarial test olarak sabitlendi. VM doğrulaması (aşağısı)
bu kalibrasyonun gerçeğe karşı sınavı.

**Test durumu:** 101/101 pytest (60 → 101; +41: yol 7, evrim 16, zincir 7,
API 11 — projenin ilk TestClient suite'i).

## Zincir doğrulaması (VM) — 2026-07-10: model gerçek upgrade'e karşı

**Yöntem:** 18.04 VM'i klonlandı (`ubuntu1804-upgtest`; orijinale dokunulmadı),
klon gerçekten upgrade edildi (`do-release-upgrade` 18.04→20.04, nonint, ~13 dk),
`apt-mark showmanual` önce/sonra anlık görüntüleri modelin tahminiyle kıyaslandı
(`tests/vm_validation_compare.py`; ham dosyalar `docs/vm-validation/`).

| Ölçüm | Değer |
|---|---|
| Envanter önce → sonra | 469 → 430 |
| Gerçekte kaybolan | 41 paket |
| Model tahmini (kanıtlı kaldırma) | 0 |
| Yanlış alarm (FP) | **0** |
| precision | tanımsız (tahmin yok) · recall = 0/41 |

**Yorum (dürüst okuma):**
- Kaybolan 41 paketin TAMAMI eski kütüphane soname'leri / geçiş paketleri
  (libicu60, libssl1.0.0, python3.6*, ureadahead, nplan...). Mekanik kontrol:
  **41'inin HİÇBİRİ 20.04 release notes'ta herhangi bir bağlamda geçmiyor.**
  Yani kaynak-temelli bir modelin bu bacakta 0 tahmin üretmesi doğru davranış —
  kaynakta kanıt yoktu, model uydurmadı. recall=0 modelin hatası değil,
  "notların anlattığı" ile "upgrade'in fiilen yaptığı" arasındaki farkın
  ölçümü — raporlardaki model-sınırı disclaimer'ının varlık sebebi.
- **0 yanlış alarm** kritik yarı: gerçek-veri kalibrasyonuyla sıkılaştırılan
  kural (özne-bitişikliği) gerçek upgrade'de tek bir hayalet kaldırma bile
  üretmedi. Kanıt olduğunda çalıştığının kanıtı ise pptpd: 24.04 notlarında
  açıkça yazıyor ve model onu yakalıyor (yukarıdaki zincir tablosu).
- Ek sınır notu (belgeliydi, gözlendi): do-release-upgrade manuel/otomatik
  işaretlerini de değiştirir ve obsolete temizliği yapar — "kaybolan" her
  paket, notların kastettiği anlamda "kaldırılmış" değildir.

**Sunum cümlesi:** "Envanter evrimi modelini gerçek bir VM upgrade'ine karşı
doğruladım: model sıfır yanlış alarm verdi; kaçırdığı 41 paketin hiçbiri
release notes'ta anılmıyordu bile — yani model tam da tasarlandığı gibi,
kaynağının ötesinde tahmin yürütmeyi reddediyor."

## Zincir doğrulaması 2 (VM) — 2026-07-10: 20.04 → 22.04 → 24.04 (iki bacak, gerçek upgrade)

**Yöntem:** 20.04 VM'i (db profili) klonlandı; her bacakta model tahmini
upgrade'den ÖNCE dosyaya yazıldı (`predicted-*.txt`), sonra gerçek
`do-release-upgrade` koşuldu, `apt-mark showmanual` önce/sonra kıyaslandı.

| Bacak | Envanter | Model tahmini | Gerçekte kaybolan | FP | Sonuç |
|---|---|---|---|---|---|
| 20.04→22.04 | 29→28 | 0 | 2 (libfwupdplugin1, libxmlb1) | **0** | FN'ler soname kütüphaneleri — notlarda yok |
| 22.04→24.04 | 28→28 | 0 | 0 | **0** | birebir uyum |
| **Zincir toplamı** | 29→28 | 0 | 2 | **0** | 18.04 deneyiyle aynı desen |

İki VM deneyinin ortak sonucu: **model hiçbir gerçek upgrade'de yanlış alarm
üretmedi**; kaçırdığı her paket release notes'un hiç anmadığı soname/geçiş
paketleriydi (mekanik olarak doğrulandı) — yani model tam tasarlandığı gibi
kaynağının ötesinde tahmin yürütmüyor.

**Yolda çıkan gerçek-dünya engelleri (5 operasyonel ders — runbook değeri):**
1. `apt upgrade` "kept back" paketleri kurmaz → `do-release-upgrade` sessizce
   reddeder; **dist-upgrade şart** (update-manager-core bile kept-back'ti).
2. Zincirli upgrade'de bacaklar arası **reboot şart** ("Please reboot before
   upgrading").
3. SSH üzerinden upgrade'de **temiz locale şart** (`LC_ALL=C.UTF-8`) — Türkçe
   LANG iletilince DistUpgradeView `locale.Error` ile çöktü.
4. **postgresql-NN deny-list bloğu (en değerlisi):** araç, veri kaybını
   önlemek için versiyonlu postgres paketlerini otomatik kaldırmaz ve
   upgrade'i DURDURUR — elle kaldırma ister. Raporumuz 22.04→24.04 için
   postgresql'i zaten "etkilenen" işaretliyordu: **raporun uyardığı paket,
   gerçek upgrade'i fiilen durduran paket çıktı** (sunum anekdotu).
5. Nonint upgrade son adımda (`confirmRestart()`) asılı kalabiliyor —
   paket işi bitmişken dıştan reboot güvenli (dpkg sonrası temiz doğrulandı).

Ham dosyalar: `docs/vm-validation/` (tahminler upgrade-öncesi zaman damgalı;
mid ve mid2 baseline'ları birebir aynı çıktı — postgres-12 manuel listede
değildi, kıyas elle müdahaleden etkilenmedi).

---

# S5 Kabul Matrisi — Taşıma Protokolü (2026-07-29)

*update_plan_3 S5: 6 senaryo × 2 konfigürasyon, LLM sabit (qwen2.5:7b).
Her iki kolon da AYNI kodda (S3 -ing toleransı dahil) CANLI koşuldu — tek
değişken embedding+eşik. Tarihsel bloklar yalnız akıl-sağlığı bandı.
Görsel: `s5-matrix/figs/fig_s5_matris.png` · ham veri: `s5-matrix/matrix_*.json`*

## Yan yana tablo

| Senaryo | Konfig | Taslak | Doğrulanan | RED | FLAG | Süre |
|---|---|---|---|---|---|---|
| M8 22.04→24.04 (gerçek) | eski | 8 | 4 | 4 | 4 | 93.1s |
| M8 22.04→24.04 (gerçek) | **yeni** | 8 | **8** | **0** | 1 | **70.2s** |
| M8 20.04→22.04 (sunucu) | eski | 6 | 6 | 0 | 0 | 50.5s |
| M8 20.04→22.04 (sunucu) | **yeni** | 6 | 6 | 0 | 0 | 52.9s |
| M8 18.04→20.04 (legacy) | eski | 8 | 8 | 0 | 0 | 76.3s |
| M8 18.04→20.04 (legacy) | **yeni** | 7 | 7 | 0 | 0 | 73.3s |
| SSH 22.04→24.04 | eski | 8 | 8 | 0 | 0 | 73.5s |
| SSH 22.04→24.04 | **yeni** | 8 | 8 | 0 | 1 | 82.4s |
| SSH 20.04→22.04 | eski | 7 | 3 | 4 | 0 | 67.8s |
| SSH 20.04→22.04 | **yeni** | 6 | **4** | **2** | 0 | **58.2s** |
| SSH 18.04→20.04 (469 pkt) | eski | 9 | 7 | 2 | 2 | 95.3s |
| SSH 18.04→20.04 (469 pkt) | **yeni** | 6 | **5** | **1** | 0 | **58.2s** |

## Karar: GEÇTİ — bge-small + 0.60 kalıcı

Rollback kriterleri (koşulardan ÖNCE update_plan_3.md'de yazılmıştı):

1. **Sadık iddia low_support RED'ine düştü mü?** HAYIR — 12 koşunun
   TAMAMINDA (iki konfig) sıfır `low_support` RED'i. Tüm RED'ler sözcüksel
   (unverified_entity / fabricated_term = taslak kalite varyansı; aralarında
   "tailscale daemon" klasiği de var — grounding tasarlandığı gibi yakaladı).
   Yeni konfigde doğrulanan iddiaların destek aralığı 0.735–0.924 — 0.60
   eşiğinin rahat üstü.
2. **Oran düşüşü (>0.05 çoğunlukta)?** HAYIR — yeni, 6/6 senaryoda eşit veya
   İYİ: gerçek-makine 0.50→1.00, SSH 20.04 0.43→0.67, SSH 18.04 0.78→0.83.
3. **Süre regresyonu >%20?** HAYIR — en kötü +%12 (SSH 22.04); üç senaryoda
   belirgin hızlanma (95→58s, 93→70s).

**Gözlem (göç lehine sürpriz):** bge retrieval'ı LLM'e daha isabetli bağlam
verdiği için taslakların kendisi temizleniyor — eski konfigin sözcüksel
RED'leri yeni konfigde yarıya indi (8→3). Eski kolonun tarihsel bantlardan
sapması (m8-gerçek 4 RED, tarihsel 0-1) embedding skorlamasıyla ilgisiz:
tümü sözcüksel, kaynak LLM taslak varyansı + retrieval bağlam farkı.
