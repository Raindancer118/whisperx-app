"""Async email sending via SMTP (mx.volantic.de)."""

from __future__ import annotations

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

SMTP_HOST = os.environ.get("SMTP_HOST", "mx.volantic.de")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "noreply@volantic.de")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_NAME = "WhisperX"
APP_URL = os.environ.get("APP_URL", "http://localhost")


async def send_transcription_done(
    to_email: str,
    filename: str,
    job_id: str,
    output_format: str,
) -> None:
    """Send a 'transcription ready' email."""
    results_url = f"{APP_URL}/results/{job_id}"
    fmt_label = {"md": "Markdown", "txt": "Text", "json": "JSON"}.get(output_format, output_format.upper())

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Inter, -apple-system, sans-serif; background: #f8fafc; margin: 0; padding: 0; }}
    .wrap {{ max-width: 580px; margin: 40px auto; background: #fff;
             border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; }}
    .header {{ background: #0F1F3D; padding: 32px 40px; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 22px; font-weight: 700;
                  font-family: Rajdhani, sans-serif; letter-spacing: 0.5px; }}
    .body {{ padding: 32px 40px; color: #374151; line-height: 1.6; }}
    .filename {{ background: #f1f5f9; border-radius: 8px; padding: 12px 16px;
                 font-family: monospace; font-size: 14px; color: #0F1F3D;
                 word-break: break-all; margin: 16px 0; }}
    .btn {{ display: inline-block; background: #2563EB; color: #fff !important;
            text-decoration: none; padding: 14px 28px; border-radius: 8px;
            font-weight: 600; font-size: 15px; margin-top: 8px; }}
    .footer {{ padding: 20px 40px; border-top: 1px solid #e2e8f0;
               color: #9ca3af; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>WhisperX &mdash; Transkription fertig</h1>
    </div>
    <div class="body">
      <p>Deine Transkription ist abgeschlossen.</p>
      <div class="filename">{filename}</div>
      <p>Format: <strong>{fmt_label}</strong></p>
      <p>
        <a class="btn" href="{results_url}">Ergebnis ansehen</a>
      </p>
      <p style="margin-top:24px;color:#6b7280;font-size:13px;">
        Oder direkt aufrufen:<br>
        <a href="{results_url}" style="color:#2563EB;">{results_url}</a>
      </p>
    </div>
    <div class="footer">
      Diese E-Mail wurde automatisch von WhisperX gesendet &middot;
      <a href="{APP_URL}" style="color:#9ca3af;">WhisperX</a>
    </div>
  </div>
</body>
</html>"""

    text = (
        f"Deine Transkription ist fertig!\n\n"
        f"Datei: {filename}\n"
        f"Format: {fmt_label}\n\n"
        f"Ergebnis: {results_url}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Transkription fertig: {filename}"
    msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )


async def send_transcription_error(to_email: str, filename: str, job_id: str) -> None:
    """Send a 'transcription failed' email."""
    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Inter, -apple-system, sans-serif; background:#f8fafc; margin:0; padding:0; }}
    .wrap {{ max-width:580px; margin:40px auto; background:#fff;
             border-radius:12px; border:1px solid #e2e8f0; overflow:hidden; }}
    .header {{ background:#0F1F3D; padding:32px 40px; }}
    .header h1 {{ color:#fff; margin:0; font-size:22px; font-weight:700; }}
    .body {{ padding:32px 40px; color:#374151; line-height:1.6; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header"><h1>WhisperX &mdash; Fehler bei Transkription</h1></div>
    <div class="body">
      <p>Bei der Transkription von <strong>{filename}</strong> ist ein Fehler aufgetreten.</p>
      <p>Bitte versuche es erneut oder kontaktiere den Support.</p>
      <p>Job-ID: <code>{job_id}</code></p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Transkription fehlgeschlagen: {filename}"
    msg["From"] = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )
