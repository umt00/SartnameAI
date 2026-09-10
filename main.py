"""SartnameAI — Merkezi Terminal Kontrol Paneli.

3 Modüllü Kurumsal Mimari:
1. Pipeline (ETL): PDF -> Excel Dönüştürücü & Katalog İndeksleyici
2. Generator: 1:1 Doğrulamalı Parametrik Şartname Üretici (.docx)
3. Matcher: Şartname Karşılaştırma, Çok Katmanlı Puanlama & Absürtlük Tespiti
"""

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table
from rich.text import Text

from generator.spec_service import SpecificationPipelineService
from matcher.matcher_service import MatcherService
from pipeline.pipeline_service import PipelineService
from shared.catalog_service import ExcelCatalogService
from shared.config import get_settings
from shared.models import MatchRequest, SpecRequest

console = Console()
settings = get_settings()


def show_banner():
    """Ana başlık ve sistem durumunu gösterir."""
    banner = Text()
    banner.append("SartnameAI", style="bold cyan")
    banner.append(" — Kurumsal Teknik Şartname & Karşılaştırma Asistanı\n", style="bold white")
    banner.append("⚡ FastMCP Modülleri: ", style="dim")
    banner.append(f"Pipeline(:{settings.PIPELINE_PORT}) | ", style="green")
    banner.append(f"Generator(:{settings.GENERATOR_PORT}) | ", style="yellow")
    banner.append(f"Matcher(:{settings.MATCHER_PORT})", style="magenta")

    console.print(Panel(banner, border_style="cyan", expand=False))


def menu_pipeline():
    """ETL Pipeline kontrol menüsü."""
    service = PipelineService()
    status = service.get_status()

    table = Table(title="📦 Pipeline Durumu", border_style="green")
    table.add_column("Kategori", style="bold")
    table.add_column("Adet", justify="right")
    table.add_column("Açıklama")

    table.add_row("Bekleyen PDF'ler", str(status["pending_count"]), "1_incoming_pdfs klasöründeki dosyalar")
    table.add_row("İşlenmiş PDF'ler", str(status["processed_count"]), "2_processed_pdfs arşivindeki dosyalar")
    table.add_row("Aktif Kataloglar", str(status["catalog_excel_count"]), "data/catalogs altındaki Excel dosyaları")

    console.print(table)

    if status["pending_count"] > 0:
        console.print(f"\n[bold yellow]Bekleyen {status['pending_count']} adet PDF bulundu![/bold yellow]")
        if Confirm.ask("Tüm bekleyen PDF'leri şimdi normalize Excel'e dönüştüreyim mi?"):
            with console.status("[bold green]PDF tabloları taranıyor ve dönüştürülüyor..."):
                res = service.process_all_pending()
            console.print(f"[green]✓ {res.processed_count} dosya başarıyla işlendi ve kataloğa aktarıldı.[/green]")
            if res.failed_count > 0:
                console.print(f"[red]✗ {res.failed_count} dosya işlenirken hata oluştu: {res.failed_files}[/red]")
    else:
        console.print("\n[dim]Bekleyen yeni PDF yok. PDF eklemek için: pipeline/1_incoming_pdfs/[/dim]")


def menu_generate_spec():
    """Şartname oluşturma arayüzü."""
    console.print("\n[bold yellow]📄 Yeni Şartname Oluşturma Sihirbazı[/bold yellow]")

    catalog = ExcelCatalogService()
    models = catalog.get_available_models()

    console.print(f"[dim]Katalogda {len(models)} adet donanım modeli kayıtlı.[/dim]")
    model_name = Prompt.ask("Şartnamesi hazırlanacak donanım modeli", default="FAS2820")

    spec = catalog.get_spec(model_name)
    if spec:
        console.print(f"[green]✓ Model bulundu:[/green] {spec.model_name} ({spec.series})")
    else:
        console.print("[yellow]! Model katalogda bulunamadı, genel şablon kullanılacak.[/yellow]")

    flex = Prompt.ask("Şartname Türü", choices=["tekil", "jenerik"], default="tekil")
    warranty = IntPrompt.ask("Garanti Süresi (Yıl)", default=5)
    support = Prompt.ask("Destek Seviyesi", choices=["9x5", "7x24"], default="9x5")

    req = SpecRequest(
        model=model_name,
        flexibility=flex,
        warranty_years=warranty,
        support_type=support,
    )

    service = SpecificationPipelineService()
    with console.status("[bold cyan]Şartname üretiliyor, 1:1 denetim testi yapılıyor..."):
        result = asyncio.run(service.generate_specification(req))

    res_table = Table(title="✅ Şartname Hazırlandı", border_style="yellow")
    res_table.add_column("Alan", style="bold")
    res_table.add_column("Bilgi")

    res_table.add_row("Doküman Başlığı", result.document_title)
    res_table.add_row("Model / Seri", f"{result.model_name} ({result.series})")
    res_table.add_row("Esneklik Türü", "Tekil (Markaya Özel)" if result.flexibility == "tekil" else "Jenerik (Rekabete Açık)")
    res_table.add_row("Madde Sayısı", f"{result.total_clauses} madde")
    res_table.add_row("1:1 Doğrulama Güvencesi", f"%{result.audit_coverage_pct:.1f} ({result.verification_status})")
    res_table.add_row("Word Dosyası (.docx)", str(result.file_path))
    res_table.add_row("Denetim Raporu (.audit.json)", str(Path(result.file_path).with_suffix(".audit.json")) if result.file_path else "-")

    console.print(res_table)
    console.print(f"\n[italic dim]{result.disclaimer}[/italic dim]")


def menu_match_spec():
    """Şartname karşılaştırma ve ürün eşleştirme arayüzü."""
    console.print("\n[bold magenta]🎯 Şartname Karşılaştırma ve Ürün Eşleştirme[/bold magenta]")
    console.print("[dim]Şartname metnini doğrudan yapıştırabilir veya .docx dosya yolu verebilirsiniz.[/dim]\n")

    choice = Prompt.ask("Giriş türü", choices=["metin", "docx"], default="metin")

    if choice == "docx":
        file_path = Prompt.ask("Şartname .docx dosya yolu")
        req = MatchRequest(specification_file=file_path, top_n=5)
    else:
        console.print("[cyan]Şartname metnini girin (bitirmek için boş satırda Enter'a basın):[/cyan]")
        lines = []
        while True:
            line = input()
            if not line:
                break
            lines.append(line)
        text = "\n".join(lines)
        if not text.strip():
            console.print("[red]Metin boş olamaz![/red]")
            return
        req = MatchRequest(specification_text=text, top_n=5)

    service = MatcherService()
    with console.status("[bold magenta]Tüm katalog taranıyor, çok katmanlı puanlama hesaplanıyor..."):
        results = service.match_specification(req)

    if not results:
        console.print("[yellow]Uygun eşleşme bulunamadı veya şartname metni boş.[/yellow]")
        return

    table = Table(title="🏆 En Uygun Ürün Sıralaması", border_style="magenta")
    table.add_column("Sıra", justify="center")
    table.add_column("Ürün Modeli", style="bold")
    table.add_column("Ürün Serisi")
    table.add_column("Uyum Puanı", justify="right")
    table.add_column("Seviye")
    table.add_column("Tam Eşleşen Kriter")

    for idx, r in enumerate(results, start=1):
        color = "green" if r.overall_score >= 90 else ("yellow" if r.overall_score >= 80 else "red")
        table.add_row(
            str(idx),
            r.model_name,
            r.series,
            f"[{color}]%{r.overall_score:.1f}[/{color}]",
            r.tier,
            f"{r.matched_count}/{r.total_evaluated}",
        )

    console.print(table)

    best = results[0]
    console.print(Panel(best.recommendation, title=f"💡 Uzman Değerlendirmesi ({best.model_name})", border_style="green"))


def menu_catalog_explorer():
    """Katalog modellerini ve detaylarını listeler."""
    catalog = ExcelCatalogService()
    summaries = catalog.list_models()

    table = Table(title=f"📚 Donanım Kataloğu ({len(summaries)} Model)", border_style="blue")
    table.add_column("Model Adı", style="bold")
    table.add_column("Seri")
    table.add_column("RAM", justify="right")
    table.add_column("Azami Disk", justify="right")
    table.add_column("Azami Kapasite", justify="right")

    for s in summaries[:20]:
        table.add_row(
            s.model_name,
            s.series,
            f"{s.ram_total_gb} GB" if s.ram_total_gb else "-",
            str(s.max_drives) if s.max_drives else "-",
            s.max_raw_capacity or "-",
        )

    console.print(table)
    if len(summaries) > 20:
        console.print(f"[dim]... ve {len(summaries) - 20} model daha.[/dim]")


def menu_run_tests():
    """Otomatik testleri çalıştırıp özetler."""
    console.print("\n[bold cyan]🧪 Test Paketi Çalıştırılıyor...[/bold cyan]")
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        check=False,
    )

    console.print(result.stdout)
    if result.returncode == 0:
        console.print("[bold green]✓ TÜM TESTLER BAŞARIYLA GEÇTİ![/bold green]")
    else:
        console.print("[bold red]✗ Bazı testler başarısız oldu.[/bold red]")


def menu_mcp_servers():
    """FastMCP sunucularının durumunu ve çalıştırma bilgilerini gösterir."""
    table = Table(title="🔌 FastMCP Sunucu Mimarisi", border_style="cyan")
    table.add_column("Modül", style="bold")
    table.add_column("Port")
    table.add_column("Amaç")
    table.add_column("Başlatma Komutu")

    table.add_row(
        "1. Pipeline MCP",
        str(settings.PIPELINE_PORT),
        "PDF ETL, Katalog Yenileme",
        "uv run python pipeline/mcp_server.py",
    )
    table.add_row(
        "2. Generator MCP",
        str(settings.GENERATOR_PORT),
        "1:1 Doğrulamalı Şartname (.docx)",
        "uv run python generator/mcp_server.py",
    )
    table.add_row(
        "3. Matcher MCP",
        str(settings.MATCHER_PORT),
        "Karşılaştırma & Absürtlük Tespiti",
        "uv run python matcher/mcp_server.py",
    )

    console.print(table)
    console.print("\n[dim]Copilot Studio veya Teams'e bağlarken port yönlendirmesi veya Cloudflare tüneli kullanabilirsiniz.[/dim]")


def main():
    """Ana döngü."""
    while True:
        console.clear()
        show_banner()

        console.print("\n[bold]Lütfen işlem seçin:[/bold]")
        console.print("  [cyan]1.[/cyan] 📄 Şartname Oluştur (.docx + 1:1 Doğrulama)")
        console.print("  [magenta]2.[/magenta] 🎯 Şartname Karşılaştır & En Uygun Ürünü Bul")
        console.print("  [green]3.[/green] 📦 ETL Pipeline (PDF -> Excel)")
        console.print("  [blue]4.[/blue] 📚 Donanım Kataloğu Gezgini")
        console.print("  [yellow]5.[/yellow] 🔌 FastMCP Sunucuları Bilgisi")
        console.print("  [white]6.[/white] 🧪 Testleri Çalıştır (Pytest)")
        console.print("  [red]0.[/red] Çıkış\n")

        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5", "6", "0"], default="1")

        if choice == "1":
            menu_generate_spec()
        elif choice == "2":
            menu_match_spec()
        elif choice == "3":
            menu_pipeline()
        elif choice == "4":
            menu_catalog_explorer()
        elif choice == "5":
            menu_mcp_servers()
        elif choice == "6":
            menu_run_tests()
        elif choice == "0":
            console.print("[cyan]Görüşmek üzere![/cyan]")
            break

        Prompt.ask("\n[dim]Ana menüye dönmek için Enter'a basın[/dim]")


if __name__ == "__main__":
    main()
