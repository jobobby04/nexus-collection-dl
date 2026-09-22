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


def build_mod_stem(mod_info: dict[str, Any]) -> str:
    """
    Build a fallback filename for a mod file.

    Format: {mod_name}-{mod_id}-{version}-{file_id}.zip
    Used only when the CDN does not report a filename.
    """
    mod_name = _sanitize_component(mod_info.get("mod_name") or "")
    mod_id = mod_info.get("mod_id")
    version = mod_info.get("version") or ""
    file_id = mod_info.get("file_id")

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
    return "-".join(parts) + ".zip"


def filename_from_content_disposition(headers: dict[str, str]) -> str:
    """Extract the filename from a Content-Disposition header."""
    cd = headers.get("Content-Disposition", "")
    # RFC 5987 encoded form first (filename*=UTF-8''name.zip), then plain
    match = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd, re.IGNORECASE)
    if match:
        return Path(match.group(1).strip()).name
    return ""


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
    ) -> tuple[Path, bool]:
        """
        Download a mod file to target_dir, keeping the filename the CDN
        serves it under (from the Content-Disposition header).

        Args:
            on_progress: Optional callback(bytes_downloaded, total_bytes) for
                         generic progress reporting.

        Returns (path to the file, True if it was downloaded now,
        False if it already existed).
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

        temp_path: Path | None = None
        try:
            # Streaming GET fetches headers only, so we can resolve the real
            # filename (Content-Disposition) before deciding where to write.
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()

            name = filename_from_content_disposition(response.headers)
            if not name:
                name = Path(mod_info.get("filename") or "").name
            if not name:
                name = build_mod_stem(mod_info)
            if mod_info.get("optional"):
                name = f"[OPTIONAL] {name}"
            final_path = target_dir / name

            # Already downloaded - skip
            if final_path.exists():
                response.close()
                return final_path, False

            temp_path = target_dir / f".downloading_{name}"

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
            return final_path, True

        except Exception as e:
            # Clean up temp file on error
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
            raise DownloadError(f"Failed to download {original_filename}: {e}")

    def download_mods(
        self,
        game_domain: str,
        mods: list[dict[str, Any]],
        target_dir: Path,
        on_complete: Callable[[dict[str, Any], Path, bool], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[tuple[dict[str, Any], Path, bool]]:
        """
        Download multiple mods with a unified progress display.

        Args:
            game_domain: Game domain (e.g., 'baldursgate3')
            mods: List of mod info dicts
            target_dir: Directory to download files to
            on_complete: Callback called after each successful download
            on_progress: Optional callback(bytes_downloaded, total_bytes) for
                         generic progress (passed through to download_mod).

        Returns list of (mod_info, path, downloaded_now) tuples.
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
                    downloaded_path, downloaded_now = self.download_mod(
                        game_domain=game_domain,
                        mod_info=mod,
                        target_dir=target_dir,
                        progress=progress,
                        task_id=task_id,
                        on_progress=on_progress,
                    )
                    progress.remove_task(task_id)
                    results.append((mod, downloaded_path, downloaded_now))

                    if on_complete:
                        on_complete(mod, downloaded_path, downloaded_now)

                except DownloadError as e:
                    progress.remove_task(task_id)
                    progress.console.print(f"[red]Error:[/red] {e}")

        return results
