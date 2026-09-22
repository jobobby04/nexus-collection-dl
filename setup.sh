#!/usr/bin/env bash
set -euo pipefail

echo "=== nexus-collection-dl setup ==="

# Check Python version
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$cmd" -c "import sys; print(sys.version_info.major)")
        minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            echo "Found Python $version ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.10+ is required but not found."
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

# Install the tool
echo "Installing nexus-collection-dl..."
pip install -e . --quiet

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Usage:"
echo "  source venv/bin/activate"
echo "  export NEXUS_API_KEY='your-key-here'"
echo "  nexus-dl sync 'https://next.nexusmods.com/GAME/collections/SLUG' ./mods"
