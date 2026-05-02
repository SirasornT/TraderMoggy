import typer
from rich.console import Console

from moggy import __version__
from moggy.config import get_settings

app = typer.Typer(name="moggy", help="TraderMoggy — personal stock research assistant")
console = Console()


@app.command()
def version() -> None:
    """Print the current version."""
    console.print(f"TraderMoggy v{__version__}")


@app.command()
def config() -> None:
    """Show current configuration (secrets redacted)."""
    settings = get_settings()
    for key, value in settings.display().items():
        console.print(f"{key}: {value}")
