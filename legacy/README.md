# Legacy — Pyrogram route (deprecated)

These files are the first implementation, built on **Pyrogram**:

- `login.py` — interactive Pyrogram login
- `login_auto.py` — file-driven Pyrogram login driver
- `agent_pyrogram.py.bak` — the original Pyrogram agent

They are kept for reference only. On hosts where direct MTProto connections
are intercepted or garbled (for example, sandboxes that only allow HTTP
proxy egress), Pyrogram's auth handshake fails, which is why the project
moved to **Telethon + HTTP proxy** (`../agent.py`, `../login_telethon.py`).
Do not use these files for new deployments.
