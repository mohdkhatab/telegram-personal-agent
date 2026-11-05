# Contributing to Telegram Personal Agent

Thanks for your interest in improving this project. Contributions of all
kinds are welcome — bug reports, fixes, features, and documentation.

## Before You Start

- Check the existing issues before opening a new one.
- For large changes, open an issue first and describe what you want to build,
  so the approach can be agreed before you write code.
- Never include real credentials in issues, PRs, logs, or screenshots:
  no `api_hash`, no OTP/login codes, no `.env`, and **never** a `.session`
  file. See [SECURITY.md](SECURITY.md).

## Development Setup

```bash
git clone <this-repo>
cd telegram-agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in YOUR OWN api_id / api_hash
chmod 600 .env
```

Use a spare/test Telegram account for development whenever possible.
Automated accounts can hit Telegram flood limits — test gently.

## Making Changes

1. Create a branch: `git checkout -b feature/my-change`
2. Make your change, keeping the code style below.
3. Test:
   - `python -m py_compile agent.py login_telethon.py` must pass.
   - Run the login flow and the agent against a test account and confirm a
     message is received, typing shows, and a reply is sent.
   - Confirm the agent still sends **nothing** when the bridge is down.
4. Commit with a clear message (see below) and open a pull request.

## Code Style

- Python 3.10+ compatible, `asyncio`-based, Telethon event handlers.
- Keep blocking work (like the HTTP call to the bridge) off the event loop
  (`asyncio.to_thread`).
- Secrets are read from the environment / `.env` only — never hard-code them,
  never print them, never write them to logs.
- Comments should explain *why*, not repeat *what* the code says.
- Keep replies' safety rules intact: bots ignored, no payments promised,
  identity rule (backup agent) preserved.

## Commit Messages

Use short, imperative messages:

```
Add retry backoff for bridge timeouts
Fix typing indicator not refreshing on long replies
Docs: explain whitelist mode in README
```

## Pull Requests

- Describe what changed and how you tested it.
- Keep PRs focused: one feature or fix per PR.
- Update `README.md` and `CHANGELOG.md` when behavior changes.
- A maintainer will review; changes may be requested before merging.

## Reporting Bugs

Open an issue with:

- What you expected, what actually happened
- Steps to reproduce
- Relevant log lines (**redact** phone numbers, codes, and credentials)
- Your Python and Telethon versions

## License

By contributing, you agree that your contributions will be licensed under
the [MIT License](LICENSE).
