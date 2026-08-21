"""M2 — Scraper temel sınıfı.

Ortak scraping mantığı (HTTP çekme, BeautifulSoup parse, metadata ekleme).
Her çekilen veriye `source_url` ve `scraped_at` (timestamp) eklenir.
"""
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from pathlib import Path
import time



HEADERS = {
    "User-Agent": "Analyzer/0.1 (educational project; " + "contact: bahceci.mehmet@outlook.com)"
}

def fetch_page(url: str, timeout: int = 10, retries: int = 3, backoff: int = 2) -> str | None:
    """URL'den HTML çeker. Geçici hatalarda (timeout, bağlantı, 5xx) tekrar dener.

    - 4xx (404 gibi) kalıcı hatadır -> tekrar denemeden None döner
    - Ağ/5xx hataları geçici olabilir -> artan bekleme (backoff) ile tekrar dener
    """
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if 400 <= status < 500:
                print(f"[ERROR] HTTP {status} (kalıcı hata): {url}")
                return None    # 404 gibi -> tekrar denemenin anlamı yok
            print(f"[WARN] HTTP {status} (deneme {attempt}/{retries}): {url}")

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            print(f"[WARN] Ağ hatası ({type(e).__name__}) — deneme {attempt}/{retries}: {url}")

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Beklenmeyen istek hatası: {e}")
            return None

        # Son deneme değilse, artan süre bekle (2s, 4s, ...)
        if attempt < retries:
            wait = backoff ** attempt
            print(f"        {wait}s bekleyip tekrar denenecek...")
            time.sleep(wait)

    print(f"[ERROR] {retries} deneme de başarısız: {url}")
    return None





def save_raw_html(html: str, version: str, suffix: str = "") -> Path:
    raw_dir = Path("data/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{version}{suffix}.html"
    file_path = raw_dir / filename
    file_path.write_text(html, encoding="utf-8")
    return file_path


def _own_text(section) -> str:

    parts = []
    for child in section.children:
        name = getattr(child, "name", None)
        if name == "section":
            continue
        if name in ("h1", "h2", "h3", "h4"):
            continue
        if hasattr(child, "get_text"):
            text = child.get_text(separator="\n", strip=True)
            if text:
                parts.append(text)
    return "\n".join(parts)


def parse_release_notes(html: str, version:str, source_url:str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    sections = []
    for section in soup.find_all("section"):
        heading = section.find(["h1", "h2", "h3", "h4"])
        if heading is None:
            continue

        title = heading.get_text(strip=True)
        content = _own_text(section)

        if not content:
            continue

        sections.append({
            "version": version,
            "section": title,
            "section_id": section.get("id"),
            "content": content,
            "source_url": source_url
        })
    
    return sections


def parse_wiki_release_notes(html: str, version: str, source_url: str) -> list[dict]:
    """Eski MoinMoin wiki (ör. 20.04) için parser.

    Wiki HTML'i düzgün kapatılmamış <p>'lerle iç içe geçmiş; section yok.
    Bu yüzden belge sırasına göre gezip, her başlıktan sonraki YAPRAK metin
    düğümlerini bir sonraki başlığa kadar topluyoruz (iç içelikten etkilenmez).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    container = soup.find("div", id="content") or soup
    headings = ("h1", "h2", "h3", "h4")

    def _under_heading(node) -> bool:
        # Başlığın kendi metnini (başlık altındaki string'leri) içeriğe katma
        return any(p.name in headings for p in node.parents)

    sections = []
    current = None      # o an işlenen başlık elementi
    buf = []            # o başlığa ait biriken metin parçaları

    def _flush():
        if current is None:
            return
        content = " ".join(" ".join(buf).split())   # fazla boşlukları sadeleştir
        if content:
            sections.append({
                "version": version,
                "section": current.get_text(strip=True),
                "section_id": current.get("id"),
                "content": content,
                "source_url": source_url,
            })

    for elem in container.descendants:
        if isinstance(elem, Tag) and elem.name in headings and elem.get("id"):
            _flush()            # önceki bölümü kapat
            current = elem
            buf = []
        elif isinstance(elem, NavigableString):
            if current is not None and not _under_heading(elem):
                text = elem.strip()
                if text:
                    buf.append(text)
    _flush()                    # son bölümü kapat
    return sections
