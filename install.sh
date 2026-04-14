#!/usr/bin/env bash
# ============================================================
#  WhisperX-App — One-line installer
#
#  Usage (remote):
#    curl -sSL https://raw.githubusercontent.com/Raindancer118/whisperx-app/main/install.sh | bash
#
#  Usage (local):
#    bash install.sh
# ============================================================
set -euo pipefail

# ---- colours -----------------------------------------------
if [ -t 1 ]; then
  BOLD="\033[1m"; CYAN="\033[1;36m"; GREEN="\033[1;32m"
  YELLOW="\033[1;33m"; RED="\033[1;31m"; DIM="\033[2m"; RESET="\033[0m"
else
  BOLD=""; CYAN=""; GREEN=""; YELLOW=""; RED=""; DIM=""; RESET=""
fi

# ---- helpers -----------------------------------------------
info()    { echo -e "${CYAN}  →${RESET} $*"; }
success() { echo -e "${GREEN}  ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}  ⚠${RESET} $*"; }
error()   { echo -e "${RED}  ✗${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }
section() { echo -e "\n${BOLD}$*${RESET}"; }

# Ensure a directory is on PATH and persisted to the shell rc file
_ensure_path() {
  local dir="$1"
  # Check if already on PATH
  case ":$PATH:" in
    *":$dir:"*) return 0 ;;
  esac

  # Add to the first existing rc file
  local target_rc=""
  for rcfile in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    if [ -f "$rcfile" ]; then
      target_rc="$rcfile"
      break
    fi
  done
  [ -z "$target_rc" ] && target_rc="$HOME/.bashrc"

  if ! grep -q "$dir" "$target_rc" 2>/dev/null; then
    {
      echo ""
      echo "# Added by whisperx-app installer"
      echo "export PATH=\"$dir:\$PATH\""
    } >> "$target_rc"
    info "PATH erweitert in $target_rc"
  fi

  export PATH="$dir:$PATH"
}

# ============================================================
# BANNER
# ============================================================
echo ""
echo -e "${CYAN}${BOLD}"
echo "  ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗     ██╗  ██╗"
echo "  ██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗    ╚██╗██╔╝"
echo "  ██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝     ╚███╔╝ "
echo "  ██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗     ██╔██╗ "
echo "  ╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║    ██╔╝ ██╗"
echo "   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝"
echo -e "${RESET}"
echo -e "  ${DIM}Audio transcription with speaker diarization — installer${RESET}"
echo ""

# ============================================================
# 1. PYTHON CHECK
# ============================================================
section "[ 1 / 5 ]  Python prüfen"

PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || true)
    major=${ver%%.*}
    minor=${ver##*.}
    if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 10 ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

[ -n "$PYTHON" ] || die "Python 3.10+ nicht gefunden.
  Bitte installieren: https://www.python.org/downloads/"

success "Python $ver gefunden  ($PYTHON)"

# ============================================================
# 2. FFMPEG CHECK
# ============================================================
section "[ 2 / 5 ]  ffmpeg / ffprobe prüfen"

if command -v ffprobe &>/dev/null; then
  success "ffprobe gefunden"
else
  warn "ffprobe nicht gefunden — WhisperX benötigt ffmpeg für Audiodauer-Erkennung"
  echo ""
  echo -e "  ${DIM}Bitte ffmpeg installieren:${RESET}"
  case "$(uname -s)" in
    Linux*)
      if command -v pacman &>/dev/null; then
        echo -e "    ${DIM}sudo pacman -S ffmpeg${RESET}          # Arch / Manjaro"
      elif command -v apt-get &>/dev/null; then
        echo -e "    ${DIM}sudo apt-get install -y ffmpeg${RESET}  # Debian / Ubuntu"
      elif command -v dnf &>/dev/null; then
        echo -e "    ${DIM}sudo dnf install ffmpeg${RESET}         # Fedora"
      else
        echo -e "    ${DIM}Paketmanager: ffmpeg${RESET}"
      fi
      ;;
    Darwin*)
      echo -e "    ${DIM}brew install ffmpeg${RESET}"
      ;;
    *)
      echo -e "    ${DIM}https://ffmpeg.org/download.html${RESET}"
      ;;
  esac
  echo ""
  warn "Installation wird fortgesetzt — ffmpeg kann später nachgeholt werden."
fi

# ============================================================
# 3. INSTALL METHOD: pipx (preferred) → venv fallback
# ============================================================
section "[ 3 / 5 ]  Installationsmethode wählen"

INSTALL_METHOD=""
PIPX_CMD=""

# Check for pipx (system command)
if command -v pipx &>/dev/null; then
  PIPX_CMD="pipx"
  INSTALL_METHOD="pipx"
  info "pipx gefunden — verwende pipx (empfohlen)"

# Check for pipx as python module
elif "$PYTHON" -m pipx --version &>/dev/null 2>&1; then
  PIPX_CMD="$PYTHON -m pipx"
  INSTALL_METHOD="pipx"
  info "pipx via python -m pipx gefunden"

# Try to install pipx automatically
else
  info "pipx nicht gefunden — installiere pipx..."
  if "$PYTHON" -m pip install --user pipx --quiet 2>/dev/null; then
    PIPX_BIN="$("$PYTHON" -m site --user-base)/bin"
    _ensure_path "$PIPX_BIN"
    if command -v pipx &>/dev/null; then
      PIPX_CMD="pipx"
      INSTALL_METHOD="pipx"
      success "pipx installiert"
    elif "$PYTHON" -m pipx --version &>/dev/null 2>&1; then
      PIPX_CMD="$PYTHON -m pipx"
      INSTALL_METHOD="pipx"
      success "pipx installiert"
    fi
  fi
fi

# Fallback: dedicated venv
if [ -z "$INSTALL_METHOD" ]; then
  warn "pipx nicht verfügbar — Fallback: dedizierte venv unter ~/.whisperx-app/venv"
  INSTALL_METHOD="venv"
fi

success "Installationsmethode: ${BOLD}${INSTALL_METHOD}${RESET}"

# ============================================================
# 4. INSTALL / UPGRADE whisperx-app
# ============================================================
section "[ 4 / 5 ]  WhisperX-App installieren"

case "$INSTALL_METHOD" in

  # ---- pipx ------------------------------------------------
  pipx)
    if $PIPX_CMD list 2>/dev/null | grep -q "whisperx-app"; then
      info "Bereits installiert — aktualisiere auf neueste Version..."
      $PIPX_CMD upgrade whisperx-app
    else
      info "Installiere whisperx-app via pipx..."
      $PIPX_CMD install whisperx-app
    fi
    ;;

  # ---- venv fallback ----------------------------------------
  venv)
    VENV_DIR="$HOME/.whisperx-app/venv"
    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"

    if [ -d "$VENV_DIR" ]; then
      info "Bestehende venv gefunden — aktualisiere..."
      "$VENV_DIR/bin/pip" install --upgrade whisperx-app --quiet
    else
      info "Erstelle venv unter $VENV_DIR ..."
      "$PYTHON" -m venv "$VENV_DIR"
      "$VENV_DIR/bin/pip" install --upgrade pip --quiet
      info "Installiere whisperx-app..."
      "$VENV_DIR/bin/pip" install whisperx-app --quiet
    fi

    # Wrapper script so `whisperx-app` works from any directory
    WRAPPER="$LOCAL_BIN/whisperx-app"
    cat > "$WRAPPER" <<WRAPPER_SCRIPT
#!/usr/bin/env bash
exec "$VENV_DIR/bin/whisperx-app" "\$@"
WRAPPER_SCRIPT
    chmod +x "$WRAPPER"
    success "Wrapper erstellt: $WRAPPER"
    _ensure_path "$LOCAL_BIN"
    ;;
esac

success "whisperx-app installiert"

# ============================================================
# 5. VERIFY + DONE
# ============================================================
section "[ 5 / 5 ]  Installation prüfen"

# Resolve the binary (PATH may not be refreshed in current shell)
WXAPP=""
for candidate in \
  "$(command -v whisperx-app 2>/dev/null || true)" \
  "$HOME/.local/bin/whisperx-app" \
  "$HOME/.local/pipx/venvs/whisperx-app/bin/whisperx-app"
do
  if [ -x "${candidate:-}" ]; then
    WXAPP="$candidate"
    break
  fi
done

if [ -n "$WXAPP" ]; then
  INSTALLED_VERSION=$("$WXAPP" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "?")
  success "whisperx-app ${INSTALLED_VERSION}  →  $WXAPP"
else
  warn "Binary noch nicht im aktuellen PATH — bitte Terminal neu starten"
fi

# ---- done banner -------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}  ✓ Installation abgeschlossen!${RESET}"
echo ""
echo -e "  ${BOLD}Jetzt starten:${RESET}"
echo -e "    ${CYAN}whisperx-app${RESET}                       Interaktiver Flow"
echo -e "    ${CYAN}whisperx-app transcribe audio.mp3${RESET}  Direkt transkribieren"
echo -e "    ${CYAN}whisperx-app check${RESET}                 Systemcheck"
echo -e "    ${CYAN}whisperx-app update${RESET}                Auf Updates prüfen"
echo -e "    ${CYAN}whisperx-app --help${RESET}                Alle Befehle"
echo ""

if ! command -v whisperx-app &>/dev/null 2>&1; then
  echo -e "  ${YELLOW}${BOLD}Hinweis:${RESET} Starte ein neues Terminal oder führe aus:${RESET}"
  echo -e "    ${DIM}source ~/.bashrc   # bzw. ~/.zshrc${RESET}"
  echo ""
fi
