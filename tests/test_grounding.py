"""M5 — Grounding adversarial testleri.

Projenin ana kuralı: uydurma yok. Bu testler kuralı MEKANİK olarak sınar —
kasıtlı sahte/kaynaksız/alakasız iddialar enjekte edilip RED'lendiği doğrulanır.
"""

from src.agent.grounding import (
    _entity_in_text, _looks_like_version, _overprecise_version,
    missing_hard_entities, verify_claims,
)

CONTEXT = [
    {
        "id": "24.04_linux-kernel_0",
        "text": "Linux kernel: Ubuntu 24.04 LTS includes the new 6.8 Linux "
                "kernel that brings many new features.",
        "metadata": {"source_url": "https://example.com/24.04/",
                     "scraped_at": "2026-07-07T10:00:00"},
    },
    {
        "id": "24.04_pptpd-removed_0",
        "text": "pptpd removed: pptpd and bcrelay have been removed from the "
                "archive for this release.",
        "metadata": {"source_url": "https://example.com/24.04/",
                     "scraped_at": "2026-07-07T10:00:00"},
    },
]


# --- v2.1 / S2: eşleşme motoru (saf fonksiyon, model yüklemeden) ----------

def test_entity_word_boundary():
    # kelime sınırı: substring eşleşmesi artık YOK
    assert not _entity_in_text("php", "phpmyadmin is included")
    assert not _entity_in_text("ssl", "openssl was updated")      # solda harf engeli
    # sağda-rakam toleransı: Ubuntu paket adları ek-rakamlı (S1 verisiyle karar)
    assert _entity_in_text("php", "install php8.1 now")
    assert _entity_in_text("apache", "apache2 has been updated")
    # ayraçlı varlıklar
    assert _entity_in_text("mod_md", "the mod_md module supports acme")
    assert _entity_in_text("re-attach", "will re-attach in case of drops")


def test_version_matching_flexibility():
    assert _looks_like_version("v255.4") and _looks_like_version("10.x")
    assert not _looks_like_version("power8") and not _looks_like_version("php")
    # 'v' öneki normalize
    assert _entity_in_text("v255.4", "systemd 255.4 is included")
    assert _entity_in_text("255.4", "uses systemd v255.4 now")
    # ana-sürüm önek esnekliği (iddia daha az hassas → sorun değil)
    assert _entity_in_text("255", "systemd 255.4")
    assert _entity_in_text("3.8", "ships python3.8 by default")   # bitişik paket adı
    assert _entity_in_text("3.8", "python 3.8.")                  # cümle sonu noktası
    # aşırı hassasiyet / uydurma sürüm → eşleşmez
    assert not _entity_in_text("255.4", "systemd 255 is included")
    assert not _entity_in_text("6.9", "the new 6.8 linux kernel")
    assert not _entity_in_text("3.8", "version 3.80 released")


def test_version_dot_notation_matches():
    # 2026-07-09 tur bulgusu: Ubuntu release notes 'cloud-init v.24.1.3'
    # yazıyor (v'den sonra NOKTA) — sadık iddiadaki 'v24.1.3' haksız RED
    # yiyordu (motor 'v.' yazımını tanımıyordu, lookbehind da engelliyordu).
    assert _looks_like_version("v.24.1.3")
    assert _entity_in_text("v24.1.3", "cloud-init v.24.1.3: notable features")
    assert _entity_in_text("24.1.3", "cloud-init v.24.1.3: notable features")
    assert _entity_in_text("v.24.1.3", "cloud-init 24.1.3 was released")
    # uydurma sürüm hâlâ yakalanıyor (tolerans yazıma, rakamlara değil)
    assert not _entity_in_text("v24.9.9", "cloud-init v.24.1.3: notable features")
    # gerçek vaka birebir (dünkü 18.04→24.04 raporunun RED'lenen iddiası):
    src = ("cloud-init v.24.1.3: notable features: windows subsystem for "
           "linux(wsl) datasource support azure: improved handling and "
           "retires of dhcp during pre-provisioning stage (pps)")
    assert missing_hard_entities(
        "Cloud-init v24.1.3 supports WSL datasource", src) == []


def test_plural_singular_tolerance():
    # 2026-07-09 tur bulgusu: iddia 'stages' (çoğul), kaynak 'stage (PPS)'
    # (tekil) → haksız FLAG. Morfoloji farkı uydurma değildir.
    assert _entity_in_text("stages", "during pre-provisioning stage (pps)")
    assert _entity_in_text("stage", "in the later stages of an upgrade")
    assert _entity_in_text("patches", "a security patch was applied")
    # kelime sınırı korunur: çoğul toleransı substring'e kapı açmaz
    assert not _entity_in_text("php", "phpmyadmin is included")
    # kısa kısaltmalar tekilleştirilmez ('tls' → 'tl' üretilmez)
    assert not _entity_in_text("tls", "the tl command was used")


def test_ing_inflection_tolerance():
    # 2026-07-10 tur bulgusu: iddia 'bringing', kaynak 'brings' → haksız FLAG.
    # 'stages' çoğul düzeltmesinin morfolojik kardeşi: -ing çekimi de uydurma
    # değildir. İki yön de tolere edilir.
    assert _entity_in_text("bringing", "kernel that brings many new features")
    assert _entity_in_text("handling", "will handle dhcp requests")   # e-geri-ekleme
    assert _entity_in_text("dropping", "may drop support for i386")   # çift ünsüz
    assert _entity_in_text("handle", "improved handling of dhcp")     # ters yön
    assert _entity_in_text("drop", "dropping support for i386")       # ters yön + çift ünsüz
    # gövde ≥4 harf koruması: kısa gövdeler üretilmez
    assert not _entity_in_text("string", "the str command was used")
    assert not _entity_in_text("thing", "the thin client")
    # kelime sınırı korunur: -ing toleransı substring'e kapı açmaz
    assert not _entity_in_text("php", "phpmyadmin is included")


def test_ing_inflected_common_word_not_flagged():
    # Tur bulgusunun (2026-07-10) uçtan uca nöbetçisi: 'bringing', yaygın
    # 'bring'in -ing hâli → artık yumuşak aday bile değil; sadık iddia temiz
    # geçer (flags == []). Kural öncesi bu vaka fabricated_term RED'iydi.
    claims = [{"text": "The new 6.8 Linux kernel is bringing many new "
                       "features to Ubuntu 24.04.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"kernel", "linux"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_fabricated_ing_term_still_rejected():
    # -ing toleransı uydurmayı MASKELEMEZ: 'quantumizing' ne atıfta ne
    # korpusta ne yaygın İngilizce → RED kalır (maskeleme bekçisi)
    claims = [{"text": "Ubuntu 24.04 includes the new 6.8 Linux kernel "
                       "with quantumizing support.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"kernel", "linux"})
    assert not verified
    assert rejected[0]["reject_reason"] == "fabricated_term"
    assert rejected[0]["missing_entities"] == ["quantumizing"]


def test_graphical_common_word_not_flagged():
    # 2026-07-10 tur bulgusunun ikinci yarısı: 'graphical' (-al türetmesi,
    # -ing kuralı kapsamaz) — açık karar #3: COMMON_WORDS'e dar ekleme
    claims = [{"text": "Ubuntu 24.04 includes the new 6.8 Linux kernel "
                       "with graphical improvements.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"kernel", "linux"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_daemon_suffix_tolerance():
    # 2026-07-29 tur bulgusu: iddia 'PPTP' (kısaltma → sert varlık), kaynak
    # 'pptpd' → sağda-harf sınırı eşleşmeyi engelliyordu ve BAYRAK kaldırma
    # iddiası haksız RED yedi. Unix daemon konvansiyonu (protokol+d: sshd,
    # ntpd, pptpd) dar varyant olarak eklendi — yalnız tek 'd'.
    assert _entity_in_text("pptp", "pptpd and bcrelay have been removed")
    assert _entity_in_text("ssh", "the sshd service was restarted")
    assert _entity_in_text("ntpd", "the ntp time protocol is used")   # ters yön
    # koruma: sınır yalnız 'd' için gevşedi, genel ek toleransı YOK
    assert not _entity_in_text("php", "phpmyadmin is included")
    assert not _entity_in_text("pptp", "the pptpx tool is new")


def test_pptpd_removal_claim_verified():
    # Uçtan uca nöbetçi: bayrak bulgu (pptpd kaldırması) artık doğrulanıyor —
    # 2026-07-29 turunda RED yiyen gerçek iddia kalıbının birebir karşılığı.
    claims = [{"text": "The pptpd package has been removed, which may affect "
                       "users relying on PPTP for network connections.",
               "chunk_ids": ["24.04_pptpd-removed_0"], "category": "package",
               "affected_package": "pptpd"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"pptpd", "bcrelay"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_irregular_past_made_not_flagged():
    # 2026-07-29 E2E tur bulgusu: 'made' (düzensiz geçmiş, make↔made kök
    # değişimi morfoloji kuralının bilinçli sınırı dışında) COMMON_WORDS'te
    # yoktu → haksız term_not_in_cited_source FLAG'i. Dar ekleme ile çözüldü.
    claims = [{"text": "The upgrade made the new 6.8 Linux kernel available "
                       "with many new features.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"kernel", "linux"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_generic_noun_compiler_not_fabricated():
    # 2026-07-29 E2E tur bulgusu (yanlış-RED sınıfının canlı örneği): sadık
    # "GCC ... compiler" iddiası, 'compiler' ne ince korpusta ne listede
    # olduğu için fabricated_term RED'i yiyordu. Genel İngilizce paraphrase
    # kelimesi teknik varlık değildir → COMMON_WORDS'e dar ekleme.
    context = [{"id": "22.04_toolchain_0",
                "text": "Toolchain upgrades: GCC is updated to 11.2.0 with "
                        "binutils 2.38 in this release.",
                "metadata": {"source_url": "https://example.com/",
                             "scraped_at": "2026-07-28T10:00:00"}}]
    claims = [{"text": "GCC has been updated to version 11.2.0, which may "
                       "affect applications that depend on this compiler.",
               "chunk_ids": ["22.04_toolchain_0"], "category": "package"}]
    verified, rejected = verify_claims(claims, context,
                                       corpus_vocab={"toolchain", "binutils"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_common_compound_words_not_entities():
    # v2.1 kalibrasyon bulgusu: 'long-term' gibi yaygın-kelime bileşikleri
    # varlık DEĞİL (tire varyantı 'long term' haksız RED üretiyordu);
    # 'security-hardening' varlık KALIR (hardening yaygın değil — GCC
    # süsleme yakalaması korunur), mod_md gibi teknik adlar da kalır.
    from src.agent.grounding import _extract_entities
    ents = _extract_entities("Long-term support ensures security-hardening "
                             "features via mod_md.")
    assert "long-term" not in ents
    assert "security-hardening" in ents
    assert "mod_md" in ents


def test_overprecise_version_detection():
    # kaynak '6.8' iken iddia '6.8.4' → model hassasiyet EKLEMİŞ (S4'te FLAG)
    assert _overprecise_version("6.8.4", "the new 6.8 linux kernel")
    assert _overprecise_version("255.4", "systemd 255 is included")
    # uydurma sürüm (6.9) overprecise DEĞİL → RED yolu korunur
    assert not _overprecise_version("6.9", "the new 6.8 linux kernel")
    # iddia daha az hassas → zaten eşleşir, overprecise değil
    assert not _overprecise_version("6.8", "kernel 6.8.1 included")


def test_good_claim_verified():
    claims = [{"text": "Ubuntu 24.04 ships with the Linux 6.8 kernel.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert len(verified) == 1 and not rejected
    v = verified[0]
    # Sayısal pin = tripwire (açık karar #7): bge+önek ölçeğinde ölçülen 0.90,
    # eşik 0.60 — 0.7 pini model/eşik kaymasını yakalar (S2 kalibrasyonu).
    assert v["support_score"] > 0.7
    assert v["sources"][0]["url"].startswith("https://")
    assert v["sources"][0]["scraped_at"]          # tarih atıfı var
    assert v["flags"] == []                       # temiz iddia: sessiz FLAG yok


def test_claim_without_source_rejected():
    claims = [{"text": "Everything will be fine after the upgrade.",
               "chunk_ids": [], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert not verified
    assert rejected[0]["reject_reason"] == "no_source_cited"


def test_fabricated_chunk_id_rejected():
    # LLM'in uydurabileceği, hiç var olmayan bir atıf
    claims = [{"text": "Ubuntu 24.04 removes Python 2 entirely.",
               "chunk_ids": ["24.04_uydurma-bolum_9"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert not verified
    assert rejected[0]["reject_reason"] == "unknown_chunk_id"


def test_unsupported_claim_rejected():
    # Gerçek bir chunk'a atıf var ama iddia onunla alakasız → low_support
    claims = [{"text": "The moon is made of green cheese and tastes great.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert not verified
    assert rejected[0]["reject_reason"] == "low_support"
    # bge+önek ölçeğinde ölçülen 0.417 — 0.5 pini eşiğin (0.60) rahat altı
    # kalmasını garanti eder (S2 kalibrasyonu; saçma-sınıf maks 0.572 idi).
    assert rejected[0]["support_score"] < 0.5


def test_partial_hallucination_rejected():
    # KISMİ uydurma: gerçek chunk'a atıf, cümle genel olarak benzer,
    # ama içine uydurma bir sürüm/paket sıkıştırılmış → sözcüksel katman yakalar
    claims = [{"text": "Ubuntu 24.04 includes the Linux 6.9 kernel with "
                       "bcachefs2 filesystem support.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert not verified
    assert rejected[0]["reject_reason"] == "unverified_entity"
    assert "6.9" in rejected[0]["missing_entities"]
    assert "bcachefs2" in rejected[0]["missing_entities"]


def test_allowed_terms_not_flagged():
    # Mevcut/hedef sürüm iddiada geçebilir, chunk'ta geçmese bile RED sebebi değil
    claims = [{"text": "Upgrading from 22.04: the kernel is now Linux 6.8.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT, allowed_terms=("22.04", "24.04"))
    assert len(verified) == 1 and not rejected


# --- v2.1 / S3-S4: yumuşak varlık sınıfı + kademeli politika ---------------

def test_fabricated_soft_term_rejected():
    # 'tailscale sınıfı' uydurma: düz küçük-harf özel isim, ne atıfta ne
    # korpusta → RED (v2'nin kör noktası artık kapalı; LLM'e hiç gitmeden)
    claims = [{"text": "Ubuntu 24.04 includes the new 6.8 Linux kernel "
                       "with a local zephyrnet daemon.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    vocab = {"kernel", "linux", "daemon", "features"}   # zephyrnet YOK
    verified, rejected = verify_claims(claims, CONTEXT, corpus_vocab=vocab)
    assert not verified
    assert rejected[0]["reject_reason"] == "fabricated_term"
    assert rejected[0]["missing_entities"] == ["zephyrnet"]


def test_wrong_citation_term_flagged_not_rejected():
    # Terim korpusta VAR ama atıf yapılan chunk'ta yok → yanlış atıf olabilir;
    # iddia kalır, şüpheli detay FLAG'lenir (kademeli politika)
    claims = [{"text": "Ubuntu 24.04 includes the new 6.8 Linux kernel "
                       "with changes for pptpd users.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    vocab = {"kernel", "linux", "pptpd"}                # pptpd korpusta var
    verified, rejected = verify_claims(claims, CONTEXT, corpus_vocab=vocab)
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == [
        {"term": "pptpd", "reason": "term_not_in_cited_source"}]


def test_overprecise_version_flagged_not_rejected():
    # Kaynak '6.8' derken iddia '6.8.7' — uydurma denemez (yuvarlama olabilir)
    # ama detay kaynakta yok → FLAG; eski davranış katı RED'di
    claims = [{"text": "Ubuntu 24.04 includes the Linux 6.8.7 kernel "
                       "with many new features.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    verified, rejected = verify_claims(claims, CONTEXT,
                                       corpus_vocab={"kernel", "linux"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == [
        {"term": "6.8.7", "reason": "overprecise_version"}]


def test_pluralized_common_word_not_flagged():
    # Tur bulgusunun uçtan uca nöbetçisi: 'stages', yaygın 'stage'in çoğulu →
    # artık yumuşak aday bile değil; sadık iddia temiz geçer (flags == [])
    context = [{"id": "24.04_cloud-init_0",
                "text": "cloud-init: improved handling of dhcp during "
                        "pre-provisioning stage (pps).",
                "metadata": {"source_url": "https://example.com/",
                             "scraped_at": "2026-07-09T10:00:00"}}]
    claims = [{"text": "Cloud-init improves handling of DHCP during "
                       "pre-provisioning stages.",
               "chunk_ids": ["24.04_cloud-init_0"], "category": "package"}]
    verified, rejected = verify_claims(claims, context,
                                       corpus_vocab={"cloud-init", "dhcp"})
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == []


def test_fabricated_check_plural_tolerant():
    # Korpus sözlüğü 'cgroup' (tekil) içerirken iddianın 'cgroups' (çoğul)
    # demesi fabricated_term DEĞİL — ama atıfta olmadığı için FLAG kalır
    # (yanlış-atıf sinyali korunur, uydurma damgası vurulmaz)
    claims = [{"text": "Ubuntu 24.04 includes the new 6.8 Linux kernel "
                       "with updated cgroups.",
               "chunk_ids": ["24.04_linux-kernel_0"], "category": "general"}]
    vocab = {"kernel", "linux", "cgroup"}
    verified, rejected = verify_claims(claims, CONTEXT, corpus_vocab=vocab)
    assert len(verified) == 1 and not rejected
    assert verified[0]["flags"] == [
        {"term": "cgroups", "reason": "term_not_in_cited_source"}]


def test_php_not_supported_by_phpmyadmin_source():
    # v2'de substring yüzünden 'php', 'phpmyadmin' içinde 'bulunmuş' sayılırdı
    # (kaçan uydurma). v2.1 kelime sınırı bunu RED'ler.
    context = [{"id": "24.04_phpmyadmin_0",
                "text": "phpmyadmin has been updated to version 5.2 "
                        "in this release.",
                "metadata": {"source_url": "https://example.com/",
                             "scraped_at": "2026-07-08T10:00:00"}}]
    claims = [{"text": "PHP has been updated in this release.",
               "chunk_ids": ["24.04_phpmyadmin_0"], "category": "package"}]
    verified, rejected = verify_claims(claims, context)
    assert not verified
    assert rejected[0]["reject_reason"] == "unverified_entity"
    assert "php" in rejected[0]["missing_entities"]


def test_report_carries_model_field():
    # S4 (açık karar #4): rapor hangi LLM'le üretildiğini beyan eder —
    # A/B koşuları ve denetim izleri kendiliğinden etiketli olur.
    from config.settings import LLM_MODEL
    from src.agent.grounding import node_grounding

    state = {
        "current_version": "22.04", "target_version": "24.04",
        "general_chunks": CONTEXT, "package_hits": {},
        "draft_claims": [{"text": "Ubuntu 24.04 ships with the Linux 6.8 kernel.",
                          "chunk_ids": ["24.04_linux-kernel_0"],
                          "category": "general"}],
        "packages": [],
    }
    report = node_grounding(state)["report"]
    assert report["model"] == LLM_MODEL
    assert report["model"]                       # boş beyan yok


def test_mixed_batch_split_correctly():
    claims = [
        {"text": "pptpd has been removed in this release.",
         "chunk_ids": ["24.04_pptpd-removed_0"], "category": "package",
         "affected_package": "pptpd"},
        {"text": "Unicorns are now supported natively.",
         "chunk_ids": [], "category": "general"},
    ]
    verified, rejected = verify_claims(claims, CONTEXT)
    assert len(verified) == 1 and len(rejected) == 1
    assert verified[0]["affected_package"] == "pptpd"
