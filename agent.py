#!/usr/bin/env python3
"""
Telegram Personal Account AI Agent (Telethon) — multi-provider edition.

Your REAL Telegram account (session: telethon_account.session) gets a backup
agent that auto-replies on your behalf:

  incoming message (private chat or group)
    -> rules: enabled? mode / whitelist / group mode, bots ignored
    -> AI provider (ANY OpenAI-compatible API — see below)
    -> reply sent from your account, with a live typing indicator

AI providers (.env -> AI_PROVIDER): bridge (local Muse Bridge, default),
openrouter, openai, groq, ollama, or "custom" with your own
AI_BASE_URL + AI_API_KEY + AI_MODEL. Anything that speaks the
OpenAI chat-completions format works.

Modes (.env):
  AGENT_MODE=all_private   -> reply in every private chat
  AGENT_MODE=whitelist     -> reply only in AGENT_WHITELIST chat IDs
  AGENT_GROUPS=all         -> reply to every group message
  AGENT_GROUPS=mention     -> groups: reply only on @mention / reply-to-you /
                              trigger words (GROUP_TRIGGERS)
  AGENT_GROUPS=off         -> no group replies
Control from the account itself: send `.agent off` / `.agent on` in any chat.

Note: on hosts where direct MTProto is blocked, Telethon connects through
the HTTP proxy found in the https_proxy environment variable (read at
runtime, never saved to disk).
"""
import asyncio
import json
import os
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SESSION = str(HERE / "telethon_account")
AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "120"))

SYSTEM_PROMPT = (
    "You are the backup agent of Prime Khatab (Mohd Khatab), replying on his behalf on his "
    "personal Telegram while he is unavailable. Reply in short, natural Roman English / "
    "Hinglish, the way he chats. Be helpful and friendly. "
    "IDENTITY RULE - very important: if anyone asks who you are, 'tum kaun ho', whether "
    "Prime Khatab himself is speaking, or anything like that, reply with exactly this "
    "meaning in this line: 'Prime Khatab abhi available nahi hai, main unka backup agent "
    "hoon, unke behalf par reply kar raha hoon.' Do not claim to be Prime Khatab himself. "
    "Do not promise payments, do not share personal data, codes or passwords. "
    "If a message needs his own decision (money, personal commitment), say you will pass "
    "it to Prime Khatab and he will confirm - do not decide for him."
)

# ---------------------------------------------------------------- config ---

def load_config() -> dict:
    """Config = .env file values, overlaid by real environment variables."""
    cfg: dict[str, str] = {}
    f = HERE / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k in cfg or k.startswith(("TG_", "AI_", "AGENT_", "GROUP_", "MUSE_")):
            cfg[k] = v
    return cfg


# Provider presets: name -> (base_url, default_model, key_is_local_placeholder)
PROVIDER_PRESETS = {
    "bridge":     ("http://127.0.0.1:4010/v1",        "muse-spark-1.3",          True),
    "openrouter": ("https://openrouter.ai/api/v1",    "openai/gpt-4o-mini",      False),
    "openai":     ("https://api.openai.com/v1",       "gpt-4o-mini",             False),
    "groq":       ("https://api.groq.com/openai/v1",  "llama-3.3-70b-versatile", False),
    "ollama":     ("http://127.0.0.1:11434/v1",       "llama3.1",                True),
}


def resolve_provider(cfg: dict) -> tuple[str, str, str]:
    """Return (chat_completions_url, api_key, model) for the chosen provider."""
    provider = (cfg.get("AI_PROVIDER") or "bridge").strip().lower()
    base, model, local = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["bridge"])
    # Generic overrides — this is what makes ANY OpenAI-compatible API work.
    base = cfg.get("AI_BASE_URL") or base
    model = cfg.get("AI_MODEL") or model
    key = cfg.get("AI_API_KEY") or ""
    # Backwards compatibility with the original bridge-only settings.
    if provider == "bridge":
        legacy_url = cfg.get("MUSE_BRIDGE_URL")
        if legacy_url:
            base = legacy_url.rsplit("/chat/completions", 1)[0]
        model = cfg.get("AI_MODEL") or cfg.get("MUSE_BRIDGE_MODEL") or model
        key = key or cfg.get("MUSE_BRIDGE_KEY") or "muse-bridge-local-key"
    if local and not key:
        key = "local-no-key-needed"
    return base.rstrip("/") + "/chat/completions", key, model


def proxy_from_env() -> dict | None:
    raw = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    if not raw:
        return None
    p = urlparse(raw)
    return {"proxy_type": "http", "addr": p.hostname, "port": p.port,
            "username": p.username, "password": p.password}


# ------------------------------------------------------------- AI engine ---

_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=10))


def ai_reply(cfg: dict, hist_key: str, sender_name: str, text: str) -> str | None:
    """Call the configured OpenAI-compatible provider. Blocking; run in a thread."""
    url, key, model = resolve_provider(cfg)
    hist = _history[hist_key]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in hist:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{sender_name}: {text}"})

    payload = json.dumps({"model": model, "messages": messages}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    if "openrouter.ai" in url:  # OpenRouter appreciates attribution headers
        headers["HTTP-Referer"] = "https://github.com/mohdkhatab/telegram-personal-agent"
        headers["X-Title"] = "Telegram Personal Agent"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    host = urlparse(url).hostname or ""
    if host in ("127.0.0.1", "localhost", "::1"):
        # Local provider: never route through the egress proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    else:
        opener = urllib.request.build_opener()  # honors *_proxy env vars
    with opener.open(req, timeout=AI_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())
    msg = data["choices"][0]["message"]
    content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
    return content[:2000] or None


# ------------------------------------------------------------ rule logic ---

def decide_reply(*, is_private: bool, is_group: bool, chat_id: int, mode: str,
                 groups_mode: str, whitelist: set[int],
                 triggered: bool) -> bool:
    """Pure decision function (unit-tested). Should the agent reply here?"""
    if is_private:
        if mode == "all_private":
            return True
        if mode == "whitelist":
            return chat_id in whitelist
        return False
    if is_group:
        if groups_mode == "all":
            return True
        if groups_mode == "mention":
            return triggered
        return False
    return False  # channels / broadcast posts are never auto-replied


# ----------------------------------------------------------------- agent ---

_state = {"enabled": True}
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_last_group_reply: dict[int, float] = {}


async def main() -> None:
    from telethon import TelegramClient, events

    cfg = load_config()
    api_id = int(cfg.get("TG_API_ID") or "0")
    api_hash = cfg.get("TG_API_HASH") or ""
    mode = (cfg.get("AGENT_MODE") or "whitelist").strip()
    groups_mode = (cfg.get("AGENT_GROUPS") or "off").strip()
    whitelist = {int(x) for x in (cfg.get("AGENT_WHITELIST") or "").replace(" ", "").split(",")
                 if x.lstrip("-").isdigit()}
    triggers = [t.strip().lower() for t in (cfg.get("GROUP_TRIGGERS") or "prime,primekhatab").split(",") if t.strip()]
    group_cooldown = float(cfg.get("GROUP_COOLDOWN_SEC") or "8")
    if not api_id or not api_hash:
        raise SystemExit(".env mein TG_API_ID / TG_API_HASH missing hai.")

    url, _key, model = resolve_provider(cfg)
    client = TelegramClient(SESSION, api_id, api_hash, proxy=proxy_from_env())
    await client.connect()
    if not await client.is_user_authorized():
        raise SystemExit("Session authorized nahi hai - pehle login_telethon.py chalao.")
    me = await client.get_me()
    my_id = me.id
    my_username = (me.username or "").lower()
    print(f"Agent LIVE as {me.first_name} (@{me.username}) | private={mode} groups={groups_mode} "
          f"| provider={cfg.get('AI_PROVIDER') or 'bridge'} model={model} url={url}", flush=True)

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.agent (on|off)$"))
    async def control(event):
        _state["enabled"] = event.pattern_match.group(1) == "on"
        await event.edit(f"Agent auto-reply: {'ON' if _state['enabled'] else 'OFF'}")

    @client.on(events.NewMessage(incoming=True))
    async def handle(event):
        if not event.raw_text or len(event.raw_text.strip()) < 2:
            return
        is_private = bool(event.is_private)
        is_group = bool(event.is_group)
        if not (is_private or is_group):
            return
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False) or getattr(sender, "id", None) == my_id:
            return
        if not _state["enabled"]:
            return

        # Group trigger detection (for AGENT_GROUPS=mention).
        text_low = event.raw_text.lower()
        triggered = (f"@{my_username}" in text_low) if my_username else False
        if not triggered and any(t in text_low for t in triggers):
            triggered = True
        if not triggered and event.message.reply_to_msg_id:
            try:
                replied = await event.get_reply_message()
                if replied is not None and replied.sender_id == my_id:
                    triggered = True
            except Exception:
                pass

        chat_id = event.chat_id
        if not decide_reply(is_private=is_private, is_group=is_group, chat_id=chat_id,
                             mode=mode, groups_mode=groups_mode, whitelist=whitelist,
                             triggered=triggered):
            if is_private and mode == "whitelist":
                print(f"[skip - whitelist mein nahi] {chat_id}: {event.raw_text[:60]}", flush=True)
            return

        # Groups: per-chat cooldown so a busy group does not get reply spam.
        if is_group:
            last = _last_group_reply.get(chat_id, 0.0)
            if time.monotonic() - last < group_cooldown:
                return

        name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "User"
        hist_key = str(chat_id) if is_private else f"{chat_id}:{sender.id}"

        async with _locks[chat_id]:  # one reply at a time per chat, order safe
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendMessageTypingAction

            ai_task = asyncio.ensure_future(asyncio.to_thread(ai_reply, cfg, hist_key, name, event.raw_text))
            # LIVE TYPING from the moment the message arrives, refreshed
            # while the provider generates the reply.
            while not ai_task.done():
                try:
                    await client(SetTypingRequest(peer=chat_id, action=SendMessageTypingAction()))
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(asyncio.shield(ai_task), timeout=4)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break
            try:
                reply = ai_task.result()
            except Exception as e:
                print(f"[ai error, reply nahi bheja] {type(e).__name__}: {str(e)[:120]}", flush=True)
                return
            if not reply:
                return
            _history[hist_key].append(("user", event.raw_text))
            _history[hist_key].append(("assistant", reply))
            async with client.action(chat_id, "typing"):
                await asyncio.sleep(min(0.8, 0.25 + len(reply) / 600.0))
                await event.reply(reply)
            if is_group:
                _last_group_reply[chat_id] = time.monotonic()
            print(f"[replied] {'group' if is_group else 'dm'} {chat_id} <- {reply[:70]}", flush=True)

    print("Listening... band karne ke liye process stop karo, ya chat mein '.agent off' bhejo.", flush=True)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
