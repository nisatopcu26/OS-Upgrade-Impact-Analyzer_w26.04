"""M6 — FastAPI uygulaması.

Çalıştır:  .venv/bin/uvicorn src.api.main:app --port 8010
Docs:      http://localhost:8010/docs (otomatik Swagger arayüzü)
"""

from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(
    title="OS Upgrade Impact Analyzer",
    description="Ubuntu LTS upgrade etkilerini resmi kaynaklara dayanarak, "
                "makineye özel analiz eder. Kaynaksız iddia üretmez.",
    version="1.0",
)
app.include_router(router)
