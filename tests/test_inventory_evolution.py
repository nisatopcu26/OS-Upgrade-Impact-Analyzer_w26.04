"""Envanter evrimi — adversarial testler (Chroma'sız: sahte korpus enjekte).

Amaç: kaldırma tespitinin BİLİNÇLİ dar kalması — agresif çıkarım, gerçek
paketleri sessizce düşürürdü ("uydurma yok"un tersi de geçerli: YOKMUŞ gibi
davranmak da uydurmadır).
"""

from src.upgrade_path.inventory_evolution import (
    evolve_inventory, find_removed_packages,
)

LEGS = [("18.04", "20.04"), ("20.04", "22.04")]


def _corpus(*texts: str, version: str = "20.04") -> list[dict]:
    return [{"id": f"{version}_test_{i}", "text": t}
            for i, t in enumerate(texts)]


def test_explicit_removed_drops_package_with_evidence():
    corpus = _corpus("Python 2 support: python2 has been removed "
                     "from the archive. Use python3 instead.")
    removed = find_removed_packages({"python2", "python3"}, corpus)
    assert [r["package"] for r in removed] == ["python2"]
    ev = removed[0]
    assert ev["chunk_id"] == "20.04_test_0"
    assert "removed" in ev["quote"]        # birebir alıntı — kaynak kanıtı


def test_no_longer_available_drops_package():
    corpus = _corpus("The pptpd package is no longer available in this release.")
    removed = find_removed_packages({"pptpd"}, corpus)
    assert [r["package"] for r in removed] == ["pptpd"]


def test_deprecated_does_not_remove():
    # "deprecated" ≠ kaldırıldı (Python 2.7, 20.04'te universe'e taşındı ama
    # kurulabilir kaldı) — muhafazakâr sınırın kilit vakası
    corpus = _corpus("php is deprecated in this release and may be dropped.")
    assert find_removed_packages({"php"}, corpus) == []


def test_no_longer_supported_does_not_remove():
    # destek bitmesi ≠ paketin yokluğu
    corpus = _corpus("chrony is no longer supported by upstream.")
    assert find_removed_packages({"chrony"}, corpus) == []


def test_present_tense_removes_does_not_remove():
    # Gerçek veriden tuzak: "Pacemaker 2.0 removes deprecated syntax" —
    # kalkan şey paket değil SÖZDİZİMİ; geniş zaman bilinçli kapsam dışı
    corpus = _corpus("Pacemaker 2.0 removes support for the deprecated syntax.")
    assert find_removed_packages({"pacemaker"}, corpus) == []


def test_php_phpmyadmin_substring_trap():
    # motor kelime-sınırlı (grounding ile ortak): phpmyadmin kalkınca
    # php'ye dokunulmaz
    corpus = _corpus("phpmyadmin has been removed from the archive.")
    removed = find_removed_packages({"php", "phpmyadmin"}, corpus)
    assert [r["package"] for r in removed] == ["phpmyadmin"]


def test_keyword_and_package_must_share_sentence():
    # çapraz-cümle eşleşme yasak: foo başka cümlede, removed başka cümlede
    corpus = _corpus("The foobar package was updated to 2.0. "
                     "Legacy telnet tools have been removed.")
    assert find_removed_packages({"foobar"}, corpus) == []


def test_digit_suffix_tolerance_documented():
    # BELGELENEN miras davranış: motorun sağda-rakam toleransı
    # (apache↔apache2) evrimde de geçerli — "apache2 removed" envanterdeki
    # "apache"yi düşürür. Ubuntu paket adları ek-rakamlı olduğundan istenen
    # davranış; VM doğrulaması (Sprint 6) aksini gösterirse sıkılaştırılır.
    corpus = _corpus("apache2 has been removed from the default install.")
    removed = find_removed_packages({"apache"}, corpus)
    assert [r["package"] for r in removed] == ["apache"]


def test_dependency_drop_does_not_remove_package():
    # GERÇEK 20.04 cümlesi (ilk REPL koşusunda yakalanan yanlış pozitif):
    # kalkan şey nginx değil, bir BAĞIMLILIK — ve "can be removed" spekülatif
    corpus = _corpus(
        'Here are some scenarios you might encounter: Since nginx-core '
        'dropped the dependency on libnginx-mod-http-geoip, an "apt '
        'autoremove" might suggest that libnginx-mod-http-geoip can be removed.')
    assert find_removed_packages({"nginx"}, corpus) == []


def test_replaced_by_package_not_marked_removed():
    # GERÇEK 20.04 cümlesi (ikinci yanlış pozitif): python2 kaldırılan değil,
    # YERİNE GELEN paket ("being replaced by the python2 ... packages");
    # "might be removed" da spekülatif — legacy python bile düşürülmez
    corpus = _corpus(
        "Due to this transition the legacy python and python-minimal packages "
        "might be removed during an upgrade, being replaced by the python2 and "
        "python2-minimal packages as dependencies of the python-is-python2 "
        "package.")
    assert find_removed_packages({"python2", "python"}, corpus) == []


def test_removal_of_nominal_form_detected():
    # "the removal of <paket>" nominal biçimi de açık kaldırma sayılır
    corpus = _corpus("This release includes the removal of pptpd from main.")
    removed = find_removed_packages({"pptpd"}, corpus)
    assert [r["package"] for r in removed] == ["pptpd"]


def test_comma_breaks_adjacency_window():
    # virgül özne değişimini işaret eder — pencere kesilir:
    # kaldırılan telnet'tir, foobar değil
    corpus = _corpus("After installing foobar, the legacy telnet client "
                     "was removed.")
    assert find_removed_packages({"foobar"}, corpus) == []


def test_entering_inventory_snapshot_per_leg():
    # kaldırma SONRAKİ bacaktan itibaren etkili; bacağa GİREN envanter korunur
    def corpus_fn(version):
        if version == "20.04":
            return _corpus("python2 has been removed from the archive.")
        return []                                   # 22.04 bacağı sessiz

    evo = evolve_inventory(["python2", "nginx"], LEGS, corpus_fn=corpus_fn)
    assert evo["per_leg"][("18.04", "20.04")] == ["nginx", "python2"]
    assert evo["per_leg"][("20.04", "22.04")] == ["nginx"]   # python2 düştü
    leg1 = evo["evolution"][("18.04", "20.04")]
    assert [r["package"] for r in leg1["removed"]] == ["python2"]
    assert leg1["renamed"] == []                    # D5: rename v1'de yok


def test_every_removal_has_chunk_id_evidence():
    corpus = _corpus("samba has been removed.", "telnet is no longer available.")
    removed = find_removed_packages({"samba", "telnet"}, corpus)
    assert len(removed) == 2
    assert all(r["chunk_id"] and r["quote"] for r in removed)


def test_empty_corpus_no_change_no_crash():
    evo = evolve_inventory(["php", "nginx"], LEGS, corpus_fn=lambda v: [])
    assert evo["per_leg"][("20.04", "22.04")] == ["nginx", "php"]
    assert evo["evolution"][("18.04", "20.04")]["removed"] == []


def test_short_package_names_skipped():
    # 2 harfli adlar her metinde eşleşir → gürültü guard'ı (len>=3)
    corpus = _corpus("go has been removed from the archive.")
    assert find_removed_packages({"go"}, corpus) == []
