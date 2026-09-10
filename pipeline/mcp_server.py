"""Pipeline FastMCP Sunucusu (Port :8001).

PDF belgelerini normalize Excel tablolarına dönüştüren ETL motorunu
Copilot Studio, Microsoft Teams ve MCP istemcilerine sunar.
"""

from typing import Any

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pipeline.pipeline_service import PipelineService
from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings

settings = get_settings()

mcp = FastMCP("sartnameai-pipeline")
pipeline_service = PipelineService()
catalog_service = ExcelCatalogService()


@mcp.tool(name="pipeline_status", description="Pipeline gelen, işlenen ve katalogdaki dosyaların anlık durumunu döner.")
def get_pipeline_status() -> dict[str, Any]:
    """Pipeline durumunu raporlar."""
    return pipeline_service.get_status()


@mcp.tool(
    name="process_pending_pdfs",
    description="Gelen kutusundaki (1_incoming_pdfs) bekleyen tüm PDF'leri normalize Excel'e dönüştürür ve kataloğu günceller.",
)
def process_pending_pdfs() -> dict[str, Any]:
    """Bekleyen PDF'leri dönüştürür ve kataloğa aktarır."""
    result = pipeline_service.process_all_pending()
    if result.processed_count > 0:
        catalog_service.reload()
    return {
        "status": "success",
        "total_found": result.total_found,
        "processed_count": result.processed_count,
        "failed_count": result.failed_count,
        "processed_files": result.processed_files,
        "failed_files": result.failed_files,
        "output_excel_files": result.output_excel_files,
    }


@mcp.tool(name="reload_catalog", description="Katalog Excel dosyalarını zorla yeniden tarar ve indeksler.")
def reload_catalog() -> dict[str, Any]:
    """Kataloğu yeniler."""
    catalog_service.reload()
    models = catalog_service.get_available_models()
    return {
        "status": "reloaded",
        "total_models": len(models),
        "available_models": models,
    }


@mcp.custom_route(path="/", methods=["GET"])
async def root_health(request: Request) -> Response:
    """Sağlık kontrol endpoint'i."""
    return JSONResponse(
        {
            "status": "online",
            "service": "sartnameai-pipeline",
            "port": settings.PIPELINE_PORT,
            "version": "1.0.0",
        }
    )


class PathNormalizer(BaseHTTPMiddleware):
    """Copilot Studio ve Cloudflare isteklerini standartlaştırır."""

    async def dispatch(self, request: Request, call_next):
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
    app = PathNormalizer(raw_app)
    app = CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


if __name__ == "__main__":
    import uvicorn

    app = create_asgi_app()
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.PIPELINE_PORT,
        log_level="info",
    )
