#!/usr/bin/env bash
# ============================================================
#  WhisperX-App — Installer
#  curl -sSL https://raw.githubusercontent.com/Raindancer118/whisperx-app/main/install.sh | bash
# ============================================================
set -euo pipefail
IFS=$'\n\t'

# ── Terminal-Capabilities ────────────────────────────────────
_tty() { [ -t 1 ] && [ -t 2 ]; }

if _tty; then
  BOLD="\033[1m";    DIM="\033[2m";     ITALIC="\033[3m"
  RESET="\033[0m";   UP="\033[1A";      CR="\033[2K\r"
  C_BG="\033[48;5;235m"                 # dark background
  C_CYAN="\033[38;5;87m"
  C_BLUE="\033[38;5;75m"
  C_GREEN="\033[38;5;84m"
  C_YELLOW="\033[38;5;220m"
  C_RED="\033[38;5;203m"
  C_WHITE="\033[38;5;255m"
  C_GRAY="\033[38;5;244m"
  C_PURPLE="\033[38;5;141m"
  HIDE_CURSOR="\033[?25l"; SHOW_CURSOR="\033[?25h"
else
  BOLD=""; DIM=""; ITALIC=""; RESET=""; UP=""; CR=""
  C_BG=""; C_CYAN=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""
  C_RED=""; C_WHITE=""; C_GRAY=""; C_PURPLE=""
  HIDE_CURSOR=""; SHOW_CURSOR=""
fi

# ── Cleanup: immer Cursor wiederherstellen ───────────────────
trap 'printf "%b" "${SHOW_CURSOR}${RESET}"; echo ""' EXIT INT TERM

# ── Hilfsfunktionen ──────────────────────────────────────────
_width() { tput cols 2>/dev/null || echo 72; }
_pad()   { printf "%-${1}s" "$2"; }

_line() {
  local w; w=$(_width)
  printf "${C_GRAY}  "
  printf '─%.0s' $(seq 1 $((w - 4)))
  printf "${RESET}\n"
}

_box_top() {
  local w; w=$(_width)
  local inner=$((w - 4))
  printf "${C_GRAY}  ╭"
  printf '─%.0s' $(seq 1 $inner)
  printf "╮${RESET}\n"
}

_box_bottom() {
  local w; w=$(_width)
  local inner=$((w - 4))
  printf "${C_GRAY}  ╰"
  printf '─%.0s' $(seq 1 $inner)
  printf "╯${RESET}\n"
}

_box_row() {
  local w; w=$(_width)
  local inner=$((w - 4))
  printf "${C_GRAY}  │${RESET}%-${inner}s${C_GRAY}│${RESET}\n" "$1"
}

# Progress bar: _pbar <current> <total> <label>
_pbar() {
  local cur=$1 tot=$2 label=$3
  local w; w=$(( $(_width) - 20 ))
  [ "$w" -lt 10 ] && w=10
  local filled=$(( cur * w / tot ))
  local empty=$(( w - filled ))
  printf "  ${C_GRAY}[${C_GREEN}"
  printf '█%.0s' $(seq 1 "$filled") 2>/dev/null || true
  printf "${C_GRAY}"
  printf '░%.0s' $(seq 1 "$empty") 2>/dev/null || true
  printf "${C_GRAY}]${RESET} ${C_WHITE}%3d%%${RESET}  ${C_GRAY}%s${RESET}" \
    $(( cur * 100 / tot )) "$label"
}

# Spinner: _spin <pid> <label>
_spin() {
  local pid=$1 label=$2
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  local i=0
  printf "%b" "$HIDE_CURSOR"
  while kill -0 "$pid" 2>/dev/null; do
    printf "  ${C_CYAN}${frames[$((i % 10))]}${RESET}  ${C_GRAY}%s${RESET}   \r" "$label"
    sleep 0.08
    i=$(( i + 1 ))
  done
  printf "%b" "$SHOW_CURSOR"
  printf "%b" "$CR"
}

_ok()   { printf "  ${C_GREEN}✓${RESET}  %b\n" "$*"; }
_info() { printf "  ${C_BLUE}·${RESET}  %b\n" "$*"; }
_warn() { printf "  ${C_YELLOW}!${RESET}  %b\n" "$*"; }
_err()  { printf "  ${C_RED}✗${RESET}  %b\n" "$*" >&2; }
_die()  { _err "$*"; printf "%b" "$SHOW_CURSOR"; exit 1; }

# Run silently in background, show spinner
_run() {
  local label=$1; shift
  ("$@" &>/tmp/whisperx_install.log) &
  local pid=$!
  _spin "$pid" "$label"
  wait "$pid" || {
    _err "$label fehlgeschlagen"
    cat /tmp/whisperx_install.log >&2
    exit 1
  }
  _ok "$label"
}

# ── STEP COUNTER ─────────────────────────────────────────────
TOTAL_STEPS=6
CURRENT_STEP=0

_step() {
  CURRENT_STEP=$(( CURRENT_STEP + 1 ))
  echo ""
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}%s${RESET}\n" \
    "$CURRENT_STEP" "$TOTAL_STEPS" "$1"
  _line
}

_progress_header() {
  echo ""
  _pbar "$CURRENT_STEP" "$TOTAL_STEPS" "$1"
  echo ""
}

# ════════════════════════════════════════════════════════════
# WELCOME SCREEN
# ════════════════════════════════════════════════════════════
clear 2>/dev/null || true
printf "%b" "$HIDE_CURSOR"

echo ""
_box_top
_box_row ""
_box_row "$(printf "  ${C_CYAN}${BOLD}  ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗     ██╗  ██╗${RESET}")"
_box_row "$(printf "  ${C_CYAN}${BOLD}  ██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗    ╚██╗██╔╝${RESET}")"
_box_row "$(printf "  ${C_CYAN}${BOLD}  ██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝     ╚███╔╝ ${RESET}")"
_box_row "$(printf "  ${C_CYAN}${BOLD}  ██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗     ██╔██╗ ${RESET}")"
_box_row "$(printf "  ${C_CYAN}${BOLD}  ╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║    ██╔╝ ██╗${RESET}")"
_box_row "$(printf "  ${C_CYAN}${BOLD}   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝${RESET}")"
_box_row ""
_box_row "$(printf "      ${C_WHITE}Audio-Transkription mit Sprecher-Diarisierung${RESET}  ${C_GRAY}· CLI Installer${RESET}")"
_box_row ""
_box_bottom

echo ""
printf "  ${C_WHITE}${BOLD}Hey, willkommen! 👋${RESET}\n"
echo ""
printf "  ${C_GRAY}Wir installieren gleich alles, was du brauchst — Python-Pakete,${RESET}\n"
printf "  ${C_GRAY}System-Abhängigkeiten, das volle Programm. Du musst nichts weiter tun.${RESET}\n"
echo ""
printf "  ${C_YELLOW}${BOLD}Einzige Sache:${RESET}${C_YELLOW} Wir brauchen kurz dein sudo-Passwort,${RESET}\n"
printf "  ${C_YELLOW}damit wir ffmpeg installieren können. Einmal eingeben — dann läuft alles.${RESET}\n"
echo ""
printf "  ${C_GRAY}Lehn dich zurück. Wir sind gleich fertig. ✌️${RESET}\n"
echo ""
_line
echo ""

# ════════════════════════════════════════════════════════════
# SUDO: Passwort einmalig cachen
# ════════════════════════════════════════════════════════════
_step "Berechtigungen"

printf "  ${C_GRAY}Sudo-Passwort wird einmalig gecacht (für System-Pakete)${RESET}\n"
if sudo -v 2>/dev/null; then
  _ok "sudo-Zugriff bestätigt"
  # Keep sudo alive in background
  ( while true; do sudo -n true; sleep 50; done ) &
  SUDO_KEEP_PID=$!
  trap 'kill $SUDO_KEEP_PID 2>/dev/null; printf "%b" "${SHOW_CURSOR}${RESET}"; echo ""' EXIT INT TERM
else
  _warn "sudo nicht verfügbar — System-Pakete werden übersprungen"
  SUDO_KEEP_PID=""
fi

_progress_header "Berechtigungen ✓"

# ════════════════════════════════════════════════════════════
# PYTHON CHECK
# ════════════════════════════════════════════════════════════
_step "Python prüfen"

PYTHON=""
PY_VER=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || true)
    major=${ver%%.*}; minor=${ver##*.}
    if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 10 ]; then
      PYTHON="$cmd"; PY_VER="$ver"; break
    fi
  fi
done

[ -n "$PYTHON" ] || _die "Python 3.10+ nicht gefunden → https://www.python.org/downloads/"
_ok "Python $PY_VER  ${C_GRAY}($PYTHON)${RESET}"

_progress_header "Python ✓"

# ════════════════════════════════════════════════════════════
# FFMPEG  (auto-install wenn sudo verfügbar)
# ════════════════════════════════════════════════════════════
_step "ffmpeg installieren"

if command -v ffprobe &>/dev/null; then
  _ok "ffprobe bereits installiert"
else
  _info "ffmpeg wird benötigt — installiere jetzt..."

  FFMPEG_INSTALLED=false
  if sudo -n true 2>/dev/null; then
    OS="$(uname -s)"
    case "$OS" in
      Linux*)
        if command -v pacman &>/dev/null; then
          _run "ffmpeg installieren (pacman)" sudo pacman -S --noconfirm ffmpeg
          FFMPEG_INSTALLED=true
        elif command -v apt-get &>/dev/null; then
          _run "apt update"           sudo apt-get update -qq
          _run "ffmpeg installieren"  sudo apt-get install -y -qq ffmpeg
          FFMPEG_INSTALLED=true
        elif command -v dnf &>/dev/null; then
          _run "ffmpeg installieren (dnf)" sudo dnf install -y ffmpeg
          FFMPEG_INSTALLED=true
        fi
        ;;
      Darwin*)
        if command -v brew &>/dev/null; then
          _run "ffmpeg installieren (brew)" brew install ffmpeg
          FFMPEG_INSTALLED=true
        fi
        ;;
    esac
  fi

  if $FFMPEG_INSTALLED; then
    _ok "ffmpeg installiert"
  else
    _warn "ffmpeg konnte nicht automatisch installiert werden"
    _warn "Bitte manuell nachinstallieren:"
    command -v pacman  &>/dev/null && printf "    ${C_GRAY}sudo pacman -S ffmpeg${RESET}\n"
    command -v apt-get &>/dev/null && printf "    ${C_GRAY}sudo apt-get install ffmpeg${RESET}\n"
    command -v brew    &>/dev/null && printf "    ${C_GRAY}brew install ffmpeg${RESET}\n"
  fi
fi

_progress_header "ffmpeg ✓"

# ════════════════════════════════════════════════════════════
# INSTALL METHOD: pipx bevorzugt
# ════════════════════════════════════════════════════════════
_step "Installationsmethode"

# Helper: ensure a directory is on PATH + persisted to shell rc
_ensure_path() {
  local dir="$1"
  case ":$PATH:" in *":$dir:"*) return 0 ;; esac
  local rc=""
  for f in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
    [ -f "$f" ] && rc="$f" && break
  done
  [ -z "$rc" ] && rc="$HOME/.bashrc"
  if ! grep -q "$dir" "$rc" 2>/dev/null; then
    { echo ""; echo "# Added by whisperx-app installer"; echo "export PATH=\"$dir:\$PATH\""; } >> "$rc"
    _info "PATH erweitert in $rc"
  fi
  export PATH="$dir:$PATH"
}

INSTALL_METHOD=""
PIPX_CMD=""

if command -v pipx &>/dev/null; then
  PIPX_CMD="pipx"; INSTALL_METHOD="pipx"
  _ok "pipx gefunden"
elif "$PYTHON" -m pipx --version &>/dev/null 2>&1; then
  PIPX_CMD="$PYTHON -m pipx"; INSTALL_METHOD="pipx"
  _ok "pipx (python -m pipx)"
else
  _info "pipx nicht gefunden — wird installiert..."
  if "$PYTHON" -m pip install --user pipx --quiet 2>/dev/null; then
    PIPX_BIN="$("$PYTHON" -m site --user-base)/bin"
    _ensure_path "$PIPX_BIN"
    if command -v pipx &>/dev/null; then
      PIPX_CMD="pipx"; INSTALL_METHOD="pipx"; _ok "pipx installiert"
    elif "$PYTHON" -m pipx --version &>/dev/null 2>&1; then
      PIPX_CMD="$PYTHON -m pipx"; INSTALL_METHOD="pipx"; _ok "pipx installiert"
    fi
  fi
fi

if [ -z "$INSTALL_METHOD" ]; then
  INSTALL_METHOD="venv"
  _warn "Fallback: dedizierte venv (~/.whisperx-app/venv)"
else
  _ok "Installationsmethode: ${C_CYAN}${BOLD}pipx${RESET} ${C_GRAY}(global, sauber isoliert)${RESET}"
fi

_progress_header "Installationsmethode ✓"

# ════════════════════════════════════════════════════════════
# INSTALL whisperx-app
# ════════════════════════════════════════════════════════════
_step "WhisperX-App installieren"

# Install source: GitHub repo (switches to "whisperx-app" once published on PyPI)
GITHUB_URL="git+https://github.com/Raindancer118/whisperx-app.git"
PYPI_NAME="whisperx-app"

# Try PyPI first; fall back to GitHub if not yet published
_resolve_package_source() {
  if "$PYTHON" -m pip index versions "$PYPI_NAME" &>/dev/null 2>&1; then
    echo "$PYPI_NAME"
  else
    echo "$GITHUB_URL"
  fi
}

PKG_SOURCE=$(_resolve_package_source)
_info "Installationsquelle: ${C_CYAN}$PKG_SOURCE${RESET}"

case "$INSTALL_METHOD" in
  pipx)
    if $PIPX_CMD list 2>/dev/null | grep -q "whisperx-app"; then
      _info "Bereits installiert — aktualisiere..."
      # For git-installed packages pipx upgrade re-fetches from the original source;
      # for PyPI packages it pulls the latest version.
      _run "whisperx-app upgraden" $PIPX_CMD upgrade whisperx-app \
        || _run "whisperx-app neu installieren" $PIPX_CMD install --force "$PKG_SOURCE"
    else
      _run "whisperx-app installieren" $PIPX_CMD install "$PKG_SOURCE"
    fi
    ;;
  venv)
    VENV_DIR="$HOME/.whisperx-app/venv"
    LOCAL_BIN="$HOME/.local/bin"
    mkdir -p "$LOCAL_BIN"
    if [ -d "$VENV_DIR" ]; then
      _info "venv gefunden — upgrade..."
      _run "whisperx-app upgraden" "$VENV_DIR/bin/pip" install --upgrade "$PKG_SOURCE" --quiet
    else
      _run "venv erstellen"               "$PYTHON" -m venv "$VENV_DIR"
      _run "pip upgraden"                 "$VENV_DIR/bin/pip" install --upgrade pip --quiet
      _run "whisperx-app installieren"    "$VENV_DIR/bin/pip" install "$PKG_SOURCE" --quiet
    fi
    WRAPPER="$LOCAL_BIN/whisperx-app"
    printf '#!/usr/bin/env bash\nexec "%s/bin/whisperx-app" "$@"\n' "$VENV_DIR" > "$WRAPPER"
    chmod +x "$WRAPPER"
    _ensure_path "$LOCAL_BIN"
    _ok "Wrapper erstellt: $WRAPPER"
    ;;
esac

_progress_header "Installation ✓"

# ════════════════════════════════════════════════════════════
# VERIFY
# ════════════════════════════════════════════════════════════
_step "Alles checken"

WXAPP=""
for cand in \
  "$(command -v whisperx-app 2>/dev/null || true)" \
  "$HOME/.local/bin/whisperx-app" \
  "$HOME/.local/pipx/venvs/whisperx-app/bin/whisperx-app"
do
  [ -x "${cand:-}" ] && WXAPP="$cand" && break
done

if [ -n "$WXAPP" ]; then
  VER=$("$WXAPP" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "?")
  _ok "${C_WHITE}${BOLD}whisperx-app $VER${RESET}  ${C_GRAY}→  $WXAPP${RESET}"
else
  _warn "Binary nicht sofort im PATH — bitte Terminal neu starten"
fi

if command -v ffprobe &>/dev/null; then _ok "ffprobe verfügbar"
else                                    _warn "ffprobe fehlt — bitte ffmpeg nachinstallieren"; fi

_progress_header "Alles bereit  🎉"

# ════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════
echo ""
echo ""
_box_top
_box_row ""
_box_row "$(printf "    ${C_GREEN}${BOLD}  Fertig! Du bist ready. 🚀${RESET}")"
_box_row ""
_box_row "$(printf "    ${C_WHITE}Starte jetzt mit:${RESET}")"
_box_row ""
_box_row "$(printf "      ${C_CYAN}whisperx-app${RESET}${C_GRAY}                       → Interaktiver Flow${RESET}")"
_box_row "$(printf "      ${C_CYAN}whisperx-app transcribe audio.mp3${RESET}${C_GRAY}  → Direkt loslegen${RESET}")"
_box_row "$(printf "      ${C_CYAN}whisperx-app check${RESET}${C_GRAY}                 → Systemcheck${RESET}")"
_box_row "$(printf "      ${C_CYAN}whisperx-app update${RESET}${C_GRAY}                → Auf Updates prüfen${RESET}")"
_box_row "$(printf "      ${C_CYAN}whisperx-app --help${RESET}${C_GRAY}                → Alle Befehle${RESET}")"
_box_row ""
_box_row "$(printf "    ${C_GRAY}${ITALIC}Beim ersten Start werden ML-Pakete (Whisper, PyAnnote, …)${RESET}")"
_box_row "$(printf "    ${C_GRAY}${ITALIC}automatisch angeboten — einfach bestätigen.${RESET}")"
_box_row ""
_box_bottom

if ! command -v whisperx-app &>/dev/null 2>&1; then
  echo ""
  printf "  ${C_YELLOW}${BOLD}Tipp:${RESET}${C_YELLOW} Starte ein neues Terminal, damit PATH aktiv wird.${RESET}\n"
  printf "  ${C_GRAY}Oder: source ~/.bashrc  /  source ~/.zshrc${RESET}\n"
fi

echo ""
printf "%b" "$SHOW_CURSOR"
