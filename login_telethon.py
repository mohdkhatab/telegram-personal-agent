#!/usr/bin/env python3
"""
Telethon driver: real-account login for THIS sandbox.
- Direct MTProto from this VM fails (raw DC connections are garbled by the
  sandbox egress), so we connect through the runtime's HTTP proxy taken
  from the https_proxy env var at runtime (never printed, never saved).
- Flow: send_code_request -> code arrives in the Telegram app service chat
  -> code is dropped into ./otp.txt by the operator -> read once, delete,
  sign_in. 2-Step ON ho to ./pwd.txt se password, same one-time pattern.
- Status -> ./login_state.json, result (no secrets) -> ./login_result.json
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
SESSION = str(HERE / "telethon_account")
WAIT_SECONDS = 1200


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


def proxy_from_env() -> dict | None:
    raw = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or ""
    if not raw:
        return None
    p = urlparse(raw)
    return {"proxy_type": "http", "addr": p.hostname, "port": p.port, "username": p.username, "password": p.password}


def set_state(stage: str, message: str = "") -> None:
    (HERE / "login_state.json").write_text(json.dumps({"stage": stage, "message": message, "ts": time.time()}))


async def wait_for_file(name: str) -> str | None:
    p = HERE / name
    for _ in range(WAIT_SECONDS):
        if p.exists():
            try:
                val = p.read_text().strip()
            finally:
                p.unlink(missing_ok=True)
            if val:
                return val
        await asyncio.sleep(1)
    return None


async def main() -> int:
    from telethon import TelegramClient, errors

    env = load_env()
    api_id = int(env.get("TG_API_ID") or "0")
    api_hash = env.get("TG_API_HASH") or ""
    phone = (os.environ.get("TG_PHONE") or "").strip()
    if not api_id or not api_hash or not phone:
        set_state("error", "missing api/phone")
        return 2

    client = TelegramClient(SESSION, api_id, api_hash, proxy=proxy_from_env())
    await client.connect()
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            (HERE / "login_result.json").write_text(json.dumps({"ok": True, "id": me.id, "first_name": me.first_name, "username": me.username}))
            set_state("done", "already authorized")
            return 0
        set_state("sending_code")
        sent = await client.send_code_request(phone)
        set_state("waiting_otp", f"code type: {type(sent.type).__name__}")
        code = await wait_for_file("otp.txt")
        if not code:
            set_state("error", "otp timeout")
            return 3
        try:
            user = await client.sign_in(phone, code.replace(" ", ""), phone_code_hash=sent.phone_code_hash)
        except errors.SessionPasswordNeededError:
            set_state("waiting_password")
            pwd = await wait_for_file("pwd.txt")
            if not pwd:
                set_state("error", "password timeout")
                return 3
            user = await client.sign_in(password=pwd)
        except errors.PhoneCodeInvalidError:
            set_state("error", "code invalid")
            return 4
        except errors.PhoneCodeExpiredError:
            set_state("error", "code expired")
            return 4
        me = user if hasattr(user, "first_name") else await client.get_me()
        (HERE / "login_result.json").write_text(json.dumps({"ok": True, "id": me.id, "first_name": getattr(me, "first_name", ""), "username": getattr(me, "username", None)}))
        set_state("done")
        return 0
    finally:
        await client.disconnect()
        for sess in HERE.glob("telethon_account.session*"):
            try:
                os.chmod(sess, 0o600)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
