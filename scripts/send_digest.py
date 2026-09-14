"""Email the daily digest to yourself.

USAGE
    python scripts/send_digest.py --setup       # one-time: how to get a Gmail App Password
    python scripts/send_digest.py --dry-run     # render and preview WITHOUT sending
    python scripts/send_digest.py               # send the most recent digest
    python scripts/send_digest.py --file reports/daily/digest_2026-09-14.md
    python scripts/send_digest.py --to someone@example.com

SAFETY
    Your password is never stored in code, never printed, and never committed. It lives only
    in `.env`, which is gitignored. Always try --dry-run first: it renders the whole email
    and writes an HTML preview you can open in a browser, without contacting a mail server.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import _bootstrap  # noqa: F401
from invest import config, mailer
from invest.mailer import MailConfigError

SETUP = """
================================================================================
SETTING UP EMAIL - one time, about five minutes
================================================================================

Gmail will NOT accept your normal password from a script. Google requires an
"App Password": a 16-digit code that works for one program only and can be
revoked without changing your real password.

STEP 1 - Turn on 2-Step Verification (required before App Passwords exist)
    https://myaccount.google.com/signinoptions/two-step-verification

STEP 2 - Create an App Password
    https://myaccount.google.com/apppasswords
    Name it something like "INVEST digest".
    Google shows you 16 characters such as:  abcd efgh ijkl mnop
    Copy them. You cannot see them again - but you can always delete it and
    make a new one.

STEP 3 - Put it in your .env file (this file is gitignored and never leaves
         your machine). Open .env and add:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=your.address@gmail.com
    SMTP_APP_PASSWORD=abcdefghijklmnop
    DIGEST_TO=your.address@gmail.com

    Spaces in the password are fine - they get stripped automatically.

STEP 4 - Test without sending anything
    python scripts/send_digest.py --dry-run

STEP 5 - Send it
    python scripts/send_digest.py

--------------------------------------------------------------------------------
NOT USING GMAIL?
    Outlook / Hotmail :  SMTP_HOST=smtp-mail.outlook.com   SMTP_PORT=587
    Yahoo Mail        :  SMTP_HOST=smtp.mail.yahoo.com     SMTP_PORT=465
    iCloud            :  SMTP_HOST=smtp.mail.me.com        SMTP_PORT=587
    All of these also require an app-specific password.

IF IT WILL NOT CONNECT
    Some networks (university and corporate wifi especially) block outbound
    SMTP. Try SMTP_PORT=465, or a phone hotspot, to find out which it is.

SECURITY NOTES
    * An App Password grants access to send mail as you. Treat it like a key.
    * Revoke it any time at the App Passwords page - nothing else breaks.
    * It is in .env, which git ignores. Never paste it into a .py file: this
      repository is public, and a committed secret stays in the history forever.
================================================================================
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Email the daily digest.")
    ap.add_argument("--file", default=None, help="digest to send (default: most recent)")
    ap.add_argument("--to", default=None, help="override the recipient in .env")
    ap.add_argument("--subject", default=None, help="override the subject line")
    ap.add_argument("--dry-run", action="store_true",
                    help="render and preview without sending or contacting a server")
    ap.add_argument("--open", action="store_true",
                    help="with --dry-run, open the HTML preview in your browser")
    ap.add_argument("--setup", action="store_true", help="show the one-time setup guide")
    args = ap.parse_args()

    config.ensure_dirs()

    if args.setup:
        print(SETUP)
        return 0

    # ---- which digest ----------------------------------------------------------------
    try:
        md_path = Path(args.file) if args.file else mailer.latest_digest()
        if not md_path.is_absolute():
            md_path = config.ROOT / md_path
        if not md_path.exists():
            print("Digest not found: " + str(md_path))
            return 1
    except MailConfigError as exc:
        print(str(exc))
        return 1

    print("Digest : " + str(md_path.relative_to(config.ROOT)))
    print("Size   : " + format(md_path.stat().st_size / 1024, ".1f") + " KB")

    # ---- dry run needs no credentials -------------------------------------------------
    if args.dry_run:
        md_text = md_path.read_text(encoding="utf-8")
        first = next((ln.lstrip("# ").strip() for ln in md_text.splitlines()
                      if ln.startswith("#")), md_path.stem)
        subject = args.subject or first
        html = mailer.markdown_to_html(md_text, subject)
        preview = config.LOGS_DIR / ("digest_preview_" + md_path.stem + ".html")
        preview.write_text(html, encoding="utf-8")

        print("Subject: " + subject)
        try:
            s = mailer.load_settings()
            print("\nSMTP settings found in .env:")
            for k, v in s.redacted().items():
                print("  " + k.ljust(12) + str(v))
        except MailConfigError as exc:
            print("\nNOT configured to send yet:")
            print("  " + str(exc).replace("\n", "\n  "))
        print("\nDRY RUN - nothing was sent and no mail server was contacted.")
        print("HTML preview written to: " + str(preview.relative_to(config.ROOT)))
        if args.open:
            webbrowser.open(preview.resolve().as_uri())
        return 0

    # ---- real send --------------------------------------------------------------------
    try:
        settings = mailer.load_settings()
        if args.to:
            settings.recipients = [t.strip() for t in args.to.split(",") if t.strip()]
        print("To     : " + ", ".join(settings.recipients))
        print("Via    : " + settings.host + ":" + str(settings.port)
              + " (" + ("SSL" if settings.use_ssl else "STARTTLS") + ")")
        msg = mailer.build_message(md_path, settings, subject=args.subject)
        print("Subject: " + str(msg["Subject"]))
        print("\nSending ...")
        mailer.send(msg, settings)
    except MailConfigError as exc:
        print("\nFAILED: " + str(exc))
        return 1

    print("Sent.")
    print("\nIf it is not in your inbox, check the spam folder and mark it 'not spam' -")
    print("mail sent by a script to its own account is sometimes filtered the first time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
