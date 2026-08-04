"""M6 — Pydantic şemaları (API sözleşmesi)."""

from pydantic import BaseModel, Field, field_validator

from src.remote.ssh_runner import validate_host


class DetectResponse(BaseModel):
    distro: str | None
    version: str | None
    codename: str | None
    source: str | None
    error: str | None = None


class PackagesResponse(BaseModel):
    count: int
    source: str | None
    collected_at: str
    sample: list[str] = Field(description="İlk 20 paket (önizleme)")
    error: str | None = None


class VersionsResponse(BaseModel):
    supported: list[str]


class AnalyzeRequest(BaseModel):
    target_version: str = Field(examples=["24.04"])
    current_version: str | None = Field(
        default=None, description="Boşsa sistemden otomatik tespit edilir")
    packages: list[str] | None = Field(
        default=None,
        description="Boşsa apt-mark envanteri kullanılır (test için enjekte edilebilir)")
    host: str | None = Field(
        default=None,
        description="Uzak hedef (kullanici@ip); boşsa lokal analiz",
        examples=["ubuntu@192.168.1.10"])

    @field_validator("host")
    @classmethod
    def _host_format(cls, v: str | None) -> str | None:
        # Güvenlik: SSH argüman enjeksiyonu ("-oProxyCommand=...") API
        # sınırında ölür — doğrulama kaynağı ssh_runner.validate_host (TEK yer)
        if v is not None and not validate_host(v):
            raise ValueError(
                "geçersiz host formatı (beklenen: kullanici@ip-veya-hostname)")
        return v


class UpgradePath(BaseModel):
    """Zincir Aşama 1: resmi LTS yolu (compute_path çıktısı — deterministik).

    path=None + error → sürüm zincir dışı (rapor yine üretilmiş olabilir;
    yol bilgisi 'hesaplanamadı' der, uydurmaz).
    """
    path: list[str] | None
    legs: list[tuple[str, str]] = Field(default_factory=list)
    is_direct: bool = False
    skipped_intermediates: list[str] = Field(default_factory=list)
    error: str | None = None


class Source(BaseModel):
    chunk_id: str
    url: str
    scraped_at: str


class Claim(BaseModel):
    text: str
    category: str
    affected_package: str | None = None
    chunk_ids: list[str]
    support_score: float
    sources: list[Source]
    # v2.1: iddia doğrulandı ama bir detayı atıf yapılan kaynakta bulunamadı
    # (ör. overprecise_version, term_not_in_cited_source). Varsayılanlı →
    # eski raporlar/istemciler kırılmaz.
    flags: list[dict] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    host: str | None = None      # v2: analiz edilen hedef (None → lokal)
    current_version: str
    target_version: str
    # S4: raporu üreten LLM (açık karar #4; varsayılanlı → eski kayıtlar uyumlu)
    model: str = ""
    summary: str
    claims: list[Claim]
    not_found_notes: list[str]
    # v2.1: reddedilen iddiaların tam detayı (şeffaflık/denetim; varsayılanlı)
    rejected_claims: list[dict] = Field(default_factory=list)
    package_candidates: list[str]
    affected_packages: list[str]
    freshness: dict
    warnings: list[str]
    stats: dict
    duration_s: float
    # Zincir Aşama 1: resmi yol + kapsam bilgisi (varsayılanlı → geriye uyumlu)
    upgrade_path: UpgradePath | None = None


# --- Zincir Aşama 2: bacak-bacak analiz (POST /analyze-chain) ---------------

class RemovalEvidence(BaseModel):
    """Envanter evriminde düşürülen paket — kanıtsız kaldırma YOK."""
    package: str
    chunk_id: str
    quote: str


class LegEvolution(BaseModel):
    removed: list[RemovalEvidence] = Field(default_factory=list)
    renamed: list = Field(default_factory=list)   # v1: hep boş (belgeli sınır)


class LegResult(BaseModel):
    from_version: str
    to_version: str
    inventory_size: int
    inventory: list[str]                # şeffaflık: bacağa GİREN envanter
    evolution: LegEvolution
    report: AnalyzeResponse             # bacak raporu = tek-analiz sözleşmesi


class ChainAnalyzeResponse(BaseModel):
    host: str | None = None
    current_version: str
    target_version: str
    upgrade_path: UpgradePath
    legs: list[LegResult]
    evolution_disclaimer: str
    warnings: list[str] = Field(default_factory=list)
    # Kısmi başarısızlık (D6): bacak k>1 patlarsa tamamlananlar döner,
    # hata burada dürüstçe görünür: {"leg": ["20.04","22.04"], "detail": ...}
    error: dict | None = None
    duration_s: float
