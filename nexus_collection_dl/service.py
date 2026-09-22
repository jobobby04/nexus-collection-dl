"""Service layer - download logic for nexus-collection-dl."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .api import NexusAPI, NexusAPIError
from .collection import (
    CollectionParseError,
    ModParseError,
    parse_collection_url,
    parse_mod_url,
)
from .downloader import Downloader, build_mod_filename

# progress callback: (event_type, percentage 0-1, message)
ProgressCallback = Callable[[str, float, str], None]


def _sanitize_dirname(name: str) -> str:
    """Turn a collection name into a safe directory name."""
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip(". ")
    return name or "collection"


@dataclass
class PendingDownload:
    """A mod file that must be downloaded manually (free account)."""

    mod_id: int
    mod_name: str
    file_id: int
    filename: str
    size_bytes: int
    browser_url: str


@dataclass
class SyncResult:
    mods_downloaded: int
    skipped: int
    errors: list[str]
    pending_downloads: list[PendingDownload] = field(default_factory=list)
    collection_dir: Path | None = None


@dataclass
class ModDownloadResult:
    mod_name: str
    mod_id: int
    file_id: int
    filename: str
    path: Path | None
    success: bool
    error: str = ""
    pending_download: PendingDownload | None = None


def _noop_progress(event: str, pct: float, msg: str) -> None:
    pass


class DownloadService:
    """Downloads Nexus Mods collections and individual mods."""

    def __init__(self, api_key: str | None = None, force_free: bool = False):
        self._api_key = api_key
        self._api: NexusAPI | None = None
        self._force_free = force_free

    def _check_premium(self, user_info: dict) -> bool:
        """Check if user has premium, respecting force_free override."""
        if self._force_free:
            return False
        return user_info.get("is_premium", False)

    @property
    def api(self) -> NexusAPI:
        if self._api is None:
            self._api = NexusAPI(self._api_key)
        return self._api

    def sync(
        self,
        collection_url: str,
        mods_dir: Path,
        skip_optional: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> SyncResult:
        """Download an entire collection."""
        progress = on_progress or _noop_progress
        errors: list[str] = []

        # Parse URL
        collection_info = parse_collection_url(collection_url)

        # Check premium status
        progress("init", 0.0, "Validating API key...")
        user_info = self.api.validate_key()
        is_premium = self._check_premium(user_info)

        # Fetch collection
        progress("fetch", 0.05, "Fetching collection data...")
        collection_data = self.api.get_collection_mods(
            collection_info.game_domain, collection_info.slug
        )

        # Resolve mods_dir to a per-collection subdirectory
        dir_name = _sanitize_dirname(collection_data["name"])
        mods_dir = mods_dir / dir_name
        mods_dir.mkdir(parents=True, exist_ok=True)

        mods = collection_data["mods"]
        dupes = collection_data.get("duplicates_removed", 0)
        if dupes:
            progress("fetch", 0.06, f"Deduplicated {dupes} duplicate mod entries")
        if skip_optional:
            mods = [m for m in mods if not m.get("optional", False)]

        if not mods:
            return SyncResult(0, 0, [], collection_dir=mods_dir)

        if not is_premium:
            # Free user: list browser download links for manual download
            progress("pending", 0.5, "Building pending download list...")
            game_domain = collection_data["game_domain"]
            pending_downloads = [
                PendingDownload(
                    mod_id=mod["mod_id"],
                    mod_name=mod["mod_name"],
                    file_id=mod["file_id"],
                    filename=mod.get("filename", ""),
                    size_bytes=int(mod.get("size_bytes", 0) or 0),
                    browser_url=(
                        f"https://www.nexusmods.com/{game_domain}/mods/"
                        f"{mod['mod_id']}?tab=files&file_id={mod['file_id']}"
                    ),
                )
                for mod in mods
            ]
            progress("done", 1.0, f"Listed {len(pending_downloads)} mods for manual download")
            return SyncResult(
                mods_downloaded=0,
                skipped=0,
                errors=errors,
                pending_downloads=pending_downloads,
                collection_dir=mods_dir,
            )

        # Premium user: download directly, skipping files that already exist
        skipped = 0
        to_download = []
        for mod in mods:
            expected = mods_dir / build_mod_filename(mod)
            if expected.exists():
                skipped += 1
            else:
                to_download.append(mod)

        if skipped:
            progress("download", 0.1, f"Skipping {skipped} already-downloaded mods")

        total_mods = len(to_download)
        downloader = Downloader(self.api)

        if not to_download:
            results = []
        else:
            def on_download_progress(bytes_dl: int, total_bytes: int) -> None:
                if total_bytes > 0:
                    pct = 0.1 + 0.9 * (bytes_dl / total_bytes)
                    progress("download", pct, f"Downloading... ({bytes_dl}/{total_bytes} bytes)")

            progress("download", 0.1, f"Downloading {total_mods} mods...")
            results = downloader.download_mods(
                game_domain=collection_data["game_domain"],
                mods=to_download,
                target_dir=mods_dir,
                on_progress=on_download_progress,
            )

        progress("done", 1.0, f"Downloaded {len(results)} mods")
        return SyncResult(
            mods_downloaded=len(results),
            skipped=skipped,
            errors=errors,
            collection_dir=mods_dir,
        )

    def download_mod_by_url(
        self,
        mod_url: str,
        mods_dir: Path,
        file_id: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> ModDownloadResult:
        """Download a single mod by Nexus URL."""
        progress = on_progress or _noop_progress

        parsed = parse_mod_url(mod_url)

        progress("init", 0.0, "Validating API key...")
        user_info = self.api.validate_key()
        is_premium = self._check_premium(user_info)

        progress("fetch", 0.1, "Fetching mod info...")
        nexus_mod = self.api.get_mod_info(parsed.game_domain, parsed.mod_id)
        mod_name = nexus_mod.get("name", f"Mod {parsed.mod_id}")

        files = self.api.get_mod_files(parsed.game_domain, parsed.mod_id)
        if not files:
            return ModDownloadResult(
                mod_name=mod_name,
                mod_id=parsed.mod_id,
                file_id=0,
                filename="",
                path=None,
                success=False,
                error="No files found for this mod",
            )

        selected = _select_mod_file(files, file_id)
        if selected is None:
            return ModDownloadResult(
                mod_name=mod_name,
                mod_id=parsed.mod_id,
                file_id=0,
                filename="",
                path=None,
                success=False,
                error=(
                    f"Could not select file. Use --file-id. "
                    f"Available: {[f['file_id'] for f in files]}"
                ),
            )

        selected_file_id = selected["file_id"]
        selected_name = selected.get("name", selected.get("file_name", ""))
        original_filename = selected.get("file_name", selected_name)

        download_info = {
            "mod_id": parsed.mod_id,
            "mod_name": mod_name,
            "file_id": selected_file_id,
            "filename": original_filename,
            "version": selected.get("version", ""),
            "size_bytes": int(selected.get("size_in_bytes") or selected.get("size", 0) or 0),
        }

        if not is_premium:
            # Free user: return the browser download link
            browser_url = (
                f"https://www.nexusmods.com/{parsed.game_domain}/mods/"
                f"{parsed.mod_id}?tab=files&file_id={selected_file_id}"
            )
            pending = PendingDownload(
                mod_id=parsed.mod_id,
                mod_name=mod_name,
                file_id=selected_file_id,
                filename=original_filename,
                size_bytes=download_info["size_bytes"],
                browser_url=browser_url,
            )
            progress("done", 1.0, "Free account - download manually")
            return ModDownloadResult(
                mod_name=mod_name,
                mod_id=parsed.mod_id,
                file_id=selected_file_id,
                filename=original_filename,
                path=None,
                success=True,
                pending_download=pending,
            )

        mods_dir.mkdir(parents=True, exist_ok=True)

        def on_download_progress(bytes_dl: int, total_bytes: int) -> None:
            if total_bytes > 0:
                pct = 0.1 + 0.9 * (bytes_dl / total_bytes)
                progress("download", pct, f"Downloading {mod_name}...")

        progress("download", 0.1, f"Downloading {mod_name}...")
        downloader = Downloader(self.api)
        results = downloader.download_mods(
            game_domain=parsed.game_domain,
            mods=[download_info],
            target_dir=mods_dir,
            on_progress=on_download_progress,
        )

        if not results:
            return ModDownloadResult(
                mod_name=mod_name,
                mod_id=parsed.mod_id,
                file_id=selected_file_id,
                filename=original_filename,
                path=None,
                success=False,
                error="Download failed",
            )

        _, path = results[0]
        progress("done", 1.0, f"Downloaded {path.name}")
        return ModDownloadResult(
            mod_name=mod_name,
            mod_id=parsed.mod_id,
            file_id=selected_file_id,
            filename=path.name,
            path=path,
            success=True,
        )


def _select_mod_file(
    files: list[dict], file_id_override: int | None = None
) -> dict | None:
    """Select a file from the mod's file list.

    Priority:
    1. file_id override (exact match)
    2. MAIN category, highest file_id (most recent)
    3. Any non-archived file, highest file_id
    4. None
    """
    if not files:
        return None

    if file_id_override is not None:
        for f in files:
            if f.get("file_id") == file_id_override:
                return f
        return None

    main_files = [f for f in files if f.get("category_id") == 1]
    if main_files:
        return max(main_files, key=lambda f: f.get("file_id", 0))

    non_archived = [f for f in files if f.get("category_id") != 6]
    if non_archived:
        return max(non_archived, key=lambda f: f.get("file_id", 0))

    return None
