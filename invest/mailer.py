"""Turn a markdown digest into an email and send it over SMTP.

SECURITY, FIRST AND LOUDEST
---------------------------
This repository is PUBLIC. No password may ever be written into a Python file, a commit, or
a command you type where it lands in shell history. Credentials live only in `.env`, which
is gitignored, and this module reads them from the environment and never prints them.

Gmail will NOT accept your normal account password. You need an App Password - a 16-digit
code Google issues for one specific program - and that requires 2-Step Verification on the
account. Setup instructions are printed by `scripts/send_digest.py --setup`.

WHAT IT SENDS
    A multipart email with a plain-text part (the raw markdown, readable anywhere) and an
    HTML part rendered for email clients. Tables carry inline styles because Gmail and
    Outlook strip or ignore much of a <style> block.
"""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path
from typing import Optional

from . import config


class MailConfigError(RuntimeError):
    """Raised when required settings are missing. Never contains a password."""


@dataclass
class MailSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    recipients: list[str]
    use_ssl: bool
    sender_name: str = "INVEST Research"

    def redacted(self) -> dict:
        """Everything except the password, for printing."""
        return {
            "host": self.host, "port": self.port, "user": self.user,
            "password": "<set, " + str(len(self.password)) + " chars, not shown>",
            "from": self.sender, "to": ", ".join(self.recipients),
            "encryption": "SSL" if self.use_ssl else "STARTTLS",
        }


def load_settings() -> MailSettings:
    """Read SMTP settings from the environment (populated from .env by config.py)."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port_raw = os.environ.get("SMTP_PORT", "587").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_APP_PASSWORD", "")
    sender = os.environ.get("DIGEST_FROM", user).strip()
    to_raw = os.environ.get("DIGEST_TO", "").strip()

    missing = [name for name, val in
               (("SMTP_USER", user), ("SMTP_APP_PASSWORD", password), ("DIGEST_TO", to_raw))
               if not val]
    if missing:
        raise MailConfigError(
            "Missing from .env: " + ", ".join(missing) + "\n"
            "Run:  python scripts/send_digest.py --setup   for instructions."
        )

    try:
        port = int(port_raw)
    except ValueError:
        raise MailConfigError("SMTP_PORT must be a number, got: " + port_raw)

    # Gmail App Passwords are 16 characters and are often pasted with spaces.
    password = password.replace(" ", "")
    if host.endswith("gmail.com") and len(password) != 16:
        raise MailConfigError(
            "SMTP_APP_PASSWORD does not look like a Gmail App Password. Those are exactly "
            "16 characters (spaces optional); yours is " + str(len(password)) + ". Your "
            "normal Gmail password will NOT work - Google rejects it. See --setup."
        )

    recipients = [r.strip() for r in re.split(r"[,;]", to_raw) if r.strip()]
    return MailSettings(host=host, port=port, user=user, password=password,
                        sender=sender or user, recipients=recipients,
                        use_ssl=(port == 465))


# --------------------------------------------------------------------------------------
# Markdown -> email HTML
# --------------------------------------------------------------------------------------
# Email clients are far behind browsers. Gmail strips much of a <style> block and Outlook
# uses Word's rendering engine, so anything that must survive is applied inline.
_INLINE = {
    "table": "border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;",
    "th": ("border:1px solid #d0d7de;padding:7px 10px;background:#f2f5f8;"
           "text-align:left;font-weight:600;"),
    "td": "border:1px solid #d0d7de;padding:7px 10px;vertical-align:top;",
    "blockquote": ("margin:14px 0;padding:10px 14px;border-left:4px solid #b32626;"
                   "background:#fdf3f3;color:#5c1a1a;"),
    "code": "background:#f2f5f8;padding:1px 5px;border-radius:3px;font-size:13px;",
    "h1": "font-size:23px;margin:26px 0 10px;color:#12243a;",
    "h2": "font-size:19px;margin:24px 0 8px;color:#12243a;border-bottom:1px solid #e4e8ec;padding-bottom:5px;",
    "h3": "font-size:16px;margin:18px 0 6px;color:#12243a;",
    "hr": "border:0;border-top:1px solid #e4e8ec;margin:22px 0;",
    "li": "margin:3px 0;",
    "p": "margin:9px 0;",
}


def markdown_to_html(md_text: str, title: str) -> str:
    """Render the digest to email-safe HTML."""
    try:
        import markdown as md
    except ImportError:
        raise MailConfigError(
            "The 'markdown' package is required. Run: python -m pip install -r requirements.txt"
        )

    body = md.markdown(md_text, extensions=["tables", "sane_lists", "nl2br"])

    for tag, style in _INLINE.items():
        body = body.replace("<" + tag + ">", "<" + tag + ' style="' + style + '">')
        body = re.sub(r"<" + tag + r'(\s+)(?![^>]*style=)', "<" + tag + ' style="' + style + r'"\1',
                      body)

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>" + title + "</title></head>"
        '<body style="margin:0;padding:0;background:#eef1f4;">'
        '<div style="max-width:760px;margin:0 auto;padding:22px 20px;background:#ffffff;'
        'font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
        'font-size:15px;line-height:1.55;color:#1c2733;">'
        + body +
        '<hr style="border:0;border-top:1px solid #e4e8ec;margin:26px 0 12px;">'
        '<p style="font-size:12px;color:#6b7785;margin:0;">'
        "Generated by your INVEST system. Research and education only - <b>not financial "
        "advice</b>, and Claude is not a licensed financial advisor. No return is guaranteed. "
        "Company figures come from SEC EDGAR filings; prices from Yahoo Finance. "
        "Forward-looking figures are projections, not facts."
        "</p></div></body></html>"
    )


def build_message(md_path: Path, settings: MailSettings,
                  subject: Optional[str] = None) -> EmailMessage:
    """Assemble the multipart email. Plain text first, HTML as the richer alternative."""
    if not md_path.exists():
        raise MailConfigError("Digest not found: " + str(md_path))
    md_text = md_path.read_text(encoding="utf-8")

    if not subject:
        first = next((ln.lstrip("# ").strip() for ln in md_text.splitlines()
                      if ln.startswith("#")), md_path.stem)
        subject = re.sub(r"[^\w\s—–:.,%()+-]", "", first).strip() or md_path.stem

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.sender_name, settings.sender))
    msg["To"] = ", ".join(settings.recipients)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=settings.sender.split("@")[-1])
    msg["X-INVEST-Source"] = md_path.name

    msg.set_content(md_text)                                   # plain-text fallback
    msg.add_alternative(markdown_to_html(md_text, subject), subtype="html")
    return msg


def send(msg: EmailMessage, settings: MailSettings, verbose: bool = True) -> None:
    """Deliver over SMTP. Errors are translated into something actionable."""
    context = ssl.create_default_context()
    try:
        if settings.use_ssl:
            server = smtplib.SMTP_SSL(settings.host, settings.port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(settings.host, settings.port, timeout=30)
        with server:
            if not settings.use_ssl:
                server.starttls(context=context)
            server.login(settings.user, settings.password)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailConfigError(
            "The mail server rejected the login.\n"
            "  * Gmail will NOT accept your normal password - you need an App Password.\n"
            "  * App Passwords require 2-Step Verification to be switched on first.\n"
            "  * Check SMTP_USER is the full address, e.g. you@gmail.com.\n"
            "Run --setup for the walkthrough. Your password was not logged."
        )
    except smtplib.SMTPRecipientsRefused:
        raise MailConfigError("The server refused the recipient address in DIGEST_TO.")
    except (smtplib.SMTPConnectError, OSError) as exc:
        raise MailConfigError(
            "Could not reach " + settings.host + ":" + str(settings.port) + " - "
            + type(exc).__name__ + ". Check the host/port and your network. Some networks "
            "block outbound SMTP; port 465 sometimes works where 587 does not."
        )


def latest_digest() -> Path:
    """Most recent digest by filename date."""
    files = sorted(config.DAILY_REPORTS_DIR.glob("digest_*.md"))
    if not files:
        raise MailConfigError(
            "No digests found in " + str(config.DAILY_REPORTS_DIR) + ". "
            "Generate one with: python scripts/make_digest.py"
        )
    return files[-1]
