# Beginner's Guide

A step-by-step walkthrough for downloading Nexus Mods collections on Linux. No prior command-line experience required - every command is copy-pasteable with an explanation of what it does.

## What this tool does

`nexus-dl` lets you download entire mod collections from [Nexus Mods](https://www.nexusmods.com/) on Linux. Collections are curated mod packs that other players put together - think of them as "mod playlists" where someone has already figured out which mods work well together.

Normally, downloading collections requires Vortex or the Nexus Mods app, which only run on Windows. This tool does the same thing from a Linux terminal.

It works with any game on Nexus Mods - Baldur's Gate 3, Starfield, Cyberpunk 2077, Skyrim, Stardew Valley, and everything else.

## What you need before starting

1. **A Nexus Mods account** - Both free and Premium accounts work. Premium lets the tool download files automatically. Free accounts work too - the tool gives you download links and you grab the files through your browser. More on this below.

2. **Python 3.10 or newer** - This comes pre-installed on most Linux distributions. We'll check in a moment.

3. **A Nexus Mods API key** - This is a secret code that lets the tool talk to Nexus Mods on your behalf. We'll get this together below.

4. **git** - Used to download the tool itself. Also pre-installed on most systems.

## Opening a terminal

A terminal is a text window where you type commands. Here's how to open one:

- **Ubuntu / Pop!_OS / Linux Mint**: Press `Ctrl + Alt + T`
- **Fedora / GNOME**: Press `Super` (the Windows key), type "Terminal", and click it
- **KDE (Kubuntu, Fedora KDE)**: Press `Ctrl + Alt + T`, or find "Konsole" in your app menu.
- **Steam Deck (Desktop Mode)**: Tap the Steam icon in the taskbar, go to System > Konsole. Or find "Konsole" in the app launcher.

You should see a window with a blinking cursor. That's where you'll type the commands from this guide.

## Checking Python

Copy and paste this into your terminal, then press Enter:

```bash
python3 --version
```

You should see something like `Python 3.12.3`. Any version 3.10 or higher works.

If you get "command not found":

```bash
# Ubuntu/Debian/Pop!_OS
sudo apt install python3 python3-venv python3-pip

# Fedora
sudo dnf install python3

# Steam Deck - Python is pre-installed, but if missing:
sudo pacman -S python
```

## Installing nexus-dl

These commands download the tool and set it up. Run them one at a time:

```bash
git clone https://github.com/scottmccarrison/nexus-collection-dl.git
```

This downloads the tool's code into a folder called `nexus-collection-dl`.

```bash
cd nexus-collection-dl
```

This moves you into that folder.

```bash
./setup.sh
```

This installs everything the tool needs. It creates an isolated environment (called a "virtual environment") so it won't interfere with anything else on your system. It takes a minute or two.

```bash
source venv/bin/activate
```

This activates the tool's environment. You'll notice your terminal prompt changes - it'll show `(venv)` at the beginning. **You need to run this command every time you open a new terminal** before using `nexus-dl`. (We'll cover how to make this automatic later.)

Verify it worked:

```bash
nexus-dl --help
```

You should see a list of commands like `sync` and `download`. The tool also checks for newer versions automatically - if an update is available, you'll see a notice when you run any command.

## Getting your API key

An API key is like a password that lets the tool talk to Nexus Mods on your behalf.

1. Go to [nexusmods.com](https://www.nexusmods.com/) and log in
2. Click your profile picture in the top right
3. Click **Site preferences**
4. Click the **API Keys** tab
5. Under "Personal API Key", type a name for the key (anything works - "nexus-dl" is fine)
6. Click **Request an API key**
7. Copy the long string of letters and numbers that appears

**Keep this key private.** Treat it like a password - don't share it or post it publicly.

## Setting your API key

The tool looks for your API key in an "environment variable" called `NEXUS_API_KEY`. An environment variable is just a named value that programs can read.

### Quick method (lasts until you close the terminal)

```bash
export NEXUS_API_KEY="paste-your-key-here"
```

Replace `paste-your-key-here` with the key you copied. Keep the quotes.

### Permanent method (recommended)

To avoid setting the key every time you open a terminal, add it to your shell's startup file:

```bash
echo 'export NEXUS_API_KEY="paste-your-key-here"' >> ~/.bashrc
```

Replace `paste-your-key-here` with your actual key. Then reload the file:

```bash
source ~/.bashrc
```

Now the key will be set automatically every time you open a terminal.

**Note:** If your terminal uses `zsh` instead of `bash` (you can check with `echo $SHELL`), use `~/.zshrc` instead of `~/.bashrc`.

## Your first download

### Finding a collection URL

1. Go to [nexusmods.com](https://www.nexusmods.com/)
2. Pick a game (e.g., Baldur's Gate 3)
3. Click the **Collections** tab on the game's page
4. Browse or search for a collection you like
5. Click on it to open the collection page
6. Copy the URL from your browser's address bar - it looks something like:
   `https://next.nexusmods.com/baldursgate3/collections/abc123`

### Downloading

Make sure you're in the `nexus-collection-dl` directory and have the virtual environment activated (you should see `(venv)` in your prompt). Then:

```bash
nexus-dl sync "https://next.nexusmods.com/baldursgate3/collections/abc123" ~/mods/bg3
```

Replace the URL with the one you copied, and `bg3` with whatever game abbreviation you like (it's just a folder name).

What this does:
- Contacts Nexus Mods to get the list of mods in the collection
- Downloads each mod file (archives stay as `.zip`, `.7z`, `.rar`, etc.)
- Saves everything to `~/mods/bg3` (a "mods" folder in your home directory)

Each collection gets its own named subfolder inside the mods directory, so you can sync multiple collections for the same game without them mixing together.

This can take a while depending on how many mods are in the collection. You'll see progress as each mod downloads. If you need to stop partway through, that's fine - re-running `sync` picks up where you left off, skipping mods that were already downloaded.

### Skipping optional mods

Some collections mark certain mods as optional. To skip those:

```bash
nexus-dl sync --skip-optional "https://next.nexusmods.com/baldursgate3/collections/abc123" ~/mods/bg3
```

### File naming

Each downloaded file is named after the mod, its ID, version, and file ID, so you always know where it came from:

```
{mod name}-{mod id}-{version}-{file id}{extension}
```

For example:

```
Ring of Mind Shielding Edit-19607-1-0-1762818108.zip
```

That's the mod `Ring of Mind Shielding Edit`, mod id 19607, version 1.0 (dots become dashes), file id 1762818108.

## Downloading a single mod

You can also download an individual mod by its page URL:

```bash
nexus-dl download "https://www.nexusmods.com/starfield/mods/123" ~/mods/starfield
```

This downloads the mod's main file. If a mod has several files and the tool can't tell which one is the main one, it lists the available file IDs - pick one and re-run with `--file-id`:

```bash
nexus-dl download "https://www.nexusmods.com/starfield/mods/123" ~/mods/starfield --file-id 456
```

## If you have a free account

If you don't have Nexus Mods Premium, the tool does everything except the actual file download. You download the mod files yourself through the browser (Nexus shows a countdown timer for free downloads).

### Step 1: Sync the collection

Run the same sync command as Premium users:

```bash
nexus-dl sync "https://next.nexusmods.com/baldursgate3/collections/abc123" ~/mods/bg3
```

The tool fetches the collection metadata and shows you a table with each mod's name, filename, and a clickable URL:

```
Pending Downloads (manual)
Mod                  | Filename              | Size    | URL
Script Extender      | ScriptExtender-v2.zip | 12.3 MB | https://www.nexusmods.com/baldursgate3/mods/...
Better UI            | BetterUI-1.5.pak      | 4.1 MB  | https://www.nexusmods.com/baldursgate3/mods/...
...

Free account detected. Download the files above through your browser and save them to ~/mods/bg3/My Collection.
```

### Step 2: Download the files

Click each URL. Nexus Mods will show its standard free download page with a countdown timer. When the download starts, save the file to the collection directory shown at the bottom of the table.

You don't have to download everything at once - grab as many as you like, and re-run `sync` later to get an updated list.

## Troubleshooting

### "python3: command not found"

Python isn't installed. See the [Checking Python](#checking-python) section above for install commands.

### "nexus-dl: command not found"

You probably need to activate the virtual environment:

```bash
cd ~/nexus-collection-dl
source venv/bin/activate
```

If that doesn't work, try re-running `./setup.sh`.

### "Permission denied" when running setup.sh

The setup script needs execute permission:

```bash
chmod +x setup.sh
./setup.sh
```

### Rate limiting / "429 Too Many Requests"

Nexus Mods limits how many requests you can make per hour. If you hit this, wait a few minutes and try again. The tool handles rate limits automatically in most cases, but very large collections might need a retry.

### "NEXUS_API_KEY not set"

You need to set your API key. See [Setting your API key](#setting-your-api-key) above. If you set it with the permanent method, make sure you ran `source ~/.bashrc` or opened a new terminal.

### Something else went wrong

Check the [Issues page](https://github.com/scottmccarrison/nexus-collection-dl/issues) on GitHub to see if someone has reported the same problem, or open a new issue with the error message you're seeing.
