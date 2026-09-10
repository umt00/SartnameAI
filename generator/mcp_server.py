"""Şartname Oluşturma FastMCP Sunucusu (Port :8002).

Parametrik teknik şartname üretimini, 1:1 doğrulama testlerini ve
Word (.docx) indirme servisini Copilot Studio, Teams ve MCP istemcilerine sunar.
"""

from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from generator.spec_service import get_specification_service
from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings
from shared.models import SpecRequest

settings = get_settings()

mcp = FastMCP("sartnameai-generator")
spec_service = get_specification_service()
catalog_service = ExcelCatalogService()

GLOBAL_HOST = "http://localhost:8002"


@mcp.tool(
    name="sartname_olustur",
    description="Verilen donanım modeli için 1:1 doğrulanmış kurumsal teknik şartname (.docx) üretir.",
)
async def generate_specification_tool(
    model: str,
    brand: str = "NetApp",
    flexibility: Literal["tekil", "jenerik"] = "tekil",
    disk_configuration: str | None = None,
    target_capacity: str | None = None,
    warranty_years: int = 5,
    support_type: str = "9x5",
) -> dict[str, Any]:
    """Teknik şartname oluşturur, 1:1 doğrulamasını yapar ve indirme linkini döner."""
    req = SpecRequest(
        model=model,
        brand=brand,
        flexibility=flexibility,
        disk_configuration=disk_configuration,
        target_capacity=target_capacity,
        warranty_years=warranty_years,
        support_type=support_type,
    )

    result = await spec_service.generate_specification(req)

    # İndirme bağlantısı oluştur
    file_name = Path(result.file_path).name if result.file_path else "sartname.docx"
    download_url = (
        result.download_url
        if (result.download_url and result.download_url.startswith("http"))
        else f"{GLOBAL_HOST}/download/{file_name}"
    )

    markdown_summary = (
        f"### 📋 {result.document_title} Hazırlandı!\n\n"
        f"- **Model:** `{result.model_name}` ({result.series})\n"
        f"- **Esneklik:** `{'Tekil (Markaya Özel)' if result.flexibility == 'tekil' else 'Jenerik (Rekabete Açık)'}`\n"
        f"- **Üretilen Madde Sayısı:** `{result.total_clauses}` madde\n"
        f"- **1:1 Doğrulama Güvencesi:** `%{result.audit_coverage_pct:.1f} Tam Uyum ({result.verification_status})`\n"
        f"- **Önbellek Durumu:** `{'Hızlı Önbellek' if result.is_cached else 'Sıfırdan Üretildi'}`\n\n"
        f"📥 **[Şartname Dokümanını İndir (.docx)]({download_url})**\n\n"
        f"> _{result.disclaimer}_"
    )

    return {
        "status": "success",
        "document_title": result.document_title,
        "model_name": result.model_name,
        "series": result.series,
        "flexibility": result.flexibility,
        "total_clauses": result.total_clauses,
        "verification_status": result.verification_status,
        "audit_coverage_pct": result.audit_coverage_pct,
        "file_path": result.file_path,
        "download_url": download_url,
        "markdown_response": markdown_summary,
    }


@mcp.tool(
    name="katalog_modellerini_listele",
    description="Katalogda kayıtlı tüm donanım modellerini ve teknik özetlerini listeler.",
)
def list_catalog_models(series: str | None = None) -> list[dict[str, Any]]:
    """Katalogdaki modelleri listeler."""
    summaries = catalog_service.list_models(series)
    return [s.model_dump() for s in summaries]


@mcp.tool(
    name="model_detayi_getir",
    description="Belirtilen modelin tüm teknik donanım parametrelerini getirir.",
)
def get_model_detail(model_name: str) -> dict[str, Any]:
    """Modelin detaylı özelliklerini getirir."""
    spec = catalog_service.get_spec(model_name)
    if not spec:
        return {"status": "not_found", "message": f"'{model_name}' katalogda bulunamadı."}
    return {"status": "success", "spec": spec.model_dump()}


@mcp.custom_route(path="/", methods=["GET"])
async def root_health(request: Request) -> Response:
    """Sağlık kontrol endpoint'i."""
    return JSONResponse(
        {
            "status": "online",
            "service": "sartnameai-generator",
            "port": settings.GENERATOR_PORT,
            "version": "1.0.0",
        }
    )


@mcp.custom_route(path="/download/{filename}", methods=["GET"])
async def download_file(request: Request) -> Response:
    """Üretilen şartname veya denetim dosyasını istemciye indirir."""
    filename = request.path_params.get("filename")
    if not filename:
        return JSONResponse({"error": "Dosya adı belirtilmedi"}, status_code=400)

    # Güvenlik kontrolü: Dizin dışına çıkmayı engelle
    clean_filename = Path(filename).name
    file_path = settings.OUTPUT_DIR / clean_filename

    if not file_path.exists():
        return JSONResponse({"error": f"Dosya bulunamadı: {clean_filename}"}, status_code=404)

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if file_path.suffix.lower() == ".docx"
        else "application/json"
    )

    return FileResponse(
        path=str(file_path),
        filename=clean_filename,
        media_type=media_type,
    )


class PathNormalizer(BaseHTTPMiddleware):
    """Copilot Studio ve Cloudflare isteklerini standartlaştırır."""

    async def dispatch(self, request: Request, call_next):
        global GLOBAL_HOST
        if "x-forwarded-host" in request.headers:
            GLOBAL_HOST = f"{request.headers.get('x-forwarded-proto', 'https')}://{request.headers['x-forwarded-host']}"
        elif "host" in request.headers:
            proto = request.headers.get("x-forwarded-proto", "http")
            if "trycloudflare.com" in request.headers["host"]:
                proto = "https"
            GLOBAL_HOST = f"{proto}://{request.headers['host']}"

        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        if request.method == "POST" and request.url.path in ("/", "/sse", "/api/mcp", "/messages"):
            request.scope["path"] = "/mcp"
            request.scope["raw_path"] = b"/mcp"

        return await call_next(request)


def create_asgi_app():
    """Tünel ve CORS uyumlu ASGI uygulamasını derler."""
    raw_app = mcp.http_app(transport="streamable-http")

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(PathNormalizer),
    ]

    for m in reversed(middleware):
        raw_app = m.cls(raw_app, **m.options)

    return raw_app


if __name__ == "__main__":
    import uvicorn

    app = create_asgi_app()
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.GENERATOR_PORT,
        log_level="info",
    )
