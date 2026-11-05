#!/usr/bin/env python3
"""
Non-interactive driver for login.py's flow (used when stdin is not a TTY).

  TG_PHONE env -> send_code() -> waits for the code in ./otp.txt
  (file is read once and deleted immediately, never logged)
  -> sign_in() -> if 2-Step is ON, waits for ./pwd.txt the same way
  -> check_password() -> writes ./login_result.json and exits.

Status is written to ./login_state.json: stage + message, no secrets.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSION_NAME = str(HERE / "my_account")
WAIT_SECONDS = 900  # 15 min max wait for otp.txt / pwd.txt


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
    from pyrogram import Client, errors

    env = load_env()
    api_id = int(os.environ.get("TG_API_ID") or env.get("TG_API_ID") or "0")
    api_hash = os.environ.get("TG_API_HASH") or env.get("TG_API_HASH") or ""
    phone = (os.environ.get("TG_PHONE") or "").strip()
    if not api_id or not api_hash or not phone:
        set_state("error", "api id/hash or phone missing")
        return 2

    client = Client(SESSION_NAME, api_id=api_id, api_hash=api_hash)
    await client.connect()
    try:
        set_state("sending_code")
        sent = await client.send_code(phone)
        set_state("waiting_otp", f"code type: {type(sent.type).__name__ if sent.type else 'unknown'}")
        code = await wait_for_file("otp.txt")
        if not code:
            set_state("error", "otp timeout")
            return 3
        try:
            user = await client.sign_in(phone, sent.phone_code_hash, code.replace(" ", ""))
        except errors.SessionPasswordNeeded:
            set_state("waiting_password")
            pwd = await wait_for_file("pwd.txt")
            if not pwd:
                set_state("error", "password timeout")
                return 3
            user = await client.check_password(password=pwd)
        except errors.PhoneCodeInvalid:
            set_state("error", "code invalid")
            return 4
        except errors.PhoneCodeExpired:
            set_state("error", "code expired")
            return 4
        me = user if hasattr(user, "first_name") else await client.get_me()
        result = {
            "ok": True,
            "id": me.id,
            "first_name": getattr(me, "first_name", ""),
            "username": getattr(me, "username", None),
        }
        (HERE / "login_result.json").write_text(json.dumps(result))
        set_state("done")
        return 0
    finally:
        await client.disconnect()
        for sess in HERE.glob("my_account.session*"):
            try:
                os.chmod(sess, 0o600)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
