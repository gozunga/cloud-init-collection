# cloud-init-collection

Practical `#cloud-config` examples for [Gozunga Cloud](https://gozunga.com).

Paste any YAML into **Cloud configuration** when launching an instance.

## Layout

```
coolify/     # PaaS installers
gpu/         # NVIDIA / CUDA-ish GPU setup
docker/      # Docker Engine from official repos
apps/        # Language/runtime app starters
desktop/     # Linux desktop environments + xrdp
```

## Coolify

| File | Purpose |
|------|---------|
| [`coolify/ubuntu.yaml`](./coolify/ubuntu.yaml) | Install [Coolify](https://coolify.io) via official installer (matches [Gozunga Coolify guide](https://gozunga.com/technical-guides-and-how-tos/installing-coolify-on-gozunga-cloud)) |

Open ports: `8000` (mgmt), optional `6001`/`6002`, plus `80`/`443` for apps.

## GPU

| File | Purpose |
|------|---------|
| [`gpu/ubuntu26-nvidia-open-drivers.yaml`](./gpu/ubuntu26-nvidia-open-drivers.yaml) | Ubuntu 26 + open NVIDIA driver stack + reboot |

## Docker Engine (official repos)

Uninstalls distro/default Docker packages first, then installs from Docker’s official repository.

| File | Distro |
|------|--------|
| [`docker/ubuntu-docker-official.yaml`](./docker/ubuntu-docker-official.yaml) | Ubuntu |
| [`docker/rocky-docker-official.yaml`](./docker/rocky-docker-official.yaml) | Rocky / Alma / RHEL-style |

## App runtimes / starters

Self-contained first-boot provisioners: toolchain + minimal app + systemd unit.

| Stack | Ubuntu | Rocky / RHEL-style | Port |
|-------|--------|--------------------|------|
| Laravel (PHP-FPM + Nginx) | [`apps/ubuntu-laravel-nginx.yaml`](./apps/ubuntu-laravel-nginx.yaml) | [`apps/rocky-laravel-nginx.yaml`](./apps/rocky-laravel-nginx.yaml) | 80 |
| Python FastAPI | [`apps/ubuntu-python-fastapi.yaml`](./apps/ubuntu-python-fastapi.yaml) | [`apps/rocky-python-fastapi.yaml`](./apps/rocky-python-fastapi.yaml) | 8000 |
| Go HTTP | [`apps/ubuntu-go-web.yaml`](./apps/ubuntu-go-web.yaml) | [`apps/rocky-go-web.yaml`](./apps/rocky-go-web.yaml) | 8080 |
| Rust (Axum) | [`apps/ubuntu-rust-web.yaml`](./apps/ubuntu-rust-web.yaml) | [`apps/rocky-rust-web.yaml`](./apps/rocky-rust-web.yaml) | 8080 |
| Next.js | [`apps/ubuntu-nextjs.yaml`](./apps/ubuntu-nextjs.yaml) | [`apps/rocky-nextjs.yaml`](./apps/rocky-nextjs.yaml) | 3000 |

## Desktop environments

Install a full GUI and enable **xrdp** (RDP on TCP/3389). First boot is large/slow — give it time, then reboot if needed.

| Desktop | Ubuntu | Rocky / Alma / RHEL-style |
|---------|--------|---------------------------|
| GNOME | [`desktop/ubuntu-gnome.yaml`](./desktop/ubuntu-gnome.yaml) | [`desktop/rocky-gnome.yaml`](./desktop/rocky-gnome.yaml) |
| XFCE (lighter) | [`desktop/ubuntu-xfce.yaml`](./desktop/ubuntu-xfce.yaml) | [`desktop/rocky-xfce.yaml`](./desktop/rocky-xfce.yaml) |
| KDE Plasma | [`desktop/ubuntu-kde.yaml`](./desktop/ubuntu-kde.yaml) | [`desktop/rocky-kde.yaml`](./desktop/rocky-kde.yaml) |
| MATE | [`desktop/ubuntu-mate.yaml`](./desktop/ubuntu-mate.yaml) | [`desktop/rocky-mate.yaml`](./desktop/rocky-mate.yaml) |

**Desktop notes**
- Open security group **TCP/3389** for xrdp (and **22** if you want SSH).
- These do **not** set a user password. Set one before RDP login, e.g. `sudo passwd ubuntu` / `sudo passwd rocky`.
- Prefer XFCE on small VMs; GNOME/KDE want more RAM/CPU/disk.
- RHEL-style group names can vary by release; scripts fall back to package installs when groups differ.
- Graphical cloud images still need a console path (xrdp, VNC, or portal console).

## Notes

- **Security groups:** Gozunga instances deny inbound by default — open only what you need.
- **First boot time:** Coolify, GPU drivers, Rust, Next.js, and full desktops can take many minutes.
- **Not production hardened:** starter templates. Add SSH hardening, TLS, secrets, and backups for real workloads.
- **Secrets:** avoid putting production passwords/API keys in userdata if it is retained or shared.

## Usage on Gozunga

1. Create instance in the [portal](https://portal.gozunga.com)
2. Choose Ubuntu or Rocky/Alma image
3. Paste the YAML under **Cloud configuration**
4. Attach a security group for the needed ports
5. Confirm with `cloud-init status --wait` over SSH if desired

## Other good future examples

Ideas if we expand further:

- Caddy or Nginx reverse proxy + Let’s Encrypt
- Postgres / Redis single-node starters
- GitLab Runner / GitHub Actions runner
- WireGuard or Tailscale exit node
- k3s single-node
- HashiCorp Vault dev/prod bootstrap
- Observability stack (Netdata, Prometheus + Grafana)
- Windows-style remote desktop alternatives (TigerVNC)
- TanStack Start / SvelteKit / Django

## Contributing

PRs welcome. Keep examples:

- Valid `#cloud-config`
- Distro-specific where package managers differ
- Header comments with purpose + ports
- Idempotent enough for re-runs where practical
