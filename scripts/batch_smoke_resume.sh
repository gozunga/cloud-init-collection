#!/usr/bin/env bash
# Resume batch: retries fixed failures + remaining untested items from batch_smoke.sh
set -euo pipefail

REPO_DIR="/home/ubuntu/.openclaw/workspace/cloud-init-collection"
HARNESS="$REPO_DIR/scripts/gozunga_smoke.py"
RESULTS_FILE="/tmp/smoke-resume-results.txt"

source ~/.config/openstack/openclaw.openrc

echo "=== Resume smoke run started $(date -Iseconds) ===" | tee "$RESULTS_FILE"

run_smoke() {
    local yaml="$1"
    local image="$2"
    local flavor="${3:-gp.small1}"
    local probe="${4:-basic}"
    local label
    label=$(echo "$yaml" | sed "s|$REPO_DIR/||")

    echo ""
    echo "========================================"
    echo "TESTING: $label (image=$image, flavor=$flavor, probe=$probe)"
    echo "========================================"

    local log_file="/tmp/smoke-$(echo "$label" | tr '/' '-').log"

    if python3 -u "$HARNESS" "$yaml" \
        --image "$image" \
        --flavor "$flavor" \
        --probe "$probe" \
        --skip-ensure \
        2>&1 | tee "$log_file"; then
        echo "PASS $label" | tee -a "$RESULTS_FILE"
    else
        echo "FAIL $label" | tee -a "$RESULTS_FILE"
    fi
}

# === RETRIES / FIXED FAILURES ===
echo ""
echo "### RETRIES (fixed or likely-transient failures) ###"

# rocky-redis: was package name "redis" (doesn't exist on Rocky 10); fixed to use valkey
run_smoke "$REPO_DIR/databases/rocky-redis.yaml" rocky-10 gp.small1 basic

# ubuntu-caddy: runcmd failure — likely transient network; retest
run_smoke "$REPO_DIR/proxy/ubuntu-caddy-letsencrypt.yaml" ubuntu-26.04 gp.small1 basic

# rocky-nginx: missing EPEL for certbot packages; fixed with bootcmd epel-release
run_smoke "$REPO_DIR/proxy/rocky-nginx-letsencrypt.yaml" rocky-10 gp.small1 basic

# rocky-wireguard: runcmd failure with iptables PostUp on Rocky 10; fixed to use nftables + bootcmd EPEL
run_smoke "$REPO_DIR/networking/rocky-wireguard.yaml" rocky-10 gp.small1 basic

# rocky-netdata: SSH timeout (no route to host) — likely transient; retest
run_smoke "$REPO_DIR/observability/rocky-netdata.yaml" rocky-10 gp.small1 basic

# === NEW: REMAINING ITEMS FROM batch_smoke.sh ===
echo ""
echo "### NEW: Observability ###"
run_smoke "$REPO_DIR/observability/ubuntu-prometheus-grafana.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/observability/rocky-prometheus-grafana.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/observability/ubuntu-librenms.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/observability/rocky-librenms.yaml" rocky-10 gp.medium1 basic

echo ""
echo "### NEW: Security ###"
run_smoke "$REPO_DIR/security/ubuntu-vault.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/security/rocky-vault.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/security/ubuntu-wazuh-aio.yaml" ubuntu-26.04 gp.medium2 basic
run_smoke "$REPO_DIR/security/rocky-wazuh-aio.yaml" rocky-10 gp.medium2 basic

echo ""
echo "### NEW: Desktops (slow — install full DE) ###"
run_smoke "$REPO_DIR/desktop/ubuntu-xfce.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-xfce.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-gnome.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-gnome.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-kde.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-kde.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-mate.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-mate.yaml" rocky-10 gp.medium1 basic

echo ""
echo "=== Resume smoke run finished $(date -Iseconds) ===" | tee -a "$RESULTS_FILE"
echo ""
echo "=== SUMMARY ==="
cat "$RESULTS_FILE"
