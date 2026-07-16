#!/usr/bin/env bash
# Batch smoke runner for untested cloud-init configs
# Runs sequentially, one VM at a time, logs PASS/FAIL per config
set -euo pipefail

REPO_DIR="/home/ubuntu/.openclaw/workspace/cloud-init-collection"
HARNESS="$REPO_DIR/scripts/gozunga_smoke.py"
RESULTS_FILE="/tmp/smoke-batch-results.txt"

source ~/.config/openstack/openclaw.openrc

echo "=== Batch smoke run started $(date -Iseconds) ===" | tee "$RESULTS_FILE"

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

# --- Redis ---
run_smoke "$REPO_DIR/databases/ubuntu-redis.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/databases/rocky-redis.yaml" rocky-10 gp.small1 basic

# --- Proxy ---
run_smoke "$REPO_DIR/proxy/ubuntu-caddy-letsencrypt.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/proxy/rocky-caddy-letsencrypt.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/proxy/ubuntu-nginx-letsencrypt.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/proxy/rocky-nginx-letsencrypt.yaml" rocky-10 gp.small1 basic

# --- Networking ---
run_smoke "$REPO_DIR/networking/ubuntu-wireguard.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/networking/rocky-wireguard.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/networking/ubuntu-tailscale.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/networking/rocky-tailscale.yaml" rocky-10 gp.small1 basic

# --- k3s ---
run_smoke "$REPO_DIR/k8s/ubuntu-k3s.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/k8s/rocky-k3s.yaml" rocky-10 gp.small1 basic

# --- CI Runners ---
run_smoke "$REPO_DIR/ci/ubuntu-gitlab-runner.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/ci/rocky-gitlab-runner.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/ci/ubuntu-github-actions-runner.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/ci/rocky-github-actions-runner.yaml" rocky-10 gp.small1 basic

# --- Observability ---
run_smoke "$REPO_DIR/observability/ubuntu-netdata.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/observability/rocky-netdata.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/observability/ubuntu-prometheus-grafana.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/observability/rocky-prometheus-grafana.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/observability/ubuntu-librenms.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/observability/rocky-librenms.yaml" rocky-10 gp.medium1 basic

# --- Security ---
run_smoke "$REPO_DIR/security/ubuntu-vault.yaml" ubuntu-26.04 gp.small1 basic
run_smoke "$REPO_DIR/security/rocky-vault.yaml" rocky-10 gp.small1 basic
run_smoke "$REPO_DIR/security/ubuntu-wazuh-aio.yaml" ubuntu-26.04 gp.medium2 basic
run_smoke "$REPO_DIR/security/rocky-wazuh-aio.yaml" rocky-10 gp.medium2 basic

# --- Desktops (large, slow) ---
run_smoke "$REPO_DIR/desktop/ubuntu-xfce.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-xfce.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-gnome.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-gnome.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-kde.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-kde.yaml" rocky-10 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/ubuntu-mate.yaml" ubuntu-26.04 gp.medium1 basic
run_smoke "$REPO_DIR/desktop/rocky-mate.yaml" rocky-10 gp.medium1 basic

# --- GPU (needs GPU flavor) ---
run_smoke "$REPO_DIR/gpu/ubuntu26-nvidia-open-drivers.yaml" ubuntu-26.04 ac.nvidia_rtx2000pro1 basic

echo ""
echo "=== Batch smoke run finished $(date -Iseconds) ===" | tee -a "$RESULTS_FILE"
echo ""
echo "=== SUMMARY ==="
cat "$RESULTS_FILE"
