import os
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from pipeline import process_pdfs

console = Console()

DIR_INCOMING = "1_incoming_pdfs"
DIR_PROCESSED = "2_processed_pdfs"
DIR_OUTPUT = "3_normalized_excels"

def ensure_dirs():
    os.makedirs(DIR_INCOMING, exist_ok=True)
    os.makedirs(DIR_PROCESSED, exist_ok=True)
    os.makedirs(DIR_OUTPUT, exist_ok=True)

def count_files(directory, ext=None):
    if not os.path.exists(directory):
        return 0
    if ext:
        return len([f for f in os.listdir(directory) if f.lower().endswith(ext) and not f.startswith('.')])
    return len([f for f in os.listdir(directory) if not f.startswith('.')])

def show_status():
    ensure_dirs()
    table = Table(title="Sistem Dosya Durumu")
    
    table.add_column("Klasör", style="cyan", no_wrap=True)
    table.add_column("İçerik", justify="right", style="magenta")
    table.add_column("Açıklama", style="green")

    table.add_row("1_incoming_pdfs", f"{count_files(DIR_INCOMING, '.pdf')} PDF", "İşlenmeyi bekleyen yeni dosyalar")
    table.add_row("2_processed_pdfs", f"{count_files(DIR_PROCESSED, '.pdf')} PDF", "Daha önce işlenip arşive alınanlar")
    table.add_row("3_normalized_excels", f"{count_files(DIR_OUTPUT, '.xlsx')} Excel", "Oluşturulmuş çıktı (normalize) tabloları")

    console.print(table)
    console.print()

def run_pipeline():
    ensure_dirs()
    incoming_count = count_files(DIR_INCOMING, '.pdf')
    if incoming_count == 0:
        console.print("[yellow]Uyarı: 1_incoming_pdfs klasöründe işlenecek PDF bulunamadı.[/yellow]")
        console.print("[italic]Yeni PDF'leri bu klasöre sürükleyip bırakabilirsiniz.[/italic]\n")
        return
        
    console.print(f"[bold green]Toplam {incoming_count} adet PDF işleniyor...[/bold green]")
    processed = process_pdfs()
    console.print(f"[bold cyan]İşlem Tamamlandı. {processed} dosya başarıyla Excel'e çevrildi ve arşive taşındı.[/bold cyan]")

def main_menu():
    while True:
        console.print(Panel.fit("[bold blue]SartnameAI Kontrol Paneli[/bold blue]", border_style="blue"))
        console.print("[1] Sistem Durumunu Görüntüle")
        console.print("[2] Bekleyen PDF'leri İşle")
        console.print("[3] Çıkış")
        
        choice = Prompt.ask("\nSeçiminiz", choices=["1", "2", "3"])
        
        if choice == "1":
            console.print("\n")
            show_status()
        elif choice == "2":
            console.print("\n")
            run_pipeline()
            console.print("\n")
        elif choice == "3":
            console.print("[bold red]Çıkış yapılıyor...[/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold red]Çıkış yapılıyor...[/bold red]")
        sys.exit(0)
