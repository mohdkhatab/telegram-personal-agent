#!/usr/bin/env python3
"""
Telegram REAL (personal) account login - Userbot session maker.

Flow (exactly what the user asked for):
  1. You enter your personal phone number (with country code, e.g. +91...).
  2. This script sends a login-code request to Telegram's MTProto API
     (Pyrogram send_code) using YOUR api_id + api_hash.
  3. Telegram delivers a code inside your Telegram app (official Telegram
     service chat) - sometimes by SMS/call if the app is not reachable.
  4. You type that code HERE, in this terminal only - never in a chat,
     never to any person or public bot. The code is used once, in memory,
     and is never saved or printed back.
  5. If your account has 2-Step Verification, Telegram asks for that
     password (typed hidden, also never saved).
  6. On success a session file `my_account.session` is created in this
     folder (chmod 600). That file IS the login - treat it like a password.
     From then on the agent runs as you with no OTP needed, until you
     terminate the session from Telegram > Settings > Devices.

Credentials: read from .env in this folder (never hard-code, never commit):
    TG_API_ID=12345678
    TG_API_HASH=<your api_hash from https://my.telegram.org/apps>
"""
import asyncio
import getpass
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SESSION_NAME = str(HERE / "my_account")


def load_env() -> dict:
    env = {}
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


async def main() -> int:
    try:
        from pyrogram import Client
        from pyrogram import errors
    except ImportError:
        print("Pyrogram missing. Install: pip install pyrogram tgcrypto")
        return 1

    env = load_env()
    api_id_raw = os.environ.get("TG_API_ID") or env.get("TG_API_ID") or ""
    api_hash = os.environ.get("TG_API_HASH") or env.get("TG_API_HASH") or ""
    if not api_id_raw or not api_hash:
        print("PEHLE YE CHAHIYE: is folder ki .env file mein TG_API_ID aur TG_API_HASH daalo.")
        print("API ID tumhara ready hai: 12345678 (DonghuaMax app).")
        print("API Hash: https://my.telegram.org/apps par wahi app kholo, wahan dikhega.")
        print("API Hash ko chat mein mat bhejna - sirf .env file mein rakho (chmod 600).")
        return 2
    api_id = int(api_id_raw)

    phone = input("Apna Telegram number country code ke saath daalo (e.g. +91XXXXXXXXXX): ").strip().replace(" ", "")
    if not phone.startswith("+") or len(phone) < 8:
        print("Number galat lag raha hai - country code ke saath daalo, jaise +91...")
        return 2

    client = Client(SESSION_NAME, api_id=api_id, api_hash=api_hash)
    await client.connect()
    try:
        # Step 1: ask Telegram to send the login code to this number/account.
        sent = await client.send_code(phone)
        print("Code bhej diya gaya hai. Apne Telegram app mein official 'Telegram' chat kholo - wahan code aaya hoga.")

        # Step 2: user types the code here; sign in with the phone_code_hash.
        code = input("Wahi OTP / login code yahan daalo: ").strip().replace(" ", "")
        try:
            user = await client.sign_in(phone, sent.phone_code_hash, code)
        except errors.SessionPasswordNeeded:
            # Step 3 (only if 2-Step Verification is ON): hidden password entry.
            pwd = getpass.getpass("2-Step Verification ON hai - apna Telegram password daalo (hidden rahega): ")
            user = await client.check_password(password=pwd)
        except errors.PhoneCodeInvalid:
            print("Code galat hai. Ek baar phir fresh login chalao aur naya code daalo.")
            return 3
        except errors.PhoneCodeExpired:
            print("Code expire ho gaya. Dobara login chalao - naya code aayega.")
            return 3

        me = user if hasattr(user, "first_name") else await client.get_me()
        print("LOGIN HO GAYA - real account connect hai.")
        print(f"Account: {getattr(me, 'first_name', '')} (@{getattr(me, 'username', None) or 'no-username'}) id={me.id}")
    finally:
        await client.disconnect()

    # Lock the session file down: only this user can read it.
    for sess in HERE.glob("my_account.session*"):
        try:
            os.chmod(sess, 0o600)
        except OSError:
            pass
    print("Session file ban gayi: my_account.session (chmod 600). Ye file password jaisi hai - kisi ko mat dena.")
    print("Ab agent chalane ke liye:  python agent.py   (pehle Muse Bridge ON hona chahiye - README dekho)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
