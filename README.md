# nexus-collection-dl

A tool to download [Nexus Mods](https://www.nexusmods.com/) collections and individual mods from the command line. Works with any game - Baldur's Gate 3, Starfield, Cyberpunk 2077, you name it.

> **Note:** This is a trimmed-down version of the original [nexus-collection-dl](https://github.com/scottmccarrison/nexus-collection-dl) application, pared back to focus on downloading collections themselves. All mod management features (deployment, load order generation, state tracking, web UI) have been removed.

## Why?

Nexus Mods collections are a great way to grab a curated set of mods in one shot, but the official tools (Vortex, the NexusMods App) are Windows-only. `nexus-dl` fills that gap: point it at a collection URL, and it downloads every mod file.

**New to the command line?** Check out the [Beginner's Guide](GUIDE.md) for a full walkthrough.

## Requirements

- Python 3.10+
- Nexus Mods account (free or Premium - see [Free vs Premium](#free-vs-premium-accounts) below)

## Installation

### Docker

```bash
git clone https://github.com/scottmccarrison/nexus-collection-dl.git
cd nexus-collection-dl
docker compose build
```

```bash
# Download a collection
docker compose run --rm nexus-dl sync "https://next.nexusmods.com/starfield/collections/xyz789" /mods

# Or use docker directly
docker run --rm -e NEXUS_API_KEY -v ./mods:/mods nexus-dl sync "https://next.nexusmods.com/starfield/collections/xyz789" /mods
```

### Setup script

```bash
git clone https://github.com/scottmccarrison/nexus-collection-dl.git
cd nexus-collection-dl
./setup.sh
source venv/bin/activate
```

### Manual

```bash
git clone https://github.com/scottmccarrison/nexus-collection-dl.git
cd nexus-collection-dl
python -m venv venv
source venv/bin/activate
pip install -e .
```

## Setup

1. Grab your API key from [Nexus Mods API settings](https://www.nexusmods.com/users/myaccount?tab=api%20access).
2. Export it:

```bash
export NEXUS_API_KEY="your-api-key-here"
```

The tool checks GitHub for newer versions on every command and prints an upgrade notice if one is available.

## CLI Usage

### Download a collection

```bash
nexus-dl sync "https://next.nexusmods.com/starfield/collections/xyz789" ~/mods/starfield

nexus-dl sync "https://next.nexusmods.com/baldursgate3/collections/abc123" ~/mods/bg3

# Skip optional mods
nexus-dl sync --skip-optional "https://next.nexusmods.com/starfield/collections/xyz789" ~/mods/starfield
```

Re-running `sync` is resumable - already-downloaded mods are skipped, so you can safely abort and pick up where you left off.

### Download a single mod

```bash
# Downloads the main file automatically
nexus-dl download "https://www.nexusmods.com/starfield/mods/123" ~/mods/starfield

# Pick a specific file from the mod
nexus-dl download "https://www.nexusmods.com/starfield/mods/123" ~/mods/starfield --file-id 456
```

If the tool can't auto-select a file (no main file category), it lists all available files so you can re-run with `--file-id`.

### File naming

Files keep the filename the Nexus CDN serves them under (e.g. `Head VFX Universal Automatic Patcher (UAP) 1.0.0 22716 1.0.0 2026-06-27T17-32Z sHBNVcw0v.zip`). Optional mods get an `[OPTIONAL]` prefix.

Archives are kept intact - the tool downloads files and leaves them as `.zip`, `.7z`, `.rar`, etc.

## Free vs Premium accounts

Both free and Premium Nexus Mods accounts work with `nexus-dl`. The difference is how mod files get downloaded.

**Premium** accounts can download files directly through the API, so `sync` and `download` handle everything automatically.

**Free** accounts can't use the Nexus download API (this is a Nexus Mods restriction, not ours), but every other API endpoint works fine - collection metadata, mod info, file listings. The tool uses these free endpoints to build a list of download links for you:

```
Pending Downloads (manual)
Mod                  | Filename              | Size    | URL
Script Extender      | ScriptExtender-v2.zip | 12.3 MB | https://www.nexusmods.com/...
Better UI            | BetterUI-1.5.pak      | 4.1 MB  | https://www.nexusmods.com/...
...

Free account detected. Download the files above through your browser and save them to ~/mods/starfield/My Collection.
```

Click each URL, download through Nexus (free countdown timer), and save the files to the collection directory.

## How it works

- **sync** - Fetches the collection from the Nexus API and downloads each mod file (skipping any already downloaded). Free accounts get a table of browser download links instead.
- **download** - Downloads a single mod by URL (main file by default, or a specific file with `--file-id`).

## License

[MIT](LICENSE)
