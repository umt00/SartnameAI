"""FastMCP Sunucuları ve HTTP Arayüzü Testleri."""

import httpx
import pytest

from generator.mcp_server import create_asgi_app as generator_app
from matcher.mcp_server import create_asgi_app as matcher_app
from pipeline.mcp_server import create_asgi_app as pipeline_app


@pytest.mark.asyncio
async def test_pipeline_mcp_health():
    """Pipeline MCP sunucusunun sağlık endpoint'ini test eder."""
    app = pipeline_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8001") as client:
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert data["service"] == "sartnameai-pipeline"
        assert data["port"] == 8001


@pytest.mark.asyncio
async def test_generator_mcp_health_and_download():
    """Generator MCP sağlık ve doküman indirme endpoint'lerini test eder."""
    app = generator_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8002") as client:
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert data["service"] == "sartnameai-generator"
        assert data["port"] == 8002

        # Dosya indirme testi
        res_dl = await client.get("/download/Sartname_FAS2820_tekil.docx")
        assert res_dl.status_code == 200
        assert len(res_dl.content) > 1000


@pytest.mark.asyncio
async def test_matcher_mcp_health():
    """Matcher MCP sunucusunun sağlık endpoint'ini test eder."""
    app = matcher_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8003") as client:
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert data["service"] == "sartnameai-matcher"
        assert data["port"] == 8003
