"""Şartname Karşılaştırma FastMCP Sunucusu (Port :8003).

İhale şartnamelerini analiz ederek en uygun modelleri bulan,
puanlayan ve absürt talepleri filtreleyen FastMCP servisi.
"""

from typing import Any

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from matcher.advisor_engine import AdvisorEngine
from matcher.matcher_service import get_matcher_service
from shared.config import get_settings
from shared.models import MatchRequest

settings = get_settings()

mcp = FastMCP("sartnameai-matcher")
matcher_service = get_matcher_service()


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

    # Teams / Copilot Studio için Markdown formatında özet oluştur
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


@mcp.custom_route(path="/", methods=["GET"])
async def root_health(request: Request) -> Response:
    """Sağlık kontrol endpoint'i."""
    return JSONResponse(
        {
            "status": "online",
            "service": "sartnameai-matcher",
            "port": settings.MATCHER_PORT,
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
        port=settings.MATCHER_PORT,
        log_level="info",
    )
