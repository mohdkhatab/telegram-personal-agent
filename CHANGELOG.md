# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-05

### Added

- **Multi-provider AI engine**: replies can now come from any
  OpenAI-compatible API. Presets: `openrouter`, `openai`, `groq`, `ollama`,
  local `bridge` (default), plus a `custom` mode with `AI_BASE_URL` /
  `AI_API_KEY` / `AI_MODEL` overrides.
- **Group replies** with `AGENT_GROUPS=all|mention|off`, trigger-word and
  @mention detection, and a per-group cooldown against reply spam.

### Fixed

- Config loader now correctly overlays real environment variables over
  `.env` values (previously only keys already present in `.env` were seen).
- Remote providers are called through the environment proxy while local
  providers (bridge/Ollama) are always called directly.
- Per-chat locking so replies in one chat can never arrive out of order.
- Reasoning-style provider responses with empty `content` now fall back to
  `reasoning_content` instead of dropping the reply.
- Moved the deprecated Pyrogram implementation to `legacy/`.

## [1.0.0] - 2026-11-05

### Added

- Initial release.
- Personal-account sign-in through Telegram's MTProto API using Telethon:
  phone number + login code (`send_code_request` / `sign_in`), with 2-Step
  Verification support, via `login_telethon.py` (one-time `otp.txt` flow).
- Main agent (`agent.py`): listens to incoming private messages, generates
  replies through a local Muse Bridge (OpenAI-compatible endpoint, model
  `muse-spark-1.3`), and replies from the account.
- Modes: `all_private` (reply to all private chats) and `whitelist`
  (only configured chat IDs). Bots are always ignored.
- Live typing indicator from message arrival, refreshed while the reply is
  generated, plus a short natural pause before sending.
- Identity rule: the agent identifies as the owner's **backup agent** when
  asked who is speaking.
- Per-chat short conversation memory (last 10 turns).
- In-chat control commands: `.agent on` / `.agent off`.
- Proxy support: direct MTProto is blocked on some hosts, so Telethon can
  route through the HTTP proxy from the `https_proxy` environment variable.
- `keepalive.sh`: watchdog that restarts the bridge and agent if they die,
  honoring a `STOP` file.
- Project documentation: README, MIT LICENSE, CONTRIBUTING, SECURITY,
  CODE_OF_CONDUCT.
