# cloud-init-collection

A collection of practical cloud-init configurations for [Gozunga Cloud](https://gozunga.com).

Paste any of these YAML files into **Cloud configuration** when launching an instance.

## Existing

| File | Purpose |
|------|---------|
| [`ubuntu26-with-cuda-and-opensource-nvidia-drivers.yaml`](./ubuntu26-with-cuda-and-opensource-nvidia-drivers.yaml) | Ubuntu 26 + open NVIDIA driver stack |
| [`coolify-ubuntu.yaml`](./coolify-ubuntu.yaml) | Install [Coolify](https://coolify.io) via official installer (matches [Gozunga Coolify guide](https://gozunga.com/technical-guides-and-how-tos/installing-coolify-on-gozunga-cloud)) |

## Docker Engine (official repos)

Uninstalls distro/default Docker packages first, then installs from Docker’s official repository.

| File | Distro |
|------|--------|
| [`docker/ubuntu-docker-official.yaml`](./docker/ubuntu-docker-official.yaml) | Ubuntu |
| [`docker/rocky-docker-official.yaml`](./docker/rocky-docker-official.yaml) | Rocky / RHEL-style |

## App runtimes / starters

Each app example is a self-contained first-boot provisioner: install toolchain, drop a minimal app, enable a systemd unit.

| Stack | Ubuntu | Rocky / RHEL-style | Port |
|-------|--------|--------------------|------|
| Laravel (PHP-FPM + Nginx) | [`apps/ubuntu-laravel-nginx.yaml`](./apps/ubuntu-laravel-nginx.yaml) | [`apps/rocky-laravel-nginx.yaml`](./apps/rocky-laravel-nginx.yaml) | 80 |
| Python FastAPI | [`apps/ubuntu-python-fastapi.yaml`](./apps/ubuntu-python-fastapi.yaml) | [`apps/rocky-python-fastapi.yaml`](./apps/rocky-python-fastapi.yaml) | 8000 |
| Go HTTP | [`apps/ubuntu-go-web.yaml`](./apps/ubuntu-go-web.yaml) | [`apps/rocky-go-web.yaml`](./apps/rocky-go-web.yaml) | 8080 |
| Rust (Axum) | [`apps/ubuntu-rust-web.yaml`](./apps/ubuntu-rust-web.yaml) | [`apps/rocky-rust-web.yaml`](./apps/rocky-rust-web.yaml) | 8080 |
| Next.js | [`apps/ubuntu-nextjs.yaml`](./apps/ubuntu-nextjs.yaml) | [`apps/rocky-nextjs.yaml`](./apps/rocky-nextjs.yaml) | 3000 |

## Notes

- **Security groups:** open only the ports you need (examples above). Gozunga instances deny inbound by default.
- **First boot time:** Coolify, Rust, and Next.js take longer (package download / compile).
- **Not production hardened:** these are starter templates. Add your own SSH hardening, TLS, secrets, and app config before real workloads.
- **Secrets:** do not put production passwords/API keys in cloud-init if the userdata is retained or shared; inject via secrets manager or first-login.

## Usage on Gozunga

1. Create instance in the [portal](https://portal.gozunga.com)
2. Choose Ubuntu or Rocky image
3. Paste the YAML under **Cloud configuration**
4. Attach a security group that allows the app port(s)
5. Wait for cloud-init to finish (`cloud-init status --wait` over SSH if you want to confirm)

## Contributing

PRs welcome — keep examples:

- Valid `#cloud-config`
- Distro-specific where package managers differ
- Idempotent enough for re-runs where practical
- Documented with a short header comment (what it does + ports)
