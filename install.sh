#!/usr/bin/env bash

# ytune — Automated Installer for Linux
# Sets up system dependencies, Python virtual environment, package dependencies, and browser engines.

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}           ytune — Automated Installer             ${NC}"
echo -e "${BLUE}==================================================${NC}"
echo

# 1. Ensure we are in the project root directory
if [ ! -f "pyproject.toml" ] || [ ! -d "ytune" ]; then
    echo -e "${RED}Error: Please run this script from the ytune project root directory.${NC}"
    exit 1
fi

# 2. Check and Install System Dependencies
echo -e "${BLUE}[1/6] Checking system dependencies...${NC}"

SYS_DEPS_SATISFIED=true

if ! command -v mpv &> /dev/null; then
    SYS_DEPS_SATISFIED=false
fi

# Check for a JS runtime (deno or node)
if ! command -v deno &> /dev/null && ! command -v node &> /dev/null; then
    SYS_DEPS_SATISFIED=false
fi

install_dependencies() {
    if [ -x "$(command -v pacman)" ]; then
        echo -e "${GREEN}Detected Arch Linux system.${NC}"
        echo -e "${YELLOW}Installing mpv and deno (requires sudo)...${NC}"
        sudo pacman -S --needed --noconfirm mpv deno
    elif [ -x "$(command -v apt-get)" ]; then
        echo -e "${GREEN}Detected Debian/Ubuntu system.${NC}"
        echo -e "${YELLOW}Updating package index and installing dependencies (requires sudo)...${NC}"
        sudo apt-get update
        sudo apt-get install -y mpv libmpv-dev nodejs python3-venv python3-pip python3-dev build-essential
    elif [ -x "$(command -v dnf)" ]; then
        echo -e "${GREEN}Detected Fedora/RHEL system.${NC}"
        echo -e "${YELLOW}Installing dependencies (requires sudo)...${NC}"
        sudo dnf install -y mpv mpv-libs-devel nodejs python3-devel gcc
    else
        echo -e "${YELLOW}Warning: Could not detect package manager (pacman, apt, dnf).${NC}"
        echo -e "${YELLOW}Please ensure that 'mpv' (including 'libmpv') and a JavaScript runtime ('deno' or 'node') are installed manually.${NC}"
    fi
}

if [ "$SYS_DEPS_SATISFIED" = true ]; then
    echo -e "${GREEN}✓ System dependencies (mpv and JavaScript runtime) are already installed.${NC}"
else
    echo -e "${YELLOW}System dependencies are missing. Proceeding with installation...${NC}"
    install_dependencies
fi

# 3. Check Python 3
echo
echo -e "${BLUE}[2/6] Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed on this system.${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}Found Python version: ${PYTHON_VERSION}${NC}"

# 4. Create and set up Virtual Environment
echo
echo -e "${BLUE}[3/6] Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "Creating virtual environment in .venv...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}Virtual environment .venv already exists.${NC}"
fi

# Upgrade pip
echo "Upgrading pip, setuptools, and wheel..."
.venv/bin/pip install --upgrade pip setuptools wheel

# 5. Install package and Python dependencies
echo
echo -e "${BLUE}[4/6] Installing package and Python dependencies...${NC}"
.venv/bin/pip install -e .

# 6. Set up Playwright browser engines
echo
echo -e "${BLUE}[5/6] Setting up browser automation engines for login flow...${NC}"
.venv/bin/python -m playwright install chromium

# 7. Create global/user symlink
echo
echo -e "${BLUE}[6/6] Creating user executable wrapper...${NC}"
mkdir -p "$HOME/.local/bin"
ln -sf "$(pwd)/.venv/bin/ytune" "$HOME/.local/bin/ytune"
echo -e "${GREEN}✓ Symlinked '.venv/bin/ytune' -> '$HOME/.local/bin/ytune'${NC}"

echo
echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}        Installation Completed Successfully!       ${NC}"
echo -e "${GREEN}==================================================${NC}"
echo
echo -e "You can now run ytune from anywhere!"
echo -e "To start, run:"
echo -e "  ${BLUE}ytune auth${NC}"
echo
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "${YELLOW}Warning: '$HOME/.local/bin' is not in your PATH environment variable.${NC}"
    echo -e "${YELLOW}You can add it by appending the following line to your ~/.bashrc or ~/.zshrc:${NC}"
    echo -e "  ${BLUE}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo -e "  Then reload your shell: ${BLUE}source ~/.bashrc${NC} (or ~/.zshrc)"
    echo
fi
