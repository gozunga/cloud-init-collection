#!/usr/bin/env bash
# Sequential single-VM smoke helper
# Usage: one_smoke.sh <app> <distro> <image> <user> <port> <user-data-yaml>
set -u
source ~/.config/openstack/openclaw.openrc

APP="$1"
DISTRO="$2"
IMAGE="$3"
SSH_USER="$4"
PORT="$5"
USERDATA="$6"

NAME="smoke-${APP}-${DISTRO}-$(date -u +%Y%m%d%H%M%S)"
echo "=== START $APP/$DISTRO name=$NAME image=$IMAGE port=$PORT ==="

# ensure clean
LEFTOVERS=$(openstack server list -f value -c ID -c Name | awk '/smoke-/ {print $1}')
if [ -n "${LEFTOVERS:-}" ]; then
  echo "Deleting leftovers: $LEFTOVERS"
  openstack server delete $LEFTOVERS --wait || true
fi

CREATE_JSON=$(openstack server create \
  --image "$IMAGE" \
  --flavor gp.small1 \
  --network Internet \
  --key-name openclaw-chester \
  --security-group cloudinit-smoke \
  --user-data "$USERDATA" \
  "$NAME" -f json)
SERVER_ID=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$CREATE_JSON")
echo "SERVER_ID=$SERVER_ID"

cleanup() {
  echo "CLEANUP $SERVER_ID"
  openstack server delete "$SERVER_ID" --wait 2>/dev/null || openstack server delete "$SERVER_ID" 2>/dev/null || true
}
trap cleanup EXIT

IP=""
STATUS=""
for i in $(seq 1 60); do
  INFO=$(openstack server show "$SERVER_ID" -f json)
  STATUS=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$INFO")
  IP=$(python3 - <<'PY' "$INFO"
import json,sys
d=json.loads(sys.argv[1])
ips=[]
for k,v in (d.get("addresses") or {}).items():
  if isinstance(v,list):
    for x in v:
      if isinstance(x,dict) and x.get("addr"):
        ips.append(x["addr"])
      elif isinstance(x,str):
        ips.append(x)
print(ips[0] if ips else "")
PY
)
  echo "[boot $i] status=$STATUS ip=${IP:-}"
  if [ "$STATUS" = "ACTIVE" ] && [ -n "$IP" ]; then break; fi
  if [ "$STATUS" = "ERROR" ]; then
    echo "$INFO"
    echo "RESULT FAIL create-error"
    exit 0
  fi
  sleep 5
done

if [ "$STATUS" != "ACTIVE" ] || [ -z "$IP" ]; then
  echo "RESULT FAIL no-active-ip"
  exit 0
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=4"
SSH_READY=0
for i in $(seq 1 24); do
  if ssh $SSH_OPTS "$SSH_USER@$IP" 'echo SSH_OK' 2>/dev/null; then
    SSH_READY=1
    break
  fi
  echo "[ssh $i] waiting"
  sleep 15
done
if [ "$SSH_READY" != "1" ]; then
  echo "RESULT FAIL ssh-timeout"
  exit 0
fi

# Wait cloud-init up to 20 min, tolerate temporary SSH blips during package upgrades
CI_STATUS="unknown"
CI_DONE=0
for i in $(seq 1 80); do
  CI_OUT=$(ssh $SSH_OPTS "$SSH_USER@$IP" 'sudo cloud-init status 2>&1 || true' 2>&1 || true)
  CI_STATUS=$(echo "$CI_OUT" | grep -E '^status:' | head -1 | awk '{print $2}')
  echo "[ci $i] status=${CI_STATUS:-ssh-or-error}"
  if echo "${CI_STATUS:-}" | grep -qiE '^(done|error|degraded)$'; then
    CI_DONE=1
    break
  fi
  # if SSH is down, wait and retry (dnf/apt upgrade can bounce services)
  if ! ssh $SSH_OPTS "$SSH_USER@$IP" 'true' 2>/dev/null; then
    echo "[ci $i] ssh blip; sleeping"
  fi
  sleep 15
done

if [ "$CI_DONE" != "1" ]; then
  echo "cloud-init not finished after wait; capturing log tail if possible"
  ssh $SSH_OPTS "$SSH_USER@$IP" 'sudo tail -150 /var/log/cloud-init-output.log; echo ---; sudo cloud-init status --long 2>&1 | head -40' 2>&1 || true
fi

if echo "${CI_STATUS:-}" | grep -qiE 'error'; then
  echo "--- cloud-init error log ---"
  ssh $SSH_OPTS "$SSH_USER@$IP" 'sudo tail -150 /var/log/cloud-init-output.log' 2>&1 || true
fi

# HTTP poll up to ~3 min (9 * 20s)
HTTP_CODE="000"
for i in $(seq 1 9); do
  HTTP_CODE=$(curl -sL -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 15 "http://$IP:$PORT" || true)
  echo "[http $i] code=$HTTP_CODE"
  if [ "$HTTP_CODE" = "200" ]; then break; fi
  sleep 20
done

BODY_SNIP=""
if [ "$HTTP_CODE" = "200" ]; then
  BODY_SNIP=$(curl -sL --max-time 15 "http://$IP:$PORT" | head -50)
  echo "--- body head ---"
  echo "$BODY_SNIP"
else
  echo "--- diagnostics ---"
  ssh $SSH_OPTS "$SSH_USER@$IP" "sudo cloud-init status --long 2>&1 | head -40; echo ===; sudo ss -lntp 2>/dev/null | head -40; echo ===; sudo systemctl --failed --no-pager 2>/dev/null | head -20; echo ===; sudo tail -100 /var/log/cloud-init-output.log" 2>&1 || true
fi

# PASS criteria: cloud-init done/degraded + HTTP 200
if echo "${CI_STATUS:-}" | grep -qiE '^(done|degraded)$' && [ "$HTTP_CODE" = "200" ]; then
  RESULT=PASS
elif [ "$HTTP_CODE" = "200" ] && [ "$CI_DONE" = "1" ] && echo "${CI_STATUS:-}" | grep -qiE '^(done|degraded)$'; then
  RESULT=PASS
else
  # If cloud-init wait never got stable status but HTTP 200 and final status is done/degraded, pass
  FINAL_CI=$(ssh $SSH_OPTS "$SSH_USER@$IP" 'sudo cloud-init status 2>&1 || true' 2>&1 || true)
  FINAL_STATUS=$(echo "$FINAL_CI" | grep -E '^status:' | head -1 | awk '{print $2}')
  if echo "${FINAL_STATUS:-}" | grep -qiE '^(done|degraded)$' && [ "$HTTP_CODE" = "200" ]; then
    CI_STATUS="$FINAL_STATUS"
    RESULT=PASS
  else
    RESULT=FAIL
  fi
fi

echo "SUMMARY app=$APP distro=$DISTRO ci=${CI_STATUS:-unknown} http=$HTTP_CODE result=$RESULT"
echo "RESULT $APP $DISTRO $RESULT $HTTP_CODE ci=${CI_STATUS:-unknown}"
# trap cleans up
exit 0
