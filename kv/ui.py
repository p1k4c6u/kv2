# ui.py

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

LOGO = """
██╗  ██╗██╗   ██╗   ███████╗███████╗
██║ ██╔╝██║   ██║   ██╔════╝██╔════╝
█████╔╝ ██║   ██║   █████╗  █████╗
██╔═██╗ ╚██╗ ██╔╝   ██╔══╝  ██╔══╝
██║  ██╗ ╚████╔╝ ██╗███████╗███████╗
╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝╚══════╝
"""

COLORS = {
    "primary": "cyan",
    "secondary": "magenta",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "muted": "dim white",
}


def show_banner():
    """Display the application banner."""
    logo_text = Text(LOGO, style="bold cyan")
    subtitle = Text("Real Estate Scraper for kv.ee", style="italic magenta")

    console.print()
    console.print(Panel(
        logo_text,
        subtitle=subtitle,
        border_style="cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 2),
    ))
    console.print()


def prompt_area() -> str:
    """Prompt user to select an area with styled input."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.ROUNDED,
        border_style="dim cyan",
    )
    table.add_column("Cities", style="green")
    table.add_column("Counties", style="yellow")

    table.add_row("tallinn", "harjumaa")
    table.add_row("tartu", "jogevamaa")

    console.print(Panel(
        table,
        title="[bold]Available Areas[/bold]",
        border_style="cyan",
        box=box.ROUNDED,
    ))
    console.print()

    area = Prompt.ask(
        "[bold cyan]Enter area[/bold cyan]",
        default="tallinn",
    )
    return area.strip().lower()


def show_search_start(area: str):
    """Display search start message."""
    console.print()
    console.print(f"[bold cyan]Searching listings in [magenta]{area}[/magenta]...[/bold cyan]")
    console.print()


def show_page_progress(page_no: int, new_count: int, total_count: int):
    """Display progress for each search page."""
    if new_count > 0:
        console.print(
            f"  [dim]page[/dim] [cyan]{page_no:>2}[/cyan]  "
            f"[green]+{new_count:>3}[/green] new  "
            f"[dim]│[/dim]  [bold]{total_count:>4}[/bold] [dim]total[/dim]"
        )
    else:
        console.print(
            f"  [dim]page[/dim] [cyan]{page_no:>2}[/cyan]  "
            f"[dim]+  0 new[/dim]  "
            f"[dim]│[/dim]  [bold]{total_count:>4}[/bold] [dim]total[/dim]"
        )


def show_search_complete(count: int):
    """Display search completion message."""
    console.print()
    console.print(Panel(
        f"[bold green]Found {count} listings[/bold green]",
        border_style="green",
        box=box.ROUNDED,
    ))
    console.print()


def show_captcha_warning():
    """Display captcha warning with styled prompt."""
    console.print()
    console.print(Panel(
        "[bold yellow]Security Check Detected[/bold yellow]\n\n"
        "Please solve the CAPTCHA in the browser window,\n"
        "then press [bold]Enter[/bold] to continue...",
        border_style="yellow",
        box=box.HEAVY,
    ))
    input()


def create_crawl_progress() -> Progress:
    """Create a progress bar for crawling listings."""
    return Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[status]}[/dim]"),
        console=console,
        transient=False,
    )


def show_listing_result(index: int, total: int, title: str, price: int | None, url: str):
    """Display result for a crawled listing."""
    price_str = f"[green]€{price:,}[/green]" if price else "[dim]no price[/dim]"
    title_short = (title[:50] + "...") if title and len(title) > 53 else (title or "[dim]untitled[/dim]")

    console.print(
        f"  [cyan]{index:>3}[/cyan][dim]/[/dim][cyan]{total}[/cyan]  "
        f"{price_str:>16}  "
        f"[white]{title_short}[/white]"
    )


def show_crawl_complete(count: int, saved: int):
    """Display crawling completion summary."""
    console.print()
    console.print(Panel(
        f"[bold green]Crawling Complete[/bold green]\n\n"
        f"  [cyan]Processed:[/cyan]  {count} listings\n"
        f"  [cyan]Saved:[/cyan]      {saved} to database",
        border_style="green",
        box=box.DOUBLE,
    ))
    console.print()


def show_error(message: str):
    """Display an error message."""
    console.print()
    console.print(Panel(
        f"[bold red]Error[/bold red]\n\n{message}",
        border_style="red",
        box=box.HEAVY,
    ))
    console.print()


def show_info(message: str):
    """Display an info message."""
    console.print(f"  [dim cyan]>[/dim cyan] {message}")


def show_success(message: str):
    """Display a success message."""
    console.print(f"  [green]✓[/green] {message}")


def show_warning(message: str):
    """Display a warning message."""
    console.print(f"  [yellow]![/yellow] {message}")
