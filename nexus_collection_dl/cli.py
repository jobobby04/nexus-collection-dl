"""Command-line interface for nexus-collection-dl."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .api import NexusAPIError
from .collection import CollectionParseError, ModParseError
from .service import DownloadService, PendingDownload
from .version_check import check_for_update
from . import __version__

console = Console()


@click.group()
@click.option(
    "--api-key",
    envvar="NEXUS_API_KEY",
    help="Nexus Mods API key (or set NEXUS_API_KEY env var)",
)
@click.option(
    "--free",
    is_flag=True,
    hidden=True,
    help="Force free-user mode (for testing)",
)
@click.option(
    "--skip-update-check",
    is_flag=True,
    hidden=True,
    help="Skip automatic version check",
)
@click.pass_context
def main(ctx: click.Context, api_key: str | None, free: bool, skip_update_check: bool) -> None:
    """Download mod collections and mods from Nexus Mods."""
    update_msg = check_for_update()
    if update_msg:
        console.print(f"[yellow]{update_msg}[/yellow]")
    else:
        console.print(f"[dim]nexus-dl v{__version__}[/dim]")

    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["force_free"] = free
    ctx.obj["service"] = DownloadService(api_key, force_free=free)

    if not skip_update_check:
        from .updater import check_and_prompt_update
        check_and_prompt_update(console)


def _cli_progress(event: str, pct: float, msg: str) -> None:
    """Print progress messages to Rich console."""
    if event == "download":
        return  # Rich progress bar in downloader.py handles this
    console.print(f"[dim]{msg}[/dim]")


def _print_pending_downloads(pending: list[PendingDownload], mods_dir: Path) -> None:
    """Print a table of pending downloads with browser URLs."""
    table = Table(title="Pending Downloads (manual)")
    table.add_column("Mod", style="cyan")
    table.add_column("Filename", style="green")
    table.add_column("Size", style="dim")
    table.add_column("URL")

    for p in pending:
        size_str = _format_size(p.size_bytes) if p.size_bytes else "-"
        table.add_row(p.mod_name[:40], p.filename, size_str, p.browser_url)

    console.print(table)
    console.print(
        f"\n[yellow]Free account detected.[/yellow] Download the files above through your browser "
        f"and save them to [cyan]{mods_dir}[/cyan]."
    )


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


@main.command()
@click.argument("collection_url")
@click.argument("mods_dir", type=click.Path(path_type=Path))
@click.option("--skip-optional", is_flag=True, help="Skip optional mods")
@click.pass_context
def sync(
    ctx: click.Context,
    collection_url: str,
    mods_dir: Path,
    skip_optional: bool,
) -> None:
    """
    Download a collection to the specified directory.

    COLLECTION_URL: URL of the Nexus Mods collection
    MODS_DIR: Directory to download mods to
    """
    svc = ctx.obj["service"]
    try:
        result = svc.sync(
            collection_url, mods_dir,
            skip_optional=skip_optional,
            on_progress=_cli_progress,
        )
    except (NexusAPIError, CollectionParseError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if result.collection_dir:
        console.print(f"[dim]Collection directory: {result.collection_dir}[/dim]")

    if result.errors:
        for err in result.errors:
            console.print(f"[red]Error:[/red] {err}")

    if result.pending_downloads:
        _print_pending_downloads(result.pending_downloads, result.collection_dir)
    else:
        skip_msg = f", {result.skipped} skipped" if result.skipped else ""
        console.print(
            f"\n[green]Downloaded {result.mods_downloaded} mods{skip_msg}![/green]"
        )


@main.command()
@click.argument("mod_url")
@click.argument("mods_dir", type=click.Path(path_type=Path))
@click.option("--file-id", type=int, default=None, help="Specific file ID to download")
@click.pass_context
def download(
    ctx: click.Context,
    mod_url: str,
    mods_dir: Path,
    file_id: int | None,
) -> None:
    """
    Download a single mod by URL.

    MOD_URL: Nexus Mods mod page URL (e.g. https://www.nexusmods.com/starfield/mods/123)
    MODS_DIR: Directory to download the mod to
    """
    svc = ctx.obj["service"]
    try:
        result = svc.download_mod_by_url(
            mod_url, mods_dir,
            file_id=file_id,
            on_progress=_cli_progress,
        )
    except (NexusAPIError, ModParseError) as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if not result.success:
        console.print(f"[red]Error:[/red] {result.error}")
        sys.exit(1)

    if result.pending_download:
        p = result.pending_download
        console.print(f"[yellow]Free account - download manually:[/yellow]")
        console.print(f"  [cyan]{p.mod_name}[/cyan]: {p.browser_url}")
        console.print(f"\nSave the file to [cyan]{mods_dir}[/cyan]")
    else:
        console.print(f"[green]Downloaded '{result.mod_name}' -> {result.path}[/green]")


if __name__ == "__main__":
    main()
