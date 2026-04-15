#!/usr/bin/env bash
# ============================================================
#  WhisperX-App — Uninstaller
#  curl -sSL https://raw.githubusercontent.com/Raindancer118/whisperx-app/main/uninstall.sh | bash
# ============================================================
set -euo pipefail
IFS=$'\n\t'

# ── Terminal colours ─────────────────────────────────────────
if [ -t 1 ]; then
  BOLD="\033[1m"; RESET="\033[0m"
  C_CYAN="\033[38;5;87m";   C_GREEN="\033[38;5;84m"
  C_YELLOW="\033[38;5;220m"; C_RED="\033[38;5;203m";  C_WHITE="\033[38;5;255m"
  C_GRAY="\033[38;5;244m";   C_PURPLE="\033[38;5;141m"
  HIDE_CURSOR="\033[?25l"; SHOW_CURSOR="\033[?25h"
  CR="\033[2K\r"
else
  BOLD=""; RESET=""
  C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_WHITE=""; C_GRAY=""; C_PURPLE=""
  HIDE_CURSOR=""; SHOW_CURSOR=""; CR=""
fi

trap 'printf "%b" "${SHOW_CURSOR}${RESET}"; echo ""' EXIT INT TERM

_width()  { tput cols 2>/dev/null || echo 72; }
_line()   { local w; w=$(_width); printf "${C_GRAY}  "; printf '─%.0s' $(seq 1 $((w-4))); printf "${RESET}\n"; }
_ok()     { printf "  ${C_GREEN}✓${RESET}  %b\n" "$*"; }
_skip()   { printf "  ${C_GRAY}–${RESET}  %b\n" "$*"; }
_warn()   { printf "  ${C_YELLOW}!${RESET}  %b\n" "$*"; }
_err()    { printf "  ${C_RED}✗${RESET}  %b\n" "$*" >&2; }

# Spinner while background command runs (never exits — just warns on failure)
_run() {
  local label=$1; shift
  local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
  local i=0
  rm -f /tmp/wx_uninstall.log
  ("$@" &>/tmp/wx_uninstall.log) &
  local pid=$!
  printf "%b" "$HIDE_CURSOR"
  while kill -0 "$pid" 2>/dev/null; do
    printf "  ${C_CYAN}${frames[$((i % 10))]}${RESET}  ${C_GRAY}%s${RESET}   \r" "$label"
    sleep 0.08; i=$(( i + 1 ))
  done
  printf "%b" "${SHOW_CURSOR}${CR}"
  if wait "$pid"; then
    _ok "$label"
  else
    _warn "$label — teilweise fehlgeschlagen (Details: /tmp/wx_uninstall.log)"
  fi
}

# y/N prompt  —  usage: _ask "Frage" && do_it
_ask() {
  local question=$1 default=${2:-N}
  local hint
  [ "$default" = "J" ] && hint="${C_WHITE}[J/n]${RESET}" || hint="${C_GRAY}[j/N]${RESET}"
  printf "  ${C_CYAN}?${RESET}  %b  %b: " "$question" "$hint"
  read -r ans || ans=""
  echo ""
  case "${ans:-$default}" in
    [jJyY]*) return 0 ;;
    *)       return 1 ;;
  esac
}

# Disk size of a path (human-readable)
_size() { du -sh "$1" 2>/dev/null | cut -f1 || echo "?"; }

# docker: use sudo if needed
_dc() {
  local dir=$1; shift
  if docker info >/dev/null 2>&1; then
    ( cd "$dir" && docker "$@" )
  elif sudo -n docker info >/dev/null 2>&1; then
    ( cd "$dir" && sudo docker "$@" )
  else
    return 1
  fi
}

# ════════════════════════════════════════════════════════════
# BANNER
# ════════════════════════════════════════════════════════════
clear 2>/dev/null || true
printf "%b" "$HIDE_CURSOR"

printf "${C_RED}${BOLD}"
echo "  ██╗    ██╗██╗  ██╗██╗███████╗██████╗ ███████╗██████╗     ██╗  ██╗"
echo "  ██║    ██║██║  ██║██║██╔════╝██╔══██╗██╔════╝██╔══██╗    ╚██╗██╔╝"
echo "  ██║ █╗ ██║███████║██║███████╗██████╔╝█████╗  ██████╔╝     ╚███╔╝ "
echo "  ██║███╗██║██╔══██║██║╚════██║██╔═══╝ ██╔══╝  ██╔══██╗     ██╔██╗ "
echo "  ╚███╔███╔╝██║  ██║██║███████║██║     ███████╗██║  ██║    ██╔╝ ██╗"
echo "   ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝"
printf "${RESET}"
echo ""
printf "  ${C_GRAY}Deinstallation — wähle, was entfernt werden soll${RESET}\n"
echo ""
_line
echo ""

# ════════════════════════════════════════════════════════════
# INTERAKTIVE AUSWAHL
# ════════════════════════════════════════════════════════════
printf "%b" "$SHOW_CURSOR"

APP_DIR="$HOME/.whisperx-app/app"
VENV_DIR="$HOME/.whisperx-app/venv"
WRAPPER="$HOME/.local/bin/whisperx-app"
HF_CACHE="$HOME/.cache/huggingface"
WX_CFG="$HOME/.whisperx"

# ── Zusammenfassung der gefundenen Komponenten ────────────────────────────
printf "  ${C_WHITE}${BOLD}Gefundene Komponenten:${RESET}\n"
echo ""

HAS_CONTAINERS=false
HAS_DOCKER_VOLUMES=false
if command -v docker &>/dev/null && [ -d "$APP_DIR" ]; then
  if docker compose -f "$APP_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
    HAS_CONTAINERS=true
  fi
  # Check if any whisperx-app volumes exist
  if docker volume ls --format '{{.Name}}' 2>/dev/null | grep -q "whisperx"; then
    HAS_DOCKER_VOLUMES=true
    UPLOADS_SZ=$(docker volume inspect whisperx-app_uploads 2>/dev/null \
      | python3 -c "import json,sys,subprocess; d=json.load(sys.stdin); mp=d[0]['Mountpoint']; print(subprocess.check_output(['sudo','du','-sh',mp],stderr=subprocess.DEVNULL).decode().split()[0])" 2>/dev/null || echo "?")
    RESULTS_SZ=$(docker volume inspect whisperx-app_results 2>/dev/null \
      | python3 -c "import json,sys,subprocess; d=json.load(sys.stdin); mp=d[0]['Mountpoint']; print(subprocess.check_output(['sudo','du','-sh',mp],stderr=subprocess.DEVNULL).decode().split()[0])" 2>/dev/null || echo "?")
  fi
fi

[ -d "$APP_DIR" ]  && printf "  ${C_GRAY}  App-Verzeichnis   ~/.whisperx-app/app       (%s)${RESET}\n" "$(_size "$APP_DIR")"   || true
[ -d "$VENV_DIR" ] && printf "  ${C_GRAY}  Python-Umgebung   ~/.whisperx-app/venv      (%s)${RESET}\n" "$(_size "$VENV_DIR")"  || true
[ -f "$WRAPPER" ]  && printf "  ${C_GRAY}  Wrapper           ~/.local/bin/whisperx-app${RESET}\n"                               || true
$HAS_DOCKER_VOLUMES && printf "  ${C_GRAY}  Docker-Volumes    uploads (%s), results (%s)${RESET}\n" "${UPLOADS_SZ:-?}" "${RESULTS_SZ:-?}" || true
[ -d "$HF_CACHE" ] && printf "  ${C_YELLOW}  HF-Modell-Cache   ~/.cache/huggingface/     (%s)${RESET}\n" "$(_size "$HF_CACHE")" || true
[ -d "$WX_CFG" ]   && printf "  ${C_GRAY}  Konfiguration     ~/.whisperx/              (%s)${RESET}\n" "$(_size "$WX_CFG")"   || true
echo ""
_line
echo ""

# ── Auswahl ───────────────────────────────────────────────────────────────
printf "  ${C_WHITE}${BOLD}Was soll entfernt werden?${RESET}\n"
echo ""

RM_DOCKER=false
RM_VOLUMES=false
RM_APP=false
RM_VENV=false
RM_MODELS=false
RM_CFG=false

# Docker-Container + Images
if command -v docker &>/dev/null && { [ -d "$APP_DIR" ] || $HAS_DOCKER_VOLUMES; }; then
  _ask "Docker-Container und Images stoppen und entfernen?" "J" && RM_DOCKER=true || true
  if $HAS_DOCKER_VOLUMES; then
    _ask "${C_YELLOW}${BOLD}Uploads und Ergebnisse löschen?${RESET} (Docker-Volumes — ${C_RED}unwiderruflich${RESET})" "N" && RM_VOLUMES=true || true
  fi
fi

# App + venv
if [ -d "$HOME/.whisperx-app" ]; then
  _ask "App-Verzeichnis + Python-Umgebung entfernen? (~/.whisperx-app/)" "J" && RM_APP=true && RM_VENV=true || true
fi

# HuggingFace Modell-Cache
if [ -d "$HF_CACHE" ]; then
  HF_SZ=$(_size "$HF_CACHE")
  _ask "${C_YELLOW}HuggingFace-Modell-Cache entfernen? (~/.cache/huggingface/, ${HF_SZ})${RESET}  ${C_GRAY}(andere Apps nutzen diesen evtl. auch)${RESET}" "N" && RM_MODELS=true || true
fi

# Konfiguration / HF-Token
if [ -d "$WX_CFG" ]; then
  _ask "Konfiguration entfernen? (~/.whisperx/ — enthält HF-Token)" "N" && RM_CFG=true || true
fi

echo ""

# ── Wenn nichts ausgewählt ────────────────────────────────────────────────
if ! $RM_DOCKER && ! $RM_VOLUMES && ! $RM_APP && ! $RM_MODELS && ! $RM_CFG; then
  printf "  ${C_GREEN}Nichts ausgewählt. Abgebrochen.${RESET}\n\n"
  printf "%b" "$SHOW_CURSOR"
  exit 0
fi

# ── Letzte Bestätigung ────────────────────────────────────────────────────
_line
echo ""
printf "  ${C_RED}${BOLD}Diese Aktion kann nicht rückgängig gemacht werden.${RESET}\n"
printf "  ${C_WHITE}Wirklich fortfahren? ${RESET}${C_GRAY}Tippe  ${C_WHITE}ja${C_GRAY}  zum Bestätigen:${RESET} "
read -r confirm || true
echo ""

case "$confirm" in
  ja|JA|Ja) : ;;
  *)
    printf "  ${C_GREEN}Abgebrochen. Nichts wurde geändert.${RESET}\n\n"
    printf "%b" "$SHOW_CURSOR"
    exit 0
    ;;
esac

printf "%b" "$HIDE_CURSOR"
echo ""
_line
echo ""

STEP=0
TOTAL=0
$RM_DOCKER  && TOTAL=$((TOTAL+1))
$RM_VOLUMES && TOTAL=$((TOTAL+1))
$RM_APP     && TOTAL=$((TOTAL+1))
$RM_MODELS  && TOTAL=$((TOTAL+1))
$RM_CFG     && TOTAL=$((TOTAL+1))
TOTAL=$((TOTAL+1))  # wrapper + PATH immer

# ════════════════════════════════════════════════════════════
# DOCKER CONTAINER + IMAGES
# ════════════════════════════════════════════════════════════
if $RM_DOCKER; then
  STEP=$((STEP+1))
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}Docker-Container und Images${RESET}\n" "$STEP" "$TOTAL"
  _line

  if [ -d "$APP_DIR" ]; then
    if $RM_VOLUMES; then
      _run "Container + Volumes stoppen und entfernen" bash -c "
        cd '$APP_DIR'
        if docker info >/dev/null 2>&1; then
          docker compose down --volumes --remove-orphans
        elif sudo -n docker info >/dev/null 2>&1; then
          sudo docker compose down --volumes --remove-orphans
        fi
      "
    else
      _run "Container stoppen und entfernen" bash -c "
        cd '$APP_DIR'
        if docker info >/dev/null 2>&1; then
          docker compose down --remove-orphans
        elif sudo -n docker info >/dev/null 2>&1; then
          sudo docker compose down --remove-orphans
        fi
      "
    fi
  fi

  # Built images entfernen (compose benennt sie project_service)
  _run "Images entfernen" bash -c "
    remove_img() {
      if docker info >/dev/null 2>&1; then
        docker image rm \"\$1\" 2>/dev/null || true
      elif sudo -n docker info >/dev/null 2>&1; then
        sudo docker image rm \"\$1\" 2>/dev/null || true
      fi
    }
    for suffix in nginx api worker; do
      remove_img \"whisperx-app-\${suffix}\"
      remove_img \"whisperx_app-\${suffix}\"
      remove_img \"app-\${suffix}\"
    done
    # Dangling images aufräumen
    if docker info >/dev/null 2>&1; then
      docker image prune -f 2>/dev/null || true
    elif sudo -n docker info >/dev/null 2>&1; then
      sudo docker image prune -f 2>/dev/null || true
    fi
  "
  echo ""
fi

# ════════════════════════════════════════════════════════════
# DOCKER VOLUMES (nur wenn explizit bestätigt)
# ════════════════════════════════════════════════════════════
if $RM_VOLUMES && ! $RM_DOCKER; then
  # Wenn Docker-Container nicht über compose down entfernt wurden, Volumes direkt löschen
  STEP=$((STEP+1))
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}Docker-Volumes (Uploads + Ergebnisse)${RESET}\n" "$STEP" "$TOTAL"
  _line

  _run "Docker-Volumes entfernen" bash -c "
    for vol in whisperx-app_uploads whisperx-app_results whisperx-app_pgdata whisperx-app_redisdata whisperx-app_model_cache; do
      if docker info >/dev/null 2>&1; then
        docker volume rm \"\$vol\" 2>/dev/null || true
      elif sudo -n docker info >/dev/null 2>&1; then
        sudo docker volume rm \"\$vol\" 2>/dev/null || true
      fi
    done
  "
  echo ""
fi

# ════════════════════════════════════════════════════════════
# APP-VERZEICHNIS + VENV
# ════════════════════════════════════════════════════════════
if $RM_APP; then
  STEP=$((STEP+1))
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}App-Verzeichnis + Python-Umgebung${RESET}\n" "$STEP" "$TOTAL"
  _line

  if [ -d "$HOME/.whisperx-app" ]; then
    _run "~/.whisperx-app/ entfernen" rm -rf "$HOME/.whisperx-app"
  else
    _skip "~/.whisperx-app/ nicht gefunden"
  fi
  echo ""
fi

# ════════════════════════════════════════════════════════════
# HUGGINGFACE MODELL-CACHE
# ════════════════════════════════════════════════════════════
if $RM_MODELS; then
  STEP=$((STEP+1))
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}HuggingFace-Modell-Cache${RESET}\n" "$STEP" "$TOTAL"
  _line

  if [ -d "$HF_CACHE" ]; then
    _run "~/.cache/huggingface/ entfernen" rm -rf "$HF_CACHE"
  else
    _skip "~/.cache/huggingface/ nicht gefunden"
  fi
  echo ""
fi

# ════════════════════════════════════════════════════════════
# KONFIGURATION
# ════════════════════════════════════════════════════════════
if $RM_CFG; then
  STEP=$((STEP+1))
  printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}Konfiguration${RESET}\n" "$STEP" "$TOTAL"
  _line

  if [ -d "$WX_CFG" ]; then
    _run "~/.whisperx/ entfernen" rm -rf "$WX_CFG"
  else
    _skip "~/.whisperx/ nicht gefunden"
  fi
  echo ""
fi

# ════════════════════════════════════════════════════════════
# WRAPPER + PATH (immer)
# ════════════════════════════════════════════════════════════
STEP=$((STEP+1))
printf "  ${C_PURPLE}${BOLD}[ %d / %d ]${RESET}  ${C_WHITE}${BOLD}Wrapper und PATH-Einträge${RESET}\n" "$STEP" "$TOTAL"
_line

if [ -f "$WRAPPER" ]; then
  rm -f "$WRAPPER"
  _ok "Wrapper entfernt: $WRAPPER"
else
  _skip "Wrapper nicht gefunden"
fi

for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.profile"; do
  if [ -f "$rc" ] && grep -q "whisperx-app" "$rc" 2>/dev/null; then
    sed -i '/# Added by whisperx-app installer/d' "$rc" 2>/dev/null || true
    sed -i '/whisperx-app.*PATH/d'                "$rc" 2>/dev/null || true
    sed -i '/\.whisperx-app/d'                    "$rc" 2>/dev/null || true
    _ok "PATH-Eintrag entfernt aus $(basename "$rc")"
  fi
done

echo ""

# ════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════
W=$(_width); INNER=$((W - 4))
echo ""
printf "${C_GRAY}  ╭"; printf '─%.0s' $(seq 1 $INNER); printf "╮${RESET}\n"
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}  ${C_GREEN}${BOLD}✓ WhisperX-App entfernt.${RESET}%-$((INNER-26))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
if ! $RM_CFG; then
  printf "${C_GRAY}  │${RESET}  ${C_GRAY}HF-Token bleibt erhalten in ~/.whisperx/config.json${RESET}%-$((INNER-53))s${C_GRAY}│${RESET}\n" ""
  printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
fi
if ! $RM_MODELS && [ -d "$HF_CACHE" ]; then
  printf "${C_GRAY}  │${RESET}  ${C_GRAY}Modell-Cache bleibt erhalten in ~/.cache/huggingface/${RESET}%-$((INNER-54))s${C_GRAY}│${RESET}\n" ""
  printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
fi
printf "${C_GRAY}  │${RESET}  ${C_GRAY}Neues Terminal öffnen, um PATH-Änderungen zu übernehmen.${RESET}%-$((INNER-57))s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  │${RESET}%-${INNER}s${C_GRAY}│${RESET}\n" ""
printf "${C_GRAY}  ╰"; printf '─%.0s' $(seq 1 $INNER); printf "╯${RESET}\n"
echo ""
printf "%b" "$SHOW_CURSOR"
