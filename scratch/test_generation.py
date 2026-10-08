import asyncio

from rich.console import Console

from generator.spec_service import SpecificationPipelineService
from shared.models import SpecRequest


async def run_test():
    console = Console()
    console.print("[bold yellow]Test: Şartname Oluşturma (AIClauseEngine ile)[/bold yellow]")

    req = SpecRequest(
        model="FAS2820",
        flexibility="tekil",
        warranty_years=5,
        support_type="9x5",
    )

    service = SpecificationPipelineService()

    with console.status("[bold cyan]Şartname üretiliyor, AI'dan yanıt bekleniyor..."):
        result = await service.generate_specification(req)

    console.print(f"\n[green][BASARILI] Şartname Üretildi: {result.document_title}[/green]")
    console.print(f"Madde Sayısı: {result.total_clauses}")
    console.print(f"Word Dosyası: {result.file_path}")

    console.print("\n[bold magenta]-- Üretilen Yapay Zeka Şartname Maddeleri --[/bold magenta]")
    for idx, clause in enumerate(result.clauses, 1):
        console.print(f"\n[bold cyan]Madde {idx} ({clause.category}):[/bold cyan] {clause.title}")
        console.print(clause.text)

if __name__ == "__main__":
    asyncio.run(run_test())
