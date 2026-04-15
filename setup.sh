#!/usr/bin/env bash
# ============================================================
#  whisperx-app — setup.sh
#  Generiert eine .env mit sicheren Zufallswerten.
#  Vorhandene Werte (z.B. HF_TOKEN, SMTP_PASSWORD) bleiben erhalten.
# ============================================================
set -euo pipefail

ENV_FILE="$(dirname "$0")/.env"

# Hilfsfunktionen
_has() { grep -q "^${1}=" "$ENV_FILE" 2>/dev/null; }
_set() { echo "${1}=${2}" >> "$ENV_FILE"; }
_gen_hex()  { python3 -c "import secrets; print(secrets.token_hex($1))"; }
_gen_safe() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }

echo ""
echo "  whisperx-app — Setup"
echo "  ─────────────────────────────"

# .env anlegen falls nicht vorhanden
[ -f "$ENV_FILE" ] || touch "$ENV_FILE"

# APP_URL
if ! _has APP_URL; then
  read -rp "  APP_URL [http://localhost]: " app_url
  _set APP_URL "${app_url:-http://localhost}"
  echo "  ✓ APP_URL gesetzt"
fi

# VOLANTIC_CLIENT_ID
_has VOLANTIC_CLIENT_ID || _set VOLANTIC_CLIENT_ID "whisperx-app"

# SESSION_SECRET — immer neu generieren wenn nicht vorhanden
if ! _has SESSION_SECRET; then
  _set SESSION_SECRET "$(_gen_hex 32)"
  echo "  ✓ SESSION_SECRET generiert"
fi

# POSTGRES_PASSWORD
if ! _has POSTGRES_PASSWORD; then
  _set POSTGRES_PASSWORD "$(_gen_safe 24)"
  echo "  ✓ POSTGRES_PASSWORD generiert"
fi

# SMTP_PASSWORD — manuell
if ! _has SMTP_PASSWORD; then
  read -rsp "  SMTP-Passwort (noreply@volantic.de): " smtp_pw
  echo ""
  _set SMTP_PASSWORD "$smtp_pw"
  echo "  ✓ SMTP_PASSWORD gesetzt"
fi

# HF_TOKEN — manuell
if ! _has HF_TOKEN; then
  echo ""
  echo "  HuggingFace Token nötig (https://hf.co/settings/tokens)"
  echo "  Nutzungsbedingungen akzeptieren: https://hf.co/pyannote/speaker-diarization-3.1"
  read -rsp "  HF_TOKEN: " hf_token
  echo ""
  _set HF_TOKEN "$hf_token"
  echo "  ✓ HF_TOKEN gesetzt"
fi

echo ""
echo "  ✓ .env fertig — starte mit: docker compose up -d"
echo ""
