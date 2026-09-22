# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-09-22

### Added

- `sync` command - download an entire Nexus Mods collection
- `download` command - download a single mod by URL
- Standardized file naming: `{mod name}-{mod id}-{version}-{file id}{extension}` (e.g. `Ring of Mind Shielding Edit-19607-1-0-1762818108.zip`), with an `[OPTIONAL]` prefix for optional mods
- Resumable downloads - re-running skips files that are already downloaded
- Per-collection subdirectories - each collection gets its own named subfolder in the mods directory
- Free and Premium account support - free accounts get a table of browser download links
- Docker support
- Automatic version check - prints an upgrade notice if a newer release is available on GitHub
