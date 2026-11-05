# Telegram Personal Agent

An AI auto-reply agent for a **real, personal Telegram account** (not a bot).
It signs in with your own account through Telegram's MTProto API, listens to
incoming messages in **private chats and groups**, generates replies through
**any OpenAI-compatible AI API** — OpenRouter, OpenAI, Groq, Ollama, or a
local Muse Bridge — and sends them from your account with a live typing
indicator.

> The agent presents itself honestly: it is the account owner's **backup
> agent**. If anyone asks who is speaking, it replies:
> *"Prime Khatab abhi available nahi hai, main unka backup agent hoon, unke
> behalf par reply kar raha hoon."*

## Framework & Stack

| Layer | Technology |
|---|---|
| Language | **Python 3.12** |
| Telegram framework | **Telethon 1.45** (MTProto client framework) |
| AI reply engine | **Any OpenAI-compatible API** — presets for OpenRouter, OpenAI, Groq, Ollama and a local Muse Bridge, plus a `custom` mode for any other endpoint |
| Async model | `asyncio` (Telethon events + blocking bridge calls via `asyncio.to_thread`) |
| Config | `.env` file (never committed) |
| Session | Telethon SQLite session file (chmod 600) |

No web framework is used — this is a long-running async CLI process.

## Features

- Signs in a **personal account** with phone number + login code
  (`send_code_request` → `sign_in`), with 2-Step Verification support.
- Auto-replies to **all private chats** (`AGENT_MODE=all_private`) or only to
  a **whitelist** of chat IDs (`AGENT_MODE=whitelist`).
- **Group replies** (`AGENT_GROUPS`): `all` = reply to every group message,
  `mention` = only on @mention / reply-to-you / trigger words, `off` = none.
  A per-group cooldown stops reply spam in busy groups.
- **Any AI provider**: one config key switches between OpenRouter, OpenAI,
  Groq, Ollama, a local bridge, or your own custom OpenAI-compatible API.
- **Live typing effect** — typing is shown the moment a message arrives and
  refreshed (~4 s) while the reply is being generated.
- Short per-chat conversation memory (last 10 turns).
- In-chat remote control: send `.agent off` / `.agent on` from the account.
- Bots are ignored; groups/channels are not auto-replied.
- If the AI provider is unreachable, the agent sends nothing and only logs
  the error — it never falls back to an unintended source.
- Optional 24×7 keepalive script (`keepalive.sh`) that restarts the bridge
  and the agent if they die, and respects a `STOP` file.

## Architecture

```
Incoming Telegram message (MTProto, Telethon)
        │
        ▼
   agent.py ── rules: enabled? mode/whitelist? not a bot?
        │
        ▼
 AI provider  POST <base>/chat/completions
        │      (OpenRouter / OpenAI / Groq / Ollama / local bridge)
        ▼
   reply ──► sent from the personal account (with typing indicator)
```

Note: on hosts where direct MTProto connections are blocked, Telethon is
routed through the HTTP proxy found in the `https_proxy` environment
variable (read at runtime, never written to disk).

## Project Structure

```
telegram-agent/
├── agent.py            # Main agent: listener -> bridge -> reply
├── login_telethon.py   # One-time login driver (code via otp.txt)
├── login.py            # Interactive login (Pyrogram, legacy/alt)
├── keepalive.sh        # 24x7 watchdog for bridge + agent (STOP-aware)
├── requirements.txt
├── .env.example        # Config template
├── .env                # Your real config (chmod 600, git-ignored)
├── telethon_account.session  # Login session (chmod 600, NEVER share)
└── README / LICENSE / CONTRIBUTING / SECURITY / CHANGELOG ...
```

## Setup

1. **Get API credentials** — on [my.telegram.org/apps](https://my.telegram.org/apps)
   create/open an app and note its `api_id` and `api_hash`.
2. **Install dependencies**:

   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure** — copy `.env.example` to `.env`, fill in `TG_API_ID` and
   `TG_API_HASH`, then lock it down:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

4. **Log in once** (creates the session file):

   ```bash
   TG_PHONE=+91XXXXXXXXXX python login_telethon.py
   # when the state file says "waiting_otp", put the code you received
   # in the Telegram app into ./otp.txt — it is read once and deleted.
   ```

5. **Pick your AI provider** in `.env` — for example OpenRouter:

   ```ini
   AI_PROVIDER=openrouter
   AI_API_KEY=sk-or-...
   # AI_MODEL=openai/gpt-4o-mini   (optional override)
   ```

   Or run fully local with the Muse Bridge preset (default) or Ollama —
   see `.env.example` for all presets.

6. **Run the agent**:

   ```bash
   python agent.py
   ```

## Configuration (.env)

| Key | Meaning |
|---|---|
| `TG_API_ID` / `TG_API_HASH` | Your Telegram app credentials |
| `AI_PROVIDER` | `bridge` (default), `openrouter`, `openai`, `groq`, `ollama`, or `custom` |
| `AI_API_KEY` | Your provider API key (not needed for local bridge/Ollama) |
| `AI_BASE_URL` / `AI_MODEL` | Optional overrides for any OpenAI-compatible endpoint/model |
| `AGENT_MODE` | `all_private` = reply to everyone, `whitelist` = only listed chats |
| `AGENT_WHITELIST` | Comma-separated chat IDs (whitelist mode) |
| `AGENT_GROUPS` | `all` = every group message, `mention` = only triggers, `off` = none |
| `GROUP_COOLDOWN_SEC` | Minimum seconds between replies in the same group |
| `GROUP_TRIGGERS` | Comma-separated trigger words for group `mention` mode |

## Stopping

- Quick pause from Telegram: send `.agent off` in any chat.
- Full stop: kill the `agent.py` process and create the `STOP` file so the
  keepalive will not restart it:

  ```bash
  touch STOP
  pkill -f agent.py
  ```

- Revoke the login entirely: Telegram app → Settings → Devices →
  terminate the session.

## Safety

- The `.session` file and `TG_API_HASH` are equivalent to your password.
  Never share them, never commit them. See [SECURITY.md](SECURITY.md).
- Automated messaging can trigger Telegram flood limits. Use reasonable
  rates; do not use this for spam or bulk unsolicited messages.
- Respect Telegram's Terms of Service and the privacy of the people who
  message the account.

## License

[MIT](LICENSE) © 2026 Mohd Khatab
