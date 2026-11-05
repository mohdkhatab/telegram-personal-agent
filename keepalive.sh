#!/bin/bash
# Telegram Agent 24x7 keepalive: Muse Bridge (4010) + Telegram agent.
# - STOP file (~/workspace/telegram-agent/STOP) present ho to kuch mat karo.
# - Jo component down hai sirf wahi restart hoga.
# - Restart events keepalive.log mein, har check ka status last_check.txt mein (overwrite).
DIR=/home/hatch/workspace/telegram-agent
BRIDGE_DIR=/home/hatch/workspace/deepseek-harness/bridge
PY=/home/hatch/workspace/telegram-cdn/venv/bin/python

if [ -f "$DIR/STOP" ]; then
  echo "$(date -Is) STOP present - inactive by user order" > "$DIR/last_check.txt"
  exit 0
fi

exec 9>"$DIR/.keepalive.lock"
flock -n 9 || exit 0

status="OK"

if ! curl -s -m 4 http://127.0.0.1:4010/health 2>/dev/null | grep -q '"ok":true'; then
  (cd "$BRIDGE_DIR" && nohup node server.js >> bridge.log 2>&1 &)
  echo "$(date -Is) bridge was DOWN - restarted" >> "$DIR/keepalive.log"
  status="bridge-restarted"
  sleep 3
fi

if ! pgrep -f "venv/bin/python -u agent.py" > /dev/null; then
  (cd "$DIR" && nohup "$PY" -u agent.py >> agent.log 2>&1 < /dev/null &)
  echo "$(date -Is) agent was DOWN - restarted" >> "$DIR/keepalive.log"
  status="agent-restarted"
  sleep 6
fi

# Final verification, taaki cron ko sach pata chale
agent_ok=no; bridge_ok=no
pgrep -f "venv/bin/python -u agent.py" > /dev/null && agent_ok=yes
curl -s -m 4 http://127.0.0.1:4010/health 2>/dev/null | grep -q '"ok":true' && bridge_ok=yes
echo "$(date -Is) status=$status agent=$agent_ok bridge=$bridge_ok" > "$DIR/last_check.txt"
echo "agent=$agent_ok bridge=$bridge_ok status=$status"
