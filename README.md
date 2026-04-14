# WhisperX-App

CLI + REST API für schnelle Audio-Transkription mit genauer Sprecher-Diarisierung, powered by [WhisperX](https://github.com/m-bain/whisperX) und [pyannote.audio](https://github.com/pyannote/pyannote-audio).

## Features

- **Interaktive CLI** mit Drag & Drop Datei-Input
- **Automatische Modell-Installation** — fehlende Abhängigkeiten werden beim ersten Start angeboten
- **GPU-Erkennung** mit Zeitschätzung vor der Transkription
- **Sprecher-Diarisierung** (pyannote.audio) mit Sprecher-Namensmapping
- **3 Ausgabeformate**: TXT, JSON, Markdown (Sprecher **fett**)
- **REST API** (FastAPI) mit JWT-Auth via [Volantic Auth](https://accounts.volantic.de)
- **Uninstall-Option** die nur App-installierte Pakete entfernt

## Installation

### One-Line-Install (empfohlen)

```bash
curl -sSL https://raw.githubusercontent.com/Raindancer118/whisperx-app/main/install.sh | bash
```

Das Skript:
- prüft Python 3.10+
- installiert via **pipx** (global, sauber isoliert) oder fällt auf eine dedizierte venv zurück
- legt `whisperx-app` automatisch auf den PATH
- prüft ffmpeg und gibt Hinweise falls es fehlt

### Manuell (alternativ)

```bash
pipx install whisperx-app
# oder:
pip install whisperx-app
```

Beim ersten Start werden fehlende ML-Abhängigkeiten automatisch angeboten:

```bash
whisperx-app
# → Fehlende Abhängigkeiten gefunden. Jetzt installieren? [Y/n]
```

### Systemabhängigkeit: ffmpeg

```bash
sudo pacman -S ffmpeg      # Arch / Manjaro
sudo apt install ffmpeg    # Debian / Ubuntu
brew install ffmpeg        # macOS
```

## Verwendung

### Interaktiver Flow

```bash
whisperx-app
```

### Direkte Transkription

```bash
whisperx-app transcribe interview.mp3 --format md --output ergebnis.md
whisperx-app transcribe audio.wav --format txt --device cpu --no-diarize
```

### Konfiguration

```bash
whisperx-app config       # Interaktiver Konfigurations-Editor
whisperx-app check        # Systemcheck
whisperx-app deps         # Abhängigkeits-Status
```

### API-Server

```bash
whisperx-app api --port 8000
# → http://localhost:8000/docs
```

### Deinstallation der Abhängigkeiten

```bash
whisperx-app uninstall           # Entfernt nur App-installierte Pakete
whisperx-app uninstall --dry-run # Vorschau ohne Änderungen
```

## REST API

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|-------------|
| GET | `/health` | – | Status & verfügbare Modelle |
| POST | `/api/v1/transcribe` | Bearer JWT | Audio einreichen |
| GET | `/api/v1/jobs/{id}` | Bearer JWT | Status & Ergebnis |
| DELETE | `/api/v1/jobs/{id}` | Bearer JWT | Job abbrechen |

**Auth**: JWT Bearer Token von [Volantic Auth](https://accounts.volantic.de) (RS256, scope: `transcribe`)

## Konfiguration

Gespeichert in `~/.whisperx/config.json`:

```json
{
  "hf_token": "hf_...",
  "default_model": "large-v3",
  "default_device": "auto",
  "volantic_client_id": "whisperx-app"
}
```

## Markdown-Ausgabe (Beispiel)

```markdown
# Transkription: interview.mp3
**Erstellt:** 2026-04-14 · **Modell:** large-v3

**Tom** — 00:00:04
Hallo, willkommen zu unserem Interview.

**Anna** — 00:00:11
Danke für die Einladung!
```

## Tests

```bash
pip install -e ".[dev]"
pytest -m "not integration" --cov=whisperx_app
```

## Lizenz

MIT
