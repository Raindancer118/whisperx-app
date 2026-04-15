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

TOTAL_STEPS=10; CURRENT_STEP=0

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

# Progress bar (time-based): 0→90% while running, snaps to 100% on done.
# Usage: _run_bar LABEL EST_SECONDS cmd [args...]
# Returns exit code — does NOT call exit, so callers can handle failures.
_run_bar() {
  local label=$1 est=${2:-60}; shift 2
  rm -f /tmp/wx_install.log
  ("$@" &>/tmp/wx_install.log) &
  local pid=$! start elapsed pct w filled empty bf be
  start=$(date +%s)
  printf "%b" "$HIDE_CURSOR"
  while kill -0 "$pid" 2>/dev/null; do
    elapsed=$(( $(date +%s) - start ))
    pct=$(( elapsed * 90 / est )); [ "$pct" -gt 90 ] && pct=90
    w=$(( $(_width) - 20 )); [ "$w" -lt 10 ] && w=10
    filled=$(( pct * w / 100 )); empty=$(( w - filled ))
    bf=""; be=""
    [ "$filled" -gt 0 ] && bf=$(printf "%${filled}s" "" | tr ' ' '█')
    [ "$empty"  -gt 0 ] && be=$(printf "%${empty}s"  "" | tr ' ' '░')
    printf "  ${C_GRAY}[${C_GREEN}%s${C_GRAY}%s${C_GRAY}]${RESET} ${C_WHITE}%3d%%${RESET}  ${C_GRAY}%s${RESET}\r" \
      "$bf" "$be" "$pct" "$label"
    sleep 0.5
  done
  printf "%b" "$SHOW_CURSOR$CR"
  if wait "$pid"; then
    w=$(( $(_width) - 20 )); [ "$w" -lt 10 ] && w=10
    bf=$(printf "%${w}s" "" | tr ' ' '█')
    printf "  ${C_GRAY}[${C_GREEN}%s${C_GRAY}]${RESET} ${C_WHITE}100%%${RESET}  ${C_GRAY}%s${RESET}\n" "$bf" "$label"
    return 0
  else
    _err "$label fehlgeschlagen"
    cat /tmp/wx_install.log >&2
    return 1
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

# ── URL abfragen (vor allen Steps, Cursor muss sichtbar sein) ─────────────
printf "%b" "$SHOW_CURSOR"
echo ""
printf "  ${C_WHITE}${BOLD}Unter welcher URL soll die Web-App erreichbar sein?${RESET}\n"
printf "  ${C_GRAY}Beispiel: https://whisperx.meinedomain.de  oder  http://localhost${RESET}\n"
printf "  ${C_CYAN}URL${RESET} ${C_GRAY}[http://localhost]:${RESET} "
read -r INSTALL_APP_URL || true
INSTALL_APP_URL="${INSTALL_APP_URL:-http://localhost}"
echo ""
printf "  ${C_GREEN}✓${RESET}  ${C_GRAY}App-URL:${RESET} ${C_WHITE}${INSTALL_APP_URL}${RESET}\n"
printf "%b" "$HIDE_CURSOR"

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
# STEP 2: DOCKER
# ════════════════════════════════════════════════════════════
_step "Docker installieren"

if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  _ok "Docker $(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1) bereits installiert"
else
  _info "Docker wird installiert..."

  if command -v pacman &>/dev/null && sudo -n true 2>/dev/null; then
    _run_bar "Docker installieren (pacman)" 60 \
      sudo pacman -S --noconfirm docker docker-compose || exit 1

  elif command -v apt-get &>/dev/null && sudo -n true 2>/dev/null; then
    _run_bar "apt update" 20 sudo apt-get update -qq || true
    _run_bar "Docker installieren (apt)" 90 \
      sudo apt-get install -y docker.io docker-compose-plugin || exit 1

  elif command -v dnf &>/dev/null && sudo -n true 2>/dev/null; then
    _run_bar "Docker installieren (dnf)" 90 \
      sudo dnf install -y docker docker-compose-plugin || exit 1

  elif command -v brew &>/dev/null; then
    _run_bar "Docker installieren (brew)" 120 brew install --cask docker || exit 1

  else
    _die "Kein Paketmanager gefunden. Bitte Docker manuell installieren: https://docs.docker.com/get-docker/"
  fi

  # Docker-Dienst starten und aktivieren
  if command -v systemctl &>/dev/null; then
    sudo systemctl enable --now docker &>/dev/null || true
  fi

  # Nutzer zur docker-Gruppe hinzufügen (kein sudo für docker nötig)
  if id -nG "$USER" 2>/dev/null | grep -qv docker; then
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    _info "Nutzer zur docker-Gruppe hinzugefügt (gilt ab nächstem Login)"
  fi

  _ok "Docker installiert"
fi

_progress "Docker ✓"

# ════════════════════════════════════════════════════════════
# STEP 3: PYTHON (whisperx braucht 3.10–3.13, NICHT 3.14+)
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

  # ── uv: pre-built Python binary, no root/polkit needed ────────────────────
  # uv is the most reliable cross-platform method: downloads a pre-built
  # Python 3.11 binary in seconds, no compilation, no system privileges.
  UV_BIN=""
  if command -v uv &>/dev/null; then
    UV_BIN=$(command -v uv)
  else
    _info "uv installieren (Python-Versions-Manager)..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh >/tmp/wx_uv.log 2>&1; then
      # uv installs to ~/.local/bin or ~/.cargo/bin
      for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
        [ -x "$d/uv" ] && UV_BIN="$d/uv" && break
      done
      [ -n "$UV_BIN" ] && export PATH="$(dirname "$UV_BIN"):$PATH"
    fi
  fi

  if [ -n "$UV_BIN" ]; then
    _info "Python 3.11 via uv installieren (vorcompiliertes Binary, kein Root nötig)..."
    if _run_bar "Python 3.11 herunterladen" 60 "$UV_BIN" python install 3.11; then
      PYTHON=$("$UV_BIN" python find 3.11 2>/dev/null || true)
      if [ -n "$PYTHON" ] && [ -x "$PYTHON" ]; then
        PY_VER="3.11"
        _ok "Python 3.11 via uv  ${C_GRAY}($PYTHON)${RESET}"
        PY_INSTALLED=true
      fi
    fi
  fi

  # ── Fallback: Debian / Ubuntu ──────────────────────────────────────────────
  if ! $PY_INSTALLED && command -v apt-get &>/dev/null && sudo -n true 2>/dev/null; then
    _run_bar "apt update" 30 sudo apt-get update -qq || true
    _run_bar "Python 3.11 installieren (apt)" 60 \
      sudo apt-get install -y python3.11 python3.11-venv && PY_INSTALLED=true

  # ── Fallback: macOS (Homebrew) ─────────────────────────────────────────────
  elif ! $PY_INSTALLED && command -v brew &>/dev/null; then
    _run_bar "Python 3.11 installieren (brew)" 120 brew install python@3.11 && PY_INSTALLED=true
  fi

  if ! $PY_INSTALLED; then
    _err "Python 3.11–3.13 konnte nicht automatisch installiert werden."
    printf "\n  Bitte manuell installieren:\n"
    printf "    ${C_CYAN}sudo pamac install python311${RESET}   (Manjaro)\n"
    printf "    ${C_CYAN}sudo apt install python3.11${RESET}    (Ubuntu/Debian)\n"
    printf "    ${C_CYAN}brew install python@3.11${RESET}       (macOS)\n\n"
    exit 1
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
  _run_bar "Virtuelle Umgebung erstellen" 20 "$PYTHON" -m venv "$VENV_DIR" || exit 1
fi
_run_bar "pip upgraden" 30 "$VENV_DIR/bin/pip" install --upgrade pip --quiet || exit 1

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
_run_bar "PyTorch installieren (~500 MB)"   300  "$PIP" install "torch>=2.0" --quiet            || exit 1
_run_bar "torchaudio installieren"          120  "$PIP" install "torchaudio>=2.0" --quiet       || exit 1
_run_bar "faster-whisper installieren"       60  "$PIP" install "faster-whisper>=1.0" --quiet   || exit 1
_run_bar "whisperx installieren"            120  "$PIP" install "whisperx>=3.1" --quiet         || exit 1
_run_bar "pyannote.audio installieren"      180  "$PIP" install "pyannote.audio>=3.1" --quiet   || exit 1
_run_bar "librosa + soundfile installieren"  60  "$PIP" install "librosa>=0.10" "soundfile>=0.12" --quiet || exit 1
_run_bar "FastAPI + uvicorn installieren"    60  "$PIP" install "fastapi>=0.115" "uvicorn[standard]>=0.30" "python-multipart>=0.0.9" --quiet || exit 1
_run_bar "JWT + crypto installieren"         40  "$PIP" install "python-jose[cryptography]>=3.3" --quiet || exit 1
_run_bar "pydantic + utils installieren"     60  "$PIP" install "pydantic>=2.0" "pydantic-settings>=2.0" "aiofiles>=23.0" "httpx>=0.27" --quiet || exit 1

_progress "ML-Pakete ✓"

# ════════════════════════════════════════════════════════════
# STEP 6: WHISPERX-APP INSTALLIEREN
# ════════════════════════════════════════════════════════════
_step "WhisperX-App installieren"

GITHUB_URL="git+https://github.com/Raindancer118/whisperx-app.git"

if "$VENV_DIR/bin/whisperx-app" --version &>/dev/null 2>&1; then
  _run_bar "WhisperX-App aktualisieren" 60 "$PIP" install --upgrade "$GITHUB_URL" --quiet || exit 1
else
  _run_bar "WhisperX-App installieren"  60 "$PIP" install "$GITHUB_URL" --quiet || exit 1
fi

# Wrapper script in ~/.local/bin so it's globally available
WRAPPER="$LOCAL_BIN/whisperx-app"
printf '#!/usr/bin/env bash\nexec "%s/bin/whisperx-app" "$@"\n' "$VENV_DIR" > "$WRAPPER"
chmod +x "$WRAPPER"
_ensure_path "$LOCAL_BIN"
_ok "Wrapper: $WRAPPER"

_progress "WhisperX-App ✓"

# ════════════════════════════════════════════════════════════
# STEP 7: KONFIGURATION
# ════════════════════════════════════════════════════════════
_step "Konfiguration"
printf "%b" "$SHOW_CURSOR"  # cursor on for password input

_gen_hex()  { python3 -c "import secrets; print(secrets.token_hex($1))" 2>/dev/null \
              || openssl rand -hex "$1" 2>/dev/null || echo "change-me-$(date +%s)"; }
_gen_safe() { python3 -c "import secrets; print(secrets.token_urlsafe($1))" 2>/dev/null \
              || openssl rand -base64 "$1" 2>/dev/null | tr -d '=\n'; }

# ── HuggingFace Token ─────────────────────────────────────────────────────
HF_TOKEN=""
HF_CFG="$HOME/.whisperx/config.json"

# Check if already configured
if [ -f "$HF_CFG" ]; then
  existing_token=$(python3 -c "import json; d=json.load(open('$HF_CFG')); print(d.get('hf_token') or '')" 2>/dev/null || true)
  if [ -n "$existing_token" ] && [ "$existing_token" != "null" ]; then
    HF_TOKEN="$existing_token"
    _ok "HuggingFace-Token bereits konfiguriert"
  fi
fi

if [ -z "$HF_TOKEN" ]; then
  echo ""
  printf "  ${C_WHITE}${BOLD}HuggingFace-Token${RESET} ${C_GRAY}(für Sprecher-Diarisierung)${RESET}\n"
  printf "  ${C_GRAY}Token erstellen: https://hf.co/settings/tokens${RESET}\n"
  printf "  ${C_GRAY}Nutzungsbed.:   https://hf.co/pyannote/speaker-diarization-3.1${RESET}\n"
  echo ""
  printf "  ${C_CYAN}HF_TOKEN${RESET} ${C_GRAY}(Enter zum Überspringen):${RESET} "
  read -rs HF_TOKEN || true
  echo ""
  if [ -n "$HF_TOKEN" ]; then
    mkdir -p "$HOME/.whisperx"
    if [ -f "$HF_CFG" ]; then
      python3 -c "
import json, sys
with open('$HF_CFG') as f: d = json.load(f)
d['hf_token'] = '$HF_TOKEN'
with open('$HF_CFG', 'w') as f: json.dump(d, f, indent=2)
" 2>/dev/null && _ok "HF_TOKEN in ~/.whisperx/config.json gespeichert"
    else
      echo "{\"hf_token\": \"$HF_TOKEN\"}" > "$HF_CFG"
      _ok "HF_TOKEN gespeichert"
    fi
  else
    _warn "Übersprungen — Sprecher-Diarisierung nicht verfügbar bis Token gesetzt"
  fi
fi

# ── Secrets generieren (werden in Step 10 für .env genutzt) ──────────────
SESSION_SECRET_VAL=$(_gen_hex 32)
POSTGRES_PASSWORD_VAL=$(_gen_safe 24)
_ok "SESSION_SECRET generiert"
_ok "POSTGRES_PASSWORD generiert"

printf "%b" "$HIDE_CURSOR"
_progress "Konfiguration ✓"

# ════════════════════════════════════════════════════════════
# STEP 8: VERIFY
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
# STEP 10: WEB-APP STARTEN (Repo + Docker)
# ════════════════════════════════════════════════════════════
_step "Web-App starten"

APP_DIR="$HOME/.whisperx-app/app"
REPO_URL="https://github.com/Raindancer118/whisperx-app.git"

# ── git installieren falls nötig ──────────────────────────────────────────
if ! command -v git &>/dev/null; then
  _info "git wird benötigt..."
  if command -v pacman &>/dev/null && sudo -n true 2>/dev/null; then
    _run "git installieren (pacman)" sudo pacman -S --noconfirm git
  elif command -v apt-get &>/dev/null && sudo -n true 2>/dev/null; then
    _run "git installieren (apt)" sudo apt-get install -y git
  elif command -v brew &>/dev/null; then
    _run "git installieren (brew)" brew install git
  else
    _die "git nicht gefunden und konnte nicht installiert werden."
  fi
fi

# ── Repo klonen oder aktualisieren ────────────────────────────────────────
mkdir -p "$(dirname "$APP_DIR")"
if [ -d "$APP_DIR/.git" ]; then
  _run_bar "Repository aktualisieren" 20 git -C "$APP_DIR" pull --quiet || true
  _ok "Repository aktualisiert"
else
  _run_bar "Repository klonen" 40 git clone "$REPO_URL" "$APP_DIR" --quiet || exit 1
  _ok "Repository geklont: $APP_DIR"
fi

# ── .env schreiben ────────────────────────────────────────────────────────
cat > "$APP_DIR/.env" <<ENVEOF
APP_URL=${INSTALL_APP_URL}
VOLANTIC_CLIENT_ID=whisperx-app
SESSION_SECRET=${SESSION_SECRET_VAL}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD_VAL}
SMTP_PASSWORD=ahxL!f5RTvquxO*Q3br^Srb!wra8exu^fv96bJEMQkNfwd^N3#
HF_TOKEN=${HF_TOKEN}
ENVEOF
_ok ".env geschrieben → $APP_DIR/.env"

# ── Container bauen + starten ─────────────────────────────────────────────
echo ""
printf "  ${C_GRAY}Erster Start: CUDA-Image + Node-Build — das dauert ein paar Minuten.${RESET}\n"
printf "  ${C_GRAY}Lehn dich zurück. ☕${RESET}\n"
echo ""

# docker compose: direkter Aufruf, sudo-Fallback, sg-Fallback
_docker_compose_up() {
  cd "$APP_DIR" || return 1
  if docker info >/dev/null 2>&1; then
    docker compose up -d --build
  elif sudo -n docker info >/dev/null 2>&1; then
    sudo docker compose up -d --build
  elif command -v sg >/dev/null 2>&1; then
    sg docker "cd '$APP_DIR' && docker compose up -d --build"
  else
    echo "Docker nicht erreichbar — bitte Terminal neu starten (docker-Gruppe)" >&2
    return 1
  fi
}

_run_bar "Container bauen + starten" 600 bash -c "
  cd '$APP_DIR' || exit 1
  if docker info >/dev/null 2>&1; then
    docker compose up -d --build
  elif sudo -n docker info >/dev/null 2>&1; then
    sudo docker compose up -d --build
  elif command -v sg >/dev/null 2>&1; then
    sg docker \"cd '$APP_DIR' && docker compose up -d --build\"
  else
    echo 'Docker nicht erreichbar — bitte Terminal neu starten (docker-Gruppe)' >&2
    exit 1
  fi
" || {
  _err "Container-Start fehlgeschlagen — Details:"
  cat /tmp/wx_install.log >&2
  _warn "Tipp: Terminal neu starten (docker-Gruppe) und dann:"
  printf "    ${C_CYAN}cd %s && docker compose up -d --build${RESET}\n" "$APP_DIR"
  exit 1
}

# ── Container-Status anzeigen ─────────────────────────────────────────────
echo ""
_info "Laufende Container:"
( cd "$APP_DIR" 2>/dev/null && docker compose ps 2>/dev/null ) | tail -n +2 | while IFS= read -r line; do
  printf "    ${C_GRAY}%s${RESET}\n" "$line"
done

echo ""
_ok "${C_WHITE}${BOLD}Web-App erreichbar:${RESET}  ${C_CYAN}${BOLD}${INSTALL_APP_URL}${RESET}"
_progress "Web-App ✓ — läuft!"

# ════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════
W=$(_width); INNER=$((W - 4))
echo ""; echo ""
printf "${C_GRAY}  ╭"; printf '─%.0s' $(seq 1 $INNER); printf "╮${RESET}\n"
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_GREEN}${BOLD}✓ Alles installiert und gestartet. 🚀${RESET}%-$((INNER-40))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_WHITE}Web-App:${RESET}  ${C_CYAN}${BOLD}${INSTALL_APP_URL}${RESET}%-$((INNER - 12 - ${#INSTALL_APP_URL}))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_WHITE}CLI-Befehle:${RESET}%-$((INNER-14))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app${RESET}%-$((INNER-28))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Interaktiver Flow${RESET}"
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app transcribe audio.mp3${RESET}%-$((INNER-48))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Direkt loslegen${RESET}"
printf "${C_GRAY}  │${RESET}    ${C_CYAN}whisperx-app check${RESET}%-$((INNER-34))s${C_GRAY}│${RESET}\n" "  ${C_GRAY}→ Systemcheck${RESET}"
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  ╰"; printf '─%.0s' $(seq 1 $INNER); printf "╯${RESET}\n"

if ! command -v whisperx-app &>/dev/null 2>&1; then
  echo ""
  printf "  ${C_YELLOW}${BOLD}Tipp:${RESET}${C_YELLOW} Neues Terminal öffnen oder: source ~/.zshrc / ~/.bashrc${RESET}\n"
fi

echo ""
printf "%b" "$SHOW_CURSOR"
