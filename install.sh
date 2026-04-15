#!/usr/bin/env bash
# ============================================================
#  WhisperX-App — One-line installer
#  curl -sSL https://raw.githubusercontent.com/Raindancer118/whisperx-app/main/install.sh | bash
# ============================================================
set -euo pipefail
IFS=$'\n\t'

# ── Terminal colours ─────────────────────────────────────────
if [ -t 1 ]; then
  BOLD="\033[1m"; DIM="\033[2m"; ITALIC="\033[3m"; RESET="\033[0m"
  UP="\033[1A"; CR="\033[2K\r"
  C_CYAN="\033[38;5;87m";   C_BLUE="\033[38;5;75m";  C_GREEN="\033[38;5;84m"
  C_YELLOW="\033[38;5;220m"; C_RED="\033[38;5;203m";  C_WHITE="\033[38;5;255m"
  C_GRAY="\033[38;5;244m";   C_PURPLE="\033[38;5;141m"
  HIDE_CURSOR="\033[?25l"; SHOW_CURSOR="\033[?25h"
else
  BOLD=""; DIM=""; ITALIC=""; RESET=""; UP=""; CR=""
  C_CYAN=""; C_BLUE=""; C_GREEN=""; C_YELLOW=""
  C_RED=""; C_WHITE=""; C_GRAY=""; C_PURPLE=""
  HIDE_CURSOR=""; SHOW_CURSOR=""
fi

trap 'printf "%b" "${SHOW_CURSOR}${RESET}"; echo ""' EXIT INT TERM

# ── Helpers ──────────────────────────────────────────────────
_width()  { tput cols 2>/dev/null || echo 72; }
_line()   { local w; w=$(_width); printf "${C_GRAY}  "; printf '─%.0s' $(seq 1 $((w-4))); printf "${RESET}\n"; }
_ok()     { printf "  ${C_GREEN}✓${RESET}  %b\n" "$*"; }
_info()   { printf "  ${C_BLUE}·${RESET}  %b\n" "$*"; }
_warn()   { printf "  ${C_YELLOW}!${RESET}  %b\n" "$*"; }
_err()    { printf "  ${C_RED}✗${RESET}  %b\n" "$*" >&2; }
_die()    { _err "$*"; printf "%b" "$SHOW_CURSOR"; exit 1; }

TOTAL_STEPS=7; CURRENT_STEP=0

_step() {
  CURRENT_STEP=$(( CURRENT_STEP + 1 ))
  echo ""
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}%s${RESET}\n" \
    "$CURRENT_STEP" "$TOTAL_STEPS" "$1"
  _line
}

_pbar() {
  local cur=$1 tot=$2 label=$3
  local w=$(( $(_width) - 18 )); [ "$w" -lt 10 ] && w=10
  local filled=$(( cur * w / tot )) empty=$(( w - (cur * w / tot) ))
  printf "  ${C_GRAY}[${C_GREEN}"; printf '█%.0s' $(seq 1 "$filled") 2>/dev/null || true
  printf "${C_GRAY}";              printf '░%.0s' $(seq 1 "$empty")  2>/dev/null || true
  printf "${C_GRAY}]${RESET} ${C_WHITE}%3d%%${RESET}  ${C_GRAY}%s${RESET}" \
    $(( cur * 100 / tot )) "$label"
}

_progress() { echo ""; _pbar "$CURRENT_STEP" "$TOTAL_STEPS" "$1"; echo ""; }

# Spinner: show while background job runs, then print ok/err
_run() {
  local label=$1; shift
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  local i=0
  rm -f /tmp/wx_install.log
  ("$@" &>/tmp/wx_install.log) &
  local pid=$!
  printf "%b" "$HIDE_CURSOR"
  while kill -0 "$pid" 2>/dev/null; do
    printf "  ${C_CYAN}${frames[$((i % 10))]}${RESET}  ${C_GRAY}%s${RESET}   \r" "$label"
    sleep 0.08; i=$(( i + 1 ))
  done
  printf "%b" "$SHOW_CURSOR$CR"
  if wait "$pid"; then
    _ok "$label"
  else
    _err "$label fehlgeschlagen"
    cat /tmp/wx_install.log >&2
    exit 1
  fi
}

# Ensure a dir is on PATH and persisted to shell rc
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

# ════════════════════════════════════════════════════════════
# BANNER
# ════════════════════════════════════════════════════════════
clear 2>/dev/null || true
printf "%b" "$HIDE_CURSOR"

printf "${C_CYAN}${BOLD}"
echo "  ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗     ██╗  ██╗"
echo "  ██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗    ╚██╗██╔╝"
echo "  ██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝     ╚███╔╝ "
echo "  ██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗     ██╔██╗ "
echo "  ╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║    ██╔╝ ██╗"
echo "   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝"
printf "${RESET}"
echo ""
printf "  ${C_GRAY}Audio-Transkription mit Sprecher-Diarisierung${RESET}  ${DIM}·  CLI Installer${RESET}\n"
echo ""
_line
echo ""
printf "  ${C_WHITE}${BOLD}Hey, willkommen! 👋${RESET}\n"
echo ""
printf "  ${C_GRAY}Wir installieren jetzt alles auf einmal — die App, alle ML-Pakete,${RESET}\n"
printf "  ${C_GRAY}System-Abhängigkeiten, das volle Programm. Du musst nichts weiter tun.${RESET}\n"
echo ""
printf "  ${C_YELLOW}${BOLD}Einzige Sache:${RESET}${C_YELLOW} Kurz dein sudo-Passwort, dann läuft alles durch.${RESET}\n"
echo ""
printf "  ${C_GRAY}Lehn dich zurück. Wir sind gleich fertig. ✌️${RESET}\n"
echo ""
_line

# ════════════════════════════════════════════════════════════
# STEP 1: SUDO
# ════════════════════════════════════════════════════════════
_step "Berechtigungen"

printf "  ${C_GRAY}sudo wird einmalig gecacht — danach automatisch${RESET}\n"
if sudo -v 2>/dev/null; then
  ( while true; do sudo -n true; sleep 50; done ) &
  SUDO_PID=$!
  trap 'kill ${SUDO_PID:-} 2>/dev/null; printf "%b" "${SHOW_CURSOR}${RESET}"; echo ""' EXIT INT TERM
  _ok "sudo-Zugriff bestätigt"
else
  _warn "sudo nicht verfügbar — System-Pakete werden übersprungen"
  SUDO_PID=""
fi

_progress "Berechtigungen ✓"

# ════════════════════════════════════════════════════════════
# STEP 2: PYTHON (whisperx braucht 3.10–3.13, NICHT 3.14+)
# ════════════════════════════════════════════════════════════
_step "Python 3.10–3.13 finden"

PYTHON=""; PY_VER=""

# Prefer a whisperx-compatible version (3.10 ≤ x < 3.14)
for cmd in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$cmd" &>/dev/null; then
    v=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || true)
    maj=${v%%.*}; min=${v##*.}
    if [ "${maj:-0}" -eq 3 ] && [ "${min:-0}" -ge 10 ] && [ "${min:-0}" -le 13 ]; then
      PYTHON="$cmd"; PY_VER="$v"; break
    fi
  fi
done

# If not found, try to install python3.11 via system package manager
if [ -z "$PYTHON" ]; then
  _warn "Kein Python 3.10–3.13 gefunden (whisperx benötigt <3.14)"
  _info "Installiere Python 3.11 über Paketmanager..."

  PY_INSTALLED=false
  if command -v pacman &>/dev/null && sudo -n true 2>/dev/null; then
    # On Arch/Manjaro the package is 'python311' (no dot) in extra repo
    _info "Installiere python311 via pacman..."
    if sudo pacman -S --noconfirm python311 >/tmp/wx_py.log 2>&1; then
      _ok "Python 3.11 installiert (pacman)"
      PY_INSTALLED=true
    else
      _info "python311 nicht gefunden, versuche python3.11..."
      if sudo pacman -S --noconfirm python3.11 >/tmp/wx_py.log 2>&1; then
        _ok "Python 3.11 installiert (pacman)"
        PY_INSTALLED=true
      fi
    fi

  elif command -v apt-get &>/dev/null && sudo -n true 2>/dev/null; then
    _run "apt update"                     sudo apt-get update -qq
    _run "Python 3.11 installieren (apt)" sudo apt-get install -y python3.11 python3.11-venv
    PY_INSTALLED=true

  elif command -v brew &>/dev/null; then
    _run "Python 3.11 installieren (brew)" brew install python@3.11
    PY_INSTALLED=true
  fi

  if ! $PY_INSTALLED; then
    cat /tmp/wx_py.log >&2 2>/dev/null || true
    _die "Kein kompatibles Python gefunden und kein Paketmanager verfügbar.
    Bitte Python 3.11 manuell installieren: https://www.python.org/downloads/"
  fi

  # Re-check after install
  for cmd in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cmd" &>/dev/null; then
      v=$("$cmd" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || true)
      maj=${v%%.*}; min=${v##*.}
      if [ "${maj:-0}" -eq 3 ] && [ "${min:-0}" -ge 10 ] && [ "${min:-0}" -le 13 ]; then
        PYTHON="$cmd"; PY_VER="$v"; break
      fi
    fi
  done
  [ -n "$PYTHON" ] || _die "Python 3.11 Installation fehlgeschlagen. Bitte manuell installieren."
fi

_ok "Python $PY_VER  ${C_GRAY}($PYTHON)${RESET}"
_progress "Python ✓"

# ════════════════════════════════════════════════════════════
# STEP 3: FFMPEG
# ════════════════════════════════════════════════════════════
_step "ffmpeg installieren"

if command -v ffprobe &>/dev/null; then
  _ok "ffprobe bereits installiert"
else
  _info "ffmpeg wird installiert..."
  INSTALLED=false
  if sudo -n true 2>/dev/null; then
    if command -v pacman &>/dev/null; then
      _run "ffmpeg (pacman)" sudo pacman -S --noconfirm ffmpeg && INSTALLED=true
    elif command -v apt-get &>/dev/null; then
      _run "apt update"    sudo apt-get update -qq
      _run "ffmpeg (apt)"  sudo apt-get install -y -qq ffmpeg && INSTALLED=true
    elif command -v dnf &>/dev/null; then
      _run "ffmpeg (dnf)"  sudo dnf install -y ffmpeg && INSTALLED=true
    fi
  fi
  if command -v brew &>/dev/null && ! $INSTALLED; then
    _run "ffmpeg (brew)" brew install ffmpeg && INSTALLED=true
  fi
  $INSTALLED && _ok "ffmpeg installiert" \
             || _warn "ffmpeg konnte nicht automatisch installiert werden — bitte nachinstallieren"
fi

_progress "ffmpeg ✓"

# ════════════════════════════════════════════════════════════
# STEP 4: VENV EINRICHTEN
# ════════════════════════════════════════════════════════════
_step "Umgebung vorbereiten"

VENV_DIR="$HOME/.whisperx-app/venv"
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"

if [ -d "$VENV_DIR" ]; then
  _info "Bestehende Umgebung gefunden — wird aktualisiert"
else
  _run "Virtuelle Umgebung erstellen" "$PYTHON" -m venv "$VENV_DIR"
fi
_run "pip upgraden"  "$VENV_DIR/bin/pip" install --upgrade pip --quiet

PIP="$VENV_DIR/bin/pip"

_progress "Umgebung ✓"

# ════════════════════════════════════════════════════════════
# STEP 5: ML-PAKETE INSTALLIEREN (alles direkt, kein Defer)
# ════════════════════════════════════════════════════════════
_step "ML-Abhängigkeiten installieren"
echo ""
printf "  ${C_GRAY}Das dauert ein paar Minuten — PyTorch + Whisper sind groß.${RESET}\n"
printf "  ${C_GRAY}Perfekter Zeitpunkt für einen Kaffee. ☕${RESET}\n"
echo ""

# PyTorch first (heaviest, resolves version constraints early)
_run "PyTorch installieren (~500 MB)"       "$PIP" install "torch>=2.0" --quiet
_run "torchaudio installieren"              "$PIP" install "torchaudio>=2.0" --quiet
_run "faster-whisper installieren"          "$PIP" install "faster-whisper>=1.0" --quiet
_run "whisperx installieren"                "$PIP" install "whisperx>=3.1" --quiet
_run "pyannote.audio installieren"          "$PIP" install "pyannote.audio>=3.1" --quiet
_run "librosa + soundfile installieren"     "$PIP" install "librosa>=0.10" "soundfile>=0.12" --quiet
_run "FastAPI + uvicorn installieren"       "$PIP" install "fastapi>=0.115" "uvicorn[standard]>=0.30" "python-multipart>=0.0.9" --quiet
_run "JWT + crypto installieren"            "$PIP" install "python-jose[cryptography]>=3.3" --quiet
_run "pydantic + utils installieren"        "$PIP" install "pydantic>=2.0" "pydantic-settings>=2.0" "aiofiles>=23.0" "httpx>=0.27" --quiet

_progress "ML-Pakete ✓"

# ════════════════════════════════════════════════════════════
# STEP 6: WHISPERX-APP INSTALLIEREN
# ════════════════════════════════════════════════════════════
_step "WhisperX-App installieren"

GITHUB_URL="git+https://github.com/Raindancer118/whisperx-app.git"

if "$VENV_DIR/bin/whisperx-app" --version &>/dev/null 2>&1; then
  _run "WhisperX-App aktualisieren" "$PIP" install --upgrade "$GITHUB_URL" --quiet
else
  _run "WhisperX-App installieren"  "$PIP" install "$GITHUB_URL" --quiet
fi

# Wrapper script in ~/.local/bin so it's globally available
WRAPPER="$LOCAL_BIN/whisperx-app"
printf '#!/usr/bin/env bash\nexec "%s/bin/whisperx-app" "$@"\n' "$VENV_DIR" > "$WRAPPER"
chmod +x "$WRAPPER"
_ensure_path "$LOCAL_BIN"
_ok "Wrapper: $WRAPPER"

_progress "WhisperX-App ✓"

# ════════════════════════════════════════════════════════════
# STEP 7: VERIFY
# ════════════════════════════════════════════════════════════
_step "Alles checken"

WXAPP="$LOCAL_BIN/whisperx-app"
[ -x "$WXAPP" ] || WXAPP="$VENV_DIR/bin/whisperx-app"

if [ -x "$WXAPP" ]; then
  VER=$("$WXAPP" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "?")
  _ok "${C_WHITE}${BOLD}whisperx-app $VER${RESET}  ${C_GRAY}→  $WXAPP${RESET}"
else
  _warn "Binary nicht gefunden — bitte Terminal neu starten"
fi

command -v ffprobe &>/dev/null && _ok "ffprobe verfügbar" || _warn "ffprobe fehlt"

PY_USED=$("$VENV_DIR/bin/python" --version 2>/dev/null || echo "?")
_ok "Python-Umgebung: $PY_USED  ${C_GRAY}($VENV_DIR)${RESET}"

_progress "Alles bereit  🎉"

# ════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════
W=$(_width); INNER=$((W - 4))
echo ""; echo ""
printf "${C_GRAY}  ╭"; printf '─%.0s' $(seq 1 $INNER); printf "╮${RESET}\n"
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_GREEN}${BOLD}✓ Alles installiert. Du bist ready. 🚀${RESET}%-$((INNER-42))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_WHITE}Starte jetzt:${RESET}%-$((INNER-15))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app${RESET}%-$((INNER-28))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Interaktiver Flow${RESET}"
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app transcribe audio.mp3${RESET}%-$((INNER-48))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Direkt loslegen${RESET}"
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app check${RESET}%-$((INNER-34))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Systemcheck${RESET}"
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app update${RESET}%-$((INNER-35))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Auf Updates prüfen${RESET}"
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${DIM}Beim ersten Start: HuggingFace-Token eingeben (für Sprecher-Erkennung)${RESET}%-$((INNER-71))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  ╰"; printf '─%.0s' $(seq 1 $INNER); printf "╯${RESET}\n"

if ! command -v whisperx-app &>/dev/null 2>&1; then
  echo ""
  printf "  ${C_YELLOW}${BOLD}Tipp:${RESET}${C_YELLOW} Neues Terminal öffnen oder: source ~/.zshrc / ~/.bashrc${RESET}\n"
fi

echo ""
printf "%b" "$SHOW_CURSOR"
