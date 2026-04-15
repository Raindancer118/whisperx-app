# WhisperX Frontend — Design-Dokumentation

## Stack
- React 18 + TypeScript + Vite
- Tailwind CSS (utility-first)
- React Router v6 (SPA routing)
- react-dropzone (drag & drop upload)
- react-markdown (transcript rendering)

## Design-Sprache
- **Stil**: Clean & Light (Stripe/Notion-Ästhetik)
- **Primary**: `#0F1F3D` (Volantic Navy)
- **Accent**: `#2563EB` (Volantic Blue)
- **Background**: `#F8FAFC` (slate-50)
- **Fonts**: Rajdhani (Display/Überschriften), Inter (Body)
- **Border-Radius**: `rounded-xl` / `rounded-2xl` für Cards
- **Schatten**: Dezent (`shadow-sm`, kein hartes `shadow-md`)

## Seitenstruktur

| Route | Seite | Beschreibung |
|-------|-------|-------------|
| `/` | Login | Volantic SSO Login-Card |
| `/dashboard` | Dashboard | Alle Jobs des eingeloggten Nutzers |
| `/upload` | Upload Wizard | 4-stufiger Wizard: Datei → Optionen → E-Mail → Upload |
| `/results/:jobId` | Ergebnis | Transkript mit Download-Buttons |

## Komponenten

- `Logo` — Volantic Wortmarke (navy + accent dot)
- `Button` — primary / secondary / ghost / danger, mit Loading-State
- `Badge` — Job-Status-Badge mit Farbe + animiertem Punkt
- `Layout` — Top-Nav mit Logo, Nutzerinfo, Abmelden
- `StepIndicator` — Wizard-Fortschrittsanzeige

## Upload (Chunked)

Dateien werden in **10 MB Blöcken** hochgeladen:
1. Job-Record wird per `POST /api/web/jobs` angelegt
2. Jeder Chunk per `POST /api/web/jobs/:id/chunks/:index`
3. Bei Netzwerkfehler: 3 Versuche mit Exponential-Backoff
4. Nach letztem Chunk: Server assembliert und startet Celery-Task

Große Dateien (3 GB+) funktionieren ohne Timeout, da nginx kein Request-Buffering macht (`proxy_request_buffering off`).

## Auth Flow

```
User → GET /auth/login
     → Redirect: accounts.volantic.de/oauth/authorize (PKCE)
     → User loggt sich ein
     → Redirect: /auth/callback?code=...
     → Backend tauscht Code gegen Token
     → Setzt httpOnly Cookie `wx_session`
     → Redirect: /dashboard
```

## Lokale Entwicklung

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxied to :8000)
```

```bash
# Backend separat
uvicorn whisperx_app.api.main:create_app --factory --reload
```
