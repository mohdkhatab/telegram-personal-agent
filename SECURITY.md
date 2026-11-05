# Security Policy

## Sensitive Material in This Project

This project operates a **real personal Telegram account**. The following
items are equivalent to the account password and must be treated as secrets:

| Item | Why it is sensitive |
|---|---|
| `telethon_account.session` (any `*.session` file) | Anyone holding it can sign in as the account without a password or code |
| `TG_API_HASH` in `.env` | App credential paired with the API ID |
| Login codes (OTP) and the 2-Step Verification password | One-time/full account access |

Rules:

- Keep `.env` and session files at `chmod 600`.
- Never commit them — they are listed in `.gitignore`.
- Never paste them into chats, issues, pull requests, logs, or screenshots.
- One-time codes are used once, in memory / one-time files that are deleted
  immediately after use, and are never logged.
- If a session file leaks, revoke it immediately in the Telegram app:
  **Settings → Devices → terminate the session**, and change the account's
  2-Step Verification password.

## Operational Safety

- The agent runs in `whitelist` mode by default in the example config; the
  broader `all_private` mode should only be enabled deliberately by the
  account owner.
- The agent stops sending anything when its reply engine (the bridge) is
  unreachable — it must never fall back to sending unreviewed content from
  an unintended source.
- A `STOP` file next to the agent disables the keepalive watchdog.

## Reporting a Vulnerability

If you find a security problem in this code (for example, a path that could
expose a session file or credential), please do **not** open a public issue
with the details. Contact the maintainer privately (Mohd Khatab, via the
account that shared this repository) with a description and steps to
reproduce. You should receive a response within a few days, and a fix or a
documented mitigation will follow.

## Supported Versions

Only the latest state of the `main` branch is supported with security fixes.
