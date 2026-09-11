"""SartnameAI Birleşik (Unified) FastMCP Sunucusu.

Tüm servisleri (Pipeline, Generator, Matcher) tek bir FastMCP sunucusunda toplayarak
Copilot Studio, Microsoft Teams ve Claude/Cursor gibi istemcilere tek bir URL üzerinden
tüm yetenekleri (Şartname Oluşturma, Karşılaştırma, ETL) sunar.
"""

from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

from generator.spec_service import get_specification_service
from matcher.advisor_engine import AdvisorEngine
from matcher.matcher_service import get_matcher_service
from pipeline.pipeline_service import PipelineService
from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings
from shared.models import MatchRequest, SpecRequest

settings = get_settings()

mcp = FastMCP("sartnameai")

# Servisler
pipeline_service = PipelineService()
catalog_service = ExcelCatalogService()
spec_service = get_specification_service()
matcher_service = get_matcher_service()

GLOBAL_HOST = "https://sartnameai-app.politedune-5a0729a6.polandcentral.azurecontainerapps.io"


# ==============================================================================
# 1. GENERATOR (ŞARTNAME OLUŞTURMA) ARAÇLARI
# ==============================================================================

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
        f"📥 **[Teknik Şartnameyi İndir (.docx)]({download_url})**"
    )

    return {
        "status": "success",
        "document_title": result.document_title,
        "model_name": result.model_name,
        "series": result.series,
        "total_clauses": result.total_clauses,
        "audit_coverage_pct": result.audit_coverage_pct,
        "verification_status": result.verification_status,
        "download_url": download_url,
        "is_cached": result.is_cached,
        "markdown_response": markdown_summary,
    }


@mcp.tool(
    name="ornek_sablonlari_listele",
    description="Sistemde bulunan Word (.docx) şartname şablonlarını listeler.",
)
def list_templates() -> list[str]:
    """Kullanılabilir şablon dosyalarını listeler."""
    return spec_service.list_templates()


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


# ==============================================================================
# 2. MATCHER (ŞARTNAME KARŞILAŞTIRMA & ANALİZ) ARAÇLARI
# ==============================================================================

@mcp.tool(
    name="sartname_karsilastir",
    description="Verilen teknik şartname metnini veya Word dosyasını katalogdaki tüm ürünlerle karşılaştırır, puanlar ve en uygun modelleri önerir.",
)
def compare_specification_tool(
    specification_text: str = "",
    specification_file: str | None = None,
    top_n: int = 5,
    include_absurd_analysis: bool = True,
) -> dict[str, Any]:
    """Şartnameyi karşılaştırır ve puanlanmış sonuçları döner."""
    req = MatchRequest(
        specification_text=specification_text,
        specification_file=specification_file,
        top_n=top_n,
        include_absurd_analysis=include_absurd_analysis,
    )

    results = matcher_service.match_specification(req)
    if not results:
        return {
            "status": "warning",
            "message": "Analiz edilecek şartname metni veya dosyası bulunamadı ya da boş.",
            "results": [],
        }

    best_match = results[0]
    md_lines = [
        f"### 🎯 Şartname Karşılaştırma Analizi (En Uygun: {best_match.model_name})",
        "",
        f"**En Yüksek Uyum:** `{best_match.model_name}` ({best_match.series}) — **%{best_match.overall_score:.1f} Puan** ({best_match.tier})",
        "",
        "#### 🏆 Önerilen Ürün Sıralaması:",
    ]

    for idx, r in enumerate(results, start=1):
        md_lines.append(
            f"{idx}. **{r.model_name}** ({r.series}): `%{r.overall_score:.1f}` — _{r.tier}_ "
            f"({r.matched_count}/{r.total_evaluated} kriter tam uyumlu)"
        )

    md_lines.append("\n#### 💡 Teknik Değerlendirme ve Tavsiyeler:")
    md_lines.append(best_match.recommendation)

    if best_match.absurd_items:
        md_lines.append("\n⚠️ **Dikkat Edilmesi Gereken Şartname Maddeleri:**")
        for item in best_match.absurd_items:
            md_lines.append(f"- {item}")

    return {
        "status": "success",
        "top_model": best_match.model_name,
        "best_score": best_match.overall_score,
        "results": [r.model_dump() for r in results],
        "markdown_response": "\n".join(md_lines),
    }


@mcp.tool(
    name="en_uygun_urunleri_getir",
    description="Belirtilen şartname kriterlerine en çok uyan ilk N ürünü özet liste olarak döner.",
)
def get_best_models(specification_text: str, top_n: int = 3) -> list[dict[str, Any]]:
    """En uygun modelleri sade liste olarak döner."""
    req = MatchRequest(specification_text=specification_text, top_n=top_n)
    results = matcher_service.match_specification(req)
    return [
        {
            "model_name": r.model_name,
            "series": r.series,
            "score": r.overall_score,
            "tier": r.tier,
            "matched_count": r.matched_count,
        }
        for r in results
    ]


@mcp.tool(
    name="absurt_maddeleri_tespit_et",
    description="Şartname metnindeki çelişkili, mantıksız veya sektör standartlarına aykırı maddeleri tespit eder.",
)
def check_absurd_clauses(specification_text: str) -> dict[str, Any]:
    """Absürt maddeleri listeler."""
    absurdities = AdvisorEngine.detect_tender_absurdities(specification_text)
    return {
        "has_absurdities": len(absurdities) > 0,
        "count": len(absurdities),
        "absurd_clauses": absurdities,
    }


# ==============================================================================
# 3. PIPELINE (ETL & KATALOG) ARAÇLARI
# ==============================================================================

@mcp.tool(
    name="pipeline_status",
    description="Pipeline gelen, işlenen ve katalogdaki dosyaların anlık durumunu döner.",
)
def get_pipeline_status() -> dict[str, Any]:
    """Pipeline durumunu raporlar."""
    return pipeline_service.get_status()


@mcp.tool(
    name="process_pending_pdfs",
    description="Gelen kutusundaki bekleyen tüm PDF'leri normalize Excel'e dönüştürür ve kataloğu günceller.",
)
def process_pending_pdfs() -> dict[str, Any]:
    """Bekleyen PDF'leri dönüştürür ve kataloğa aktarır."""
    result = pipeline_service.process_all_pending()
    if result.processed_count > 0:
        catalog_service.reload()
    return {
        "processed_count": result.processed_count,
        "failed_count": result.failed_count,
        "errors": result.errors,
    }


@mcp.tool(
    name="list_available_models",
    description="Katalogdaki tüm donanım modellerini marka ve seri bazında listeler.",
)
def list_available_models(brand: str | None = None) -> dict[str, Any]:
    """Kullanılabilir modelleri döner."""
    models = catalog_service.get_available_models(brand=brand)
    return {
        "count": len(models),
        "available_models": models,
    }


# ==============================================================================
# 4. CUSTOM ROUTES & MIDDLEWARE
# ==============================================================================

@mcp.custom_route(path="/", methods=["GET"])
async def root_health(request: Request) -> Response:
    """Sağlık kontrol endpoint'i."""
    return JSONResponse(
        {
            "status": "online",
            "service": "sartnameai-unified",
            "version": "2.0.0",
            "tools_count": 9,
            "message": "SartnameAI Unified FastMCP is running with all tools active.",
        }
    )


@mcp.custom_route(path="/download/{filename}", methods=["GET"])
async def download_file(request: Request) -> Response:
    """Üretilen şartname veya denetim dosyasını istemciye indirir."""
    filename = request.path_params.get("filename")
    if not filename:
        return JSONResponse({"error": "Dosya adı belirtilmedi"}, status_code=400)

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
    """Copilot Studio, Teams ve Cloudflare isteklerini standartlaştırır ve API Key güvenliğini sağlar."""

    async def dispatch(self, request: Request, call_next):
        global GLOBAL_HOST
        if "x-forwarded-host" in request.headers:
            GLOBAL_HOST = f"{request.headers.get('x-forwarded-proto', 'https')}://{request.headers['x-forwarded-host']}"
        elif "host" in request.headers:
            proto = request.headers.get("x-forwarded-proto", "https")
            GLOBAL_HOST = f"{proto}://{request.headers['host']}"

        # 1. CORS Preflight isteklerine her zaman izin ver
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS, DELETE",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        # 2. Sağlık kontrolü ve dosya indirme endpoint'lerine kimlik doğrulamasız izin ver
        if request.method == "GET" and (request.url.path == "/" or request.url.path.startswith("/download/")):
            return await call_next(request)

        # 3. API Key Doğrulaması (X-API-Key veya Authorization başlığı)
        if settings.API_KEY:
            api_key_header = (
                request.headers.get("x-api-key")
                or request.headers.get("api-key")
                or request.headers.get("authorization", "").replace("Bearer ", "")
                or request.query_params.get("api_key")
            )
            if not api_key_header or api_key_header.strip() != settings.API_KEY.strip():
                return JSONResponse(
                    {
                        "error": "Unauthorized",
                        "message": "Geçersiz veya eksik API Anahtarı. Lütfen X-API-Key başlığını sağlayın.",
                    },
                    status_code=401,
                )

        # 4. Yol standartlaştırma
        if request.method == "POST" and request.url.path in ("/", "/sse", "/api/mcp", "/messages"):
            request.scope["path"] = "/mcp"
            request.scope["raw_path"] = b"/mcp"

        return await call_next(request)


def create_asgi_app():
    """Tünel ve CORS uyumlu birleşik ASGI uygulamasını derler."""
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
        port=8001,
        log_level="info",
    )
