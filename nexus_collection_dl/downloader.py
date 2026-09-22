"""Download manager with progress tracking."""

import re
from pathlib import Path
from typing import Any, Callable

import requests
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .api import NexusAPI, NexusAPIError


class DownloadError(Exception):
    """Raised when a download fails."""

    pass


def _sanitize_component(name: str) -> str:
    """Make a string safe to use inside a filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    return name.strip(". ")


def _sanitize_version(version: str) -> str:
    """Normalize a version for use in a filename (1.0 -> 1-0)."""
    return re.sub(r"[^A-Za-z0-9]+", "-", version).strip("-")


def build_mod_filename(mod_info: dict[str, Any], download_url: str | None = None) -> str:
    """
    Build the output filename for a mod file.

    Format: {mod_name}-{mod_id}-{version}-{file_id}{ext}
    Example: Ring of Mind Shielding Edit-19607-1-0-1762818108.zip

    Optional mods get an [OPTIONAL] prefix:
    Example: [OPTIONAL] Some Mod-123-1-0-456.zip

    The extension comes from the CDN download URL, falling back to the
    original Nexus filename, then to .zip when no extension can be
    determined.
    """
    mod_name = _sanitize_component(mod_info.get("mod_name") or "")
    if mod_info.get("optional") and mod_name:
        mod_name = f"[OPTIONAL] {mod_name}"
    mod_id = mod_info.get("mod_id")
    version = mod_info.get("version") or ""
    file_id = mod_info.get("file_id")

    ext = ""
    if download_url:
        ext = Path(download_url.split("?")[0]).suffix
    if not ext:
        ext = Path(mod_info.get("filename") or "").suffix
    if not ext:
        ext = ".zip"

    parts = [
        part
        for part in (
            mod_name,
            str(mod_id) if mod_id is not None else "",
            _sanitize_version(version) if version else "",
            str(file_id) if file_id is not None else "",
        )
        if part
    ]
    return "-".join(parts) + ext


class Downloader:
    """Handles mod file downloads with progress tracking."""

    def __init__(self, api: NexusAPI):
        self.api = api
        self.session = requests.Session()

    def download_mod(
        self,
        game_domain: str,
        mod_info: dict[str, Any],
        target_dir: Path,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Path:
        """
        Download a mod file to target_dir using the standard filename.

        Args:
            on_progress: Optional callback(bytes_downloaded, total_bytes) for
                         generic progress reporting.

        Returns path to the downloaded file.
        """
        mod_id = mod_info["mod_id"]
        file_id = mod_info["file_id"]
        original_filename = mod_info["filename"]

        # Get download URL from API
        try:
            download_url = self.api.get_download_url(game_domain, mod_id, file_id)
        except NexusAPIError as e:
            raise DownloadError(f"Failed to get download URL for {original_filename}: {e}")

        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = target_dir / build_mod_filename(mod_info, download_url)

        # Already downloaded - skip
        if final_path.exists():
            return final_path

        temp_path = target_dir / f".downloading_{final_path.name}"

        try:
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))

            if progress and task_id is not None:
                progress.update(task_id, total=total_size)

            bytes_downloaded = 0
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress and task_id is not None:
                            progress.update(task_id, advance=len(chunk))
                        if on_progress:
                            on_progress(bytes_downloaded, total_size)

            temp_path.rename(final_path)
            return final_path

        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise DownloadError(f"Failed to download {original_filename}: {e}")

    def download_mods(
        self,
        game_domain: str,
        mods: list[dict[str, Any]],
        target_dir: Path,
        on_complete: Callable[[dict[str, Any], Path], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[tuple[dict[str, Any], Path]]:
        """
        Download multiple mods with a unified progress display.

        Args:
            game_domain: Game domain (e.g., 'baldursgate3')
            mods: List of mod info dicts
            target_dir: Directory to download files to
            on_complete: Callback called after each successful download
            on_progress: Optional callback(bytes_downloaded, total_bytes) for
                         generic progress (passed through to download_mod).

        Returns list of (mod_info, downloaded_path) tuples.
        """
        results = []
        total_mods = len(mods)

        with Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=30),
            "[progress.percentage]{task.percentage:>3.0f}%",
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            for i, mod in enumerate(mods, 1):
                filename = mod["filename"]
                # Ensure size is an int (API may return string)
                size_bytes = mod.get("size_bytes") or 0
                if isinstance(size_bytes, str):
                    size_bytes = int(size_bytes) if size_bytes.isdigit() else 0

                progress.console.print(
                    f"[dim]({i}/{total_mods})[/dim] {filename}"
                )
                task_id = progress.add_task(
                    "download",
                    filename=filename[:40],
                    total=size_bytes,
                )

                try:
                    downloaded_path = self.download_mod(
                        game_domain=game_domain,
                        mod_info=mod,
                        target_dir=target_dir,
                        progress=progress,
                        task_id=task_id,
                        on_progress=on_progress,
                    )
                    progress.remove_task(task_id)
                    results.append((mod, downloaded_path))

                    if on_complete:
                        on_complete(mod, downloaded_path)

                except DownloadError as e:
                    progress.remove_task(task_id)
                    progress.console.print(f"[red]Error:[/red] {e}")

        return results
