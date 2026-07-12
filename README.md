# cloud-init-collection

Practical `#cloud-config` examples for [Gozunga Cloud](https://gozunga.com).

Paste any YAML into **Cloud configuration** when launching an instance.

## Layout

```
coolify/        # PaaS installers
gpu/            # NVIDIA / GPU driver setup
docker/         # Docker Engine (official repos)
apps/           # Language/runtime app starters
desktop/        # Linux desktop environments + xrdp
proxy/          # Caddy / Nginx reverse proxies
databases/      # Postgres / Redis single-node
ci/             # GitLab Runner / GitHub Actions runner
networking/     # WireGuard / Tailscale
k8s/            # k3s single-node
security/       # HashiCorp Vault bootstrap
observability/  # Netdata / Prometheus+Grafana
```

## Coolify

| File | Purpose |
|------|---------|
| [`coolify/ubuntu.yaml`](./coolify/ubuntu.yaml) | Install [Coolify](https://coolify.io) via official installer (matches [Gozunga Coolify guide](https://gozunga.com/technical-guides-and-how-tos/installing-coolify-on-gozunga-cloud)) |

Ports: `8000` (mgmt), optional `6001`/`6002`, plus `80`/`443` for apps.

## GPU

| File | Purpose |
|------|---------|
| [`gpu/ubuntu26-nvidia-open-drivers.yaml`](./gpu/ubuntu26-nvidia-open-drivers.yaml) | Ubuntu 26 + open NVIDIA driver stack + reboot |

## Docker Engine (official repos)

Uninstalls distro Docker packages first, then installs from Docker’s official repository.

| File | Distro |
|------|--------|
| [`docker/ubuntu-docker-official.yaml`](./docker/ubuntu-docker-official.yaml) | Ubuntu |
| [`docker/rocky-docker-official.yaml`](./docker/rocky-docker-official.yaml) | Rocky / Alma / RHEL-style |

## App runtimes / starters

| Stack | Ubuntu | Rocky / RHEL-style | Port |
|-------|--------|--------------------|------|
| Laravel (PHP-FPM + Nginx) | [`apps/ubuntu-laravel-nginx.yaml`](./apps/ubuntu-laravel-nginx.yaml) | [`apps/rocky-laravel-nginx.yaml`](./apps/rocky-laravel-nginx.yaml) | 80 |
| Python FastAPI | [`apps/ubuntu-python-fastapi.yaml`](./apps/ubuntu-python-fastapi.yaml) | [`apps/rocky-python-fastapi.yaml`](./apps/rocky-python-fastapi.yaml) | 8000 |
| Django + Gunicorn | [`apps/ubuntu-django.yaml`](./apps/ubuntu-django.yaml) | [`apps/rocky-django.yaml`](./apps/rocky-django.yaml) | 8000 |
| Go HTTP | [`apps/ubuntu-go-web.yaml`](./apps/ubuntu-go-web.yaml) | [`apps/rocky-go-web.yaml`](./apps/rocky-go-web.yaml) | 8080 |
| Rust (Axum) | [`apps/ubuntu-rust-web.yaml`](./apps/ubuntu-rust-web.yaml) | [`apps/rocky-rust-web.yaml`](./apps/rocky-rust-web.yaml) | 8080 |
| Next.js | [`apps/ubuntu-nextjs.yaml`](./apps/ubuntu-nextjs.yaml) | [`apps/rocky-nextjs.yaml`](./apps/rocky-nextjs.yaml) | 3000 |
| SvelteKit | [`apps/ubuntu-sveltekit.yaml`](./apps/ubuntu-sveltekit.yaml) | [`apps/rocky-sveltekit.yaml`](./apps/rocky-sveltekit.yaml) | 3000 |
| TanStack Start | [`apps/ubuntu-tanstack-start.yaml`](./apps/ubuntu-tanstack-start.yaml) | [`apps/rocky-tanstack-start.yaml`](./apps/rocky-tanstack-start.yaml) | 3000 |

## Desktop environments

Install a full GUI and enable **xrdp** (RDP on TCP/3389). First boot is large/slow.

| Desktop | Ubuntu | Rocky / Alma / RHEL-style |
|---------|--------|---------------------------|
| GNOME | [`desktop/ubuntu-gnome.yaml`](./desktop/ubuntu-gnome.yaml) | [`desktop/rocky-gnome.yaml`](./desktop/rocky-gnome.yaml) |
| XFCE (lighter) | [`desktop/ubuntu-xfce.yaml`](./desktop/ubuntu-xfce.yaml) | [`desktop/rocky-xfce.yaml`](./desktop/rocky-xfce.yaml) |
| KDE Plasma | [`desktop/ubuntu-kde.yaml`](./desktop/ubuntu-kde.yaml) | [`desktop/rocky-kde.yaml`](./desktop/rocky-kde.yaml) |
| MATE | [`desktop/ubuntu-mate.yaml`](./desktop/ubuntu-mate.yaml) | [`desktop/rocky-mate.yaml`](./desktop/rocky-mate.yaml) |

Desktop notes: set a password before RDP; open TCP/3389; prefer XFCE on small VMs.

## Reverse proxy

| File | Notes |
|------|-------|
| [`proxy/ubuntu-caddy-letsencrypt.yaml`](./proxy/ubuntu-caddy-letsencrypt.yaml) / [`proxy/rocky-caddy-letsencrypt.yaml`](./proxy/rocky-caddy-letsencrypt.yaml) | Caddy auto-HTTPS; edit Caddyfile domain/backend |
| [`proxy/ubuntu-nginx-letsencrypt.yaml`](./proxy/ubuntu-nginx-letsencrypt.yaml) / [`proxy/rocky-nginx-letsencrypt.yaml`](./proxy/rocky-nginx-letsencrypt.yaml) | Nginx + Certbot; run certbot after DNS |

Ports: `80`, `443`.

## Databases

| File | Notes |
|------|-------|
| [`databases/ubuntu-postgres.yaml`](./databases/ubuntu-postgres.yaml) / [`databases/rocky-postgres.yaml`](./databases/rocky-postgres.yaml) | Postgres, DB/user `app` / password `CHANGE_ME` |
| [`databases/ubuntu-redis.yaml`](./databases/ubuntu-redis.yaml) / [`databases/rocky-redis.yaml`](./databases/rocky-redis.yaml) | Redis localhost + `requirepass CHANGE_ME` |

## CI runners

| File | Notes |
|------|-------|
| [`ci/ubuntu-gitlab-runner.yaml`](./ci/ubuntu-gitlab-runner.yaml) / [`ci/rocky-gitlab-runner.yaml`](./ci/rocky-gitlab-runner.yaml) | GitLab Runner + Docker; register with token |
| [`ci/ubuntu-github-actions-runner.yaml`](./ci/ubuntu-github-actions-runner.yaml) / [`ci/rocky-github-actions-runner.yaml`](./ci/rocky-github-actions-runner.yaml) | Actions runner binaries; configure with short-lived token |

## Networking

| File | Notes |
|------|-------|
| [`networking/ubuntu-wireguard.yaml`](./networking/ubuntu-wireguard.yaml) / [`networking/rocky-wireguard.yaml`](./networking/rocky-wireguard.yaml) | WireGuard server scaffold, UDP/51820 |
| [`networking/ubuntu-tailscale.yaml`](./networking/ubuntu-tailscale.yaml) / [`networking/rocky-tailscale.yaml`](./networking/rocky-tailscale.yaml) | Tailscale install; `tailscale up` with auth key |

## Kubernetes

| File | Notes |
|------|-------|
| [`k8s/ubuntu-k3s.yaml`](./k8s/ubuntu-k3s.yaml) / [`k8s/rocky-k3s.yaml`](./k8s/rocky-k3s.yaml) | Single-node k3s; kubeconfig copied for default user |

## Security

| File | Notes |
|------|-------|
| [`security/ubuntu-vault.yaml`](./security/ubuntu-vault.yaml) / [`security/rocky-vault.yaml`](./security/rocky-vault.yaml) | Vault single-node bootstrap on `:8200` (TLS off — not prod HA) |
| [`security/ubuntu-wazuh-aio.yaml`](./security/ubuntu-wazuh-aio.yaml) / [`security/rocky-wazuh-aio.yaml`](./security/rocky-wazuh-aio.yaml) | Wazuh all-in-one (indexer+server+dashboard); dashboard HTTPS `:443` |

## Observability

| File | Notes |
|------|-------|
| [`observability/ubuntu-netdata.yaml`](./observability/ubuntu-netdata.yaml) / [`observability/rocky-netdata.yaml`](./observability/rocky-netdata.yaml) | Netdata UI `:19999` |
| [`observability/ubuntu-prometheus-grafana.yaml`](./observability/ubuntu-prometheus-grafana.yaml) / [`observability/rocky-prometheus-grafana.yaml`](./observability/rocky-prometheus-grafana.yaml) | Prometheus `:9090`, Grafana `:3000` (admin/admin) |
| [`observability/ubuntu-librenms.yaml`](./observability/ubuntu-librenms.yaml) / [`observability/rocky-librenms.yaml`](./observability/rocky-librenms.yaml) | LibreNMS Docker stack UI `:8000` (+ syslog 514, SNMP traps 162) |

## Notes

- **Security groups:** Gozunga instances deny inbound by default — open only what you need.
- **First boot time:** desktops, Coolify, GPU drivers, Rust, Node scaffolds, LibreNMS, and Wazuh AIO can take many minutes (Wazuh often 10–20+).
- **Not production hardened:** starter templates. Change default passwords, enable TLS, and restrict access.
- **Secrets:** avoid putting long-lived production secrets in userdata.

## Usage on Gozunga

1. Create instance in the [portal](https://portal.gozunga.com)
2. Choose Ubuntu or Rocky/Alma image
3. Paste the YAML under **Cloud configuration**
4. Attach a security group for the needed ports
5. Confirm with `cloud-init status --wait` over SSH if desired

## Contributing

PRs welcome. Keep examples:

- Valid `#cloud-config`
- Distro-specific where package managers differ
- Header comments with purpose + ports
- Idempotent enough for re-runs where practical
