#!/usr/bin/env python3
"""
Telegram Personal Account AI Agent - connected to OUR OWN Muse Bridge.

Flow per incoming message:
  Telegram (your real account, Pyrogram userbot session)
    -> this agent (rules: private chats only, whitelist, ignore own msgs)
    -> Muse Bridge  http://127.0.0.1:4010/v1/chat/completions
       model: muse-spark-1.3   (peeche Muse khud reply banata hai)
    -> reply is sent back FROM YOUR ACCOUNT by this agent.

IMPORTANT bridge note: the Muse Bridge is NOT a normal cloud API. Its
server (~/workspace/deepseek-harness/bridge/server.js) must be running AND
a Muse responder must be answering its queue, otherwise calls time out.
If the bridge is down this agent only logs the message and sends NOTHING.

Safety defaults (config in .env):
  AGENT_MODE=whitelist   -> auto-reply ONLY to chat ids in WHITELIST below
                            (empty whitelist = reply to nobody; test first)
  AGENT_MODE=all_private -> auto-reply to every private chat (use later)
  - Never replies to bots, channels, or its own outgoing messages.
  - Per-chat short memory (last 10 turns), typing indicator + small delay
    so it does not look instant/robotic.
  - Hard cap: replies longer than 2000 chars are trimmed.

Control from your own Saved Messages / any chat (outgoing commands):
  .agent off   -> stop auto-replying (agent keeps logging only)
  .agent on    -> resume
"""
import asyncio
import json
import os
import time
import urllib.request
from collections import defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent

BRIDGE_URL = os.environ.get("MUSE_BRIDGE_URL", "http://127.0.0.1:4010/v1/chat/completions")
BRIDGE_MODEL = os.environ.get("MUSE_BRIDGE_MODEL", "muse-spark-1.3")
BRIDGE_KEY = os.environ.get("MUSE_BRIDGE_KEY", "muse-bridge-local-key")  # local placeholder only
BRIDGE_TIMEOUT = int(os.environ.get("BRIDGE_TIMEOUT", "120"))

SYSTEM_PROMPT = (
    "You are replying on Telegram AS Mohd Khatab himself, in his own personal chat. "
    "Reply in short, natural Roman English / Hinglish, the way he chats. "
    "Be helpful and friendly. Do not reveal you are an AI or a bot. "
    "Do not promise payments, do not share personal data, codes or passwords. "
    "If a message needs Mohd's own decision (money, personal commitment), reply that "
    "you will confirm and get back - do not decide for him."
)

_state = {"enabled": True}
_history: dict[int, deque] = defaultdict(lambda: deque(maxlen=10))


def load_env() -> dict:
    env = {}
    f = HERE / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def bridge_reply(chat_id: int, sender_name: str, text: str) -> str | None:
    """Call our Muse Bridge (OpenAI-compatible). Blocking HTTP run in a thread."""
    hist = _history[chat_id]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in hist:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{sender_name}: {text}"})

    payload = json.dumps({"model": BRIDGE_MODEL, "messages": messages}).encode()
    req = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {BRIDGE_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=BRIDGE_TIMEOUT) as resp:
        data = json.loads(resp.read().decode())
    content = data["choices"][0]["message"]["content"].strip()
    return content[:2000] or None


async def main() -> None:
    from pyrogram import Client, filters
    from pyrogram.enums import ChatAction

    env = load_env()
    api_id = int(os.environ.get("TG_API_ID") or env.get("TG_API_ID") or "0")
    api_hash = os.environ.get("TG_API_HASH") or env.get("TG_API_HASH") or ""
    mode = (os.environ.get("AGENT_MODE") or env.get("AGENT_MODE") or "whitelist").strip()
    whitelist = {
        int(x) for x in (os.environ.get("AGENT_WHITELIST") or env.get("AGENT_WHITELIST") or "").replace(" ", "").split(",") if x.lstrip("-").isdigit()
    }
    if not api_id or not api_hash:
        raise SystemExit("Pehle login.py chalao aur .env mein TG_API_ID / TG_API_HASH rakho.")

    app = Client(str(HERE / "my_account"), api_id=api_id, api_hash=api_hash)

    @app.on_message(filters.outgoing & filters.regex(r"^\.agent (on|off)$"))
    async def control(_, message):
        _state["enabled"] = message.matches[0].group(1) == "on"
        await message.edit(f"Agent auto-reply: {'ON' if _state['enabled'] else 'OFF'}")

    @app.on_message(filters.private & ~filters.me & ~filters.bot & filters.text)
    async def handle(client, message):
        if not _state["enabled"]:
            return
        if mode == "whitelist" and message.chat.id not in whitelist:
            print(f"[skip - whitelist mein nahi] {message.chat.id}: {message.text[:80]}")
            return
        sender = message.from_user.first_name if message.from_user else "User"
        try:
            reply = await asyncio.to_thread(bridge_reply, message.chat.id, sender, message.text)
        except Exception as e:  # bridge down / timeout -> send NOTHING, just log
            print(f"[bridge error, reply nahi bheja] {type(e).__name__}: {e}")
            return
        if not reply:
            return
        _history[message.chat.id].append(("user", message.text))
        _history[message.chat.id].append(("assistant", reply))
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)
        await asyncio.sleep(min(2.0, 0.6 + len(reply) / 220.0))
        await message.reply(reply)
        print(f"[replied] {message.chat.id} <- {reply[:80]}")

    me = None
    async with app:
        me = await app.get_me()
        print(f"Agent LIVE as {me.first_name} (@{me.username}) | mode={mode} | bridge={BRIDGE_URL} model={BRIDGE_MODEL}")
        print("Band karne ke liye Ctrl+C. Apni kisi chat mein '.agent off' bhejo to auto-reply ruk jayega.")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
