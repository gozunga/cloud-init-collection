#!/usr/bin/env python3
"""Gozunga OpenStack cloud-init smoke harness.

Creates a temporary server with user-data from an example YAML, waits for
ACTIVE + SSH, runs cloud-init status --wait and example-specific probes, then
always deletes the server.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_NETWORK = "Internet"
DEFAULT_KEYPAIR = "openclaw-chester"
DEFAULT_SECURITY_GROUP = "cloudinit-smoke"
DEFAULT_SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")
DEFAULT_CLOUD_INIT_TIMEOUT = 20 * 60
DEFAULT_SSH_READY_TIMEOUT = 15 * 60
DEFAULT_ACTIVE_TIMEOUT = 10 * 60
STATUS_FILE = Path("/tmp/gozunga-smoke-status.txt")


class SmokeError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_status(message: str) -> None:
    line = f"{utc_now()} {message}"
    print(f"[status] {message}", flush=True)
    try:
        with STATUS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def run(
    cmd: Sequence[str],
    *,
    check: bool = True,
    capture: bool = True,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    pretty = " ".join(shlex.quote(c) for c in cmd)
    write_status(f"run: {pretty}")
    try:
        return subprocess.run(
            list(cmd),
            check=check,
            capture_output=capture,
            text=True,
            timeout=timeout,
            env=env,
            input=input_text,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        raise SmokeError(
            f"command timed out after {timeout}s: {pretty}\n{stdout}\n{stderr}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        if check:
            raise SmokeError(
                f"command failed ({exc.returncode}): {pretty}\n"
                f"stdout:\n{exc.stdout or ''}\nstderr:\n{exc.stderr or ''}"
            ) from exc
        return subprocess.CompletedProcess(
            args=exc.cmd,
            returncode=exc.returncode,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
        )


def openstack(
    args: Sequence[str],
    *,
    check: bool = True,
    timeout: int = 120,
    json_out: bool = False,
) -> str | dict | list:
    cmd = ["openstack", *args]
    # Avoid duplicating -f json when callers already requested it.
    has_json_format = False
    for i, token in enumerate(cmd[:-1]):
        if token in {"-f", "--format"} and cmd[i + 1] == "json":
            has_json_format = True
            break
    if json_out and not has_json_format:
        cmd.extend(["-f", "json"])
    result = run(cmd, check=check, timeout=timeout)
    out = (result.stdout or "").strip()
    if json_out:
        if not out:
            return {}
        return json.loads(out)
    return out


def ensure_local_pubkey_matches(keypair: str, pubkey_path: Path) -> None:
    if not pubkey_path.is_file():
        raise SmokeError(f"public key not found: {pubkey_path}")
    local = run(
        ["ssh-keygen", "-E", "md5", "-lf", str(pubkey_path)],
        timeout=30,
    ).stdout.strip()
    # Example: 256 MD5:dd:38:... comment (ED25519)
    m = re.search(r"MD5:([0-9a-f:]+)", local)
    if not m:
        raise SmokeError(f"could not parse local key fingerprint: {local}")
    local_fp = m.group(1)
    remote = openstack(["keypair", "show", keypair, "-c", "fingerprint", "-f", "value"], timeout=60)
    if not isinstance(remote, str) or not remote.strip():
        raise SmokeError(f"keypair missing: {keypair}")
    if remote.strip() != local_fp:
        raise SmokeError(
            f"keypair {keypair} fingerprint {remote.strip()} != local {local_fp}"
        )


def ensure_security_group(name: str) -> None:
    groups = openstack(["security", "group", "list", "-f", "json"], json_out=True, timeout=60)
    assert isinstance(groups, list)
    existing = {g.get("Name") for g in groups}
    if name not in existing:
        write_status(f"creating security group {name}")
        openstack(
            [
                "security",
                "group",
                "create",
                name,
                "--description",
                "Cloud-init smoke tests (SSH + common app ports)",
            ],
            timeout=60,
        )

    rules = openstack(
        ["security", "group", "rule", "list", name, "-f", "json"],
        json_out=True,
        timeout=60,
    )
    assert isinstance(rules, list)

    def has_rule(protocol: str, port: int | None = None) -> bool:
        for rule in rules:
            if str(rule.get("IP Protocol") or "").lower() != protocol:
                continue
            if str(rule.get("Direction") or "").lower() not in {"", "ingress"}:
                # openstack json often omits Direction or uses Ingress
                direction = str(rule.get("Direction") or "ingress").lower()
                if direction not in {"ingress", "none", ""}:
                    continue
            remote = str(rule.get("Remote IP Prefix") or rule.get("IP Range") or "")
            if remote and remote not in {"0.0.0.0/0", "None", "none"}:
                # still allow if empty / none; required remote is 0.0.0.0/0
                if remote != "0.0.0.0/0":
                    continue
            if protocol == "icmp":
                return True
            port_range = str(rule.get("Port Range") or "")
            if port is None:
                continue
            if port_range in {str(port), f"{port}:{port}"}:
                return True
        return False

    # Re-check using value listing too (format differences)
    value_list = openstack(
        ["security", "group", "rule", "list", name, "-f", "value"],
        timeout=60,
    )
    value_text = value_list if isinstance(value_list, str) else ""

    def ensure_tcp(port: int) -> None:
        if f"tcp" in value_text and f"{port}:{port}" in value_text:
            return
        if has_rule("tcp", port):
            return
        write_status(f"adding SG rule TCP {port}")
        openstack(
            [
                "security",
                "group",
                "rule",
                "create",
                name,
                "--ingress",
                "--protocol",
                "tcp",
                "--dst-port",
                str(port),
                "--remote-ip",
                "0.0.0.0/0",
            ],
            timeout=60,
        )

    def ensure_udp(port: int) -> None:
        if "udp" in value_text and f"{port}:{port}" in value_text:
            return
        if has_rule("udp", port):
            return
        write_status(f"adding SG rule UDP {port}")
        openstack(
            [
                "security",
                "group",
                "rule",
                "create",
                name,
                "--ingress",
                "--protocol",
                "udp",
                "--dst-port",
                str(port),
                "--remote-ip",
                "0.0.0.0/0",
            ],
            timeout=60,
        )

    def ensure_icmp() -> None:
        if "icmp" in value_text:
            return
        if has_rule("icmp"):
            return
        write_status("adding SG rule ICMP")
        openstack(
            [
                "security",
                "group",
                "rule",
                "create",
                name,
                "--ingress",
                "--protocol",
                "icmp",
                "--remote-ip",
                "0.0.0.0/0",
            ],
            timeout=60,
        )

    for port in (22, 80, 443, 3000, 8000, 8080, 9090, 19999):
        ensure_tcp(port)
    ensure_udp(51820)
    ensure_icmp()


def guess_ssh_user(image: str, yaml_path: Path) -> str:
    blob = f"{image} {yaml_path.as_posix()}".lower()
    if "rocky" in blob or "alma" in blob or "rhel" in blob or "centos" in blob:
        return "rocky"
    if "ubuntu" in blob or "debian" in blob:
        return "ubuntu"
    return "ubuntu"


def guess_probe_profile(yaml_path: Path) -> str:
    name = yaml_path.as_posix().lower()
    if "docker" in name:
        return "docker"
    if "postgres" in name:
        return "postgres"
    return "basic"


def unique_server_name(yaml_path: Path, image: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    base = re.sub(r"[^a-zA-Z0-9-]+", "-", yaml_path.stem.lower()).strip("-")
    img = re.sub(r"[^a-zA-Z0-9-]+", "-", image.lower()).strip("-")
    name = f"smoke-{base}-{img}-{stamp}"
    return name[:60].rstrip("-")


def create_server(
    *,
    name: str,
    image: str,
    flavor: str,
    network: str,
    keypair: str,
    security_group: str,
    user_data: Path,
) -> str:
    write_status(f"creating server {name}")
    out = openstack(
        [
            "server",
            "create",
            name,
            "--image",
            image,
            "--flavor",
            flavor,
            "--network",
            network,
            "--key-name",
            keypair,
            "--security-group",
            security_group,
            "--user-data",
            str(user_data),
            "--wait",
            "-f",
            "json",
        ],
        timeout=DEFAULT_ACTIVE_TIMEOUT + 120,
        json_out=True,
    )
    assert isinstance(out, dict)
    server_id = str(out.get("id") or "")
    if not server_id:
        # some openstack versions nest differently; fetch by name
        show = openstack(["server", "show", name, "-f", "json"], json_out=True, timeout=60)
        assert isinstance(show, dict)
        server_id = str(show.get("id") or "")
    if not server_id:
        raise SmokeError(f"failed to resolve server id for {name}")
    write_status(f"server created id={server_id}")
    return server_id


def wait_server_active(server_id: str, timeout: int = DEFAULT_ACTIVE_TIMEOUT) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        show = openstack(["server", "show", server_id, "-f", "json"], json_out=True, timeout=60)
        assert isinstance(show, dict)
        status = str(show.get("status") or "")
        if status != last:
            write_status(f"server status={status}")
            last = status
        if status == "ACTIVE":
            return show
        if status in {"ERROR", "DELETED"}:
            raise SmokeError(f"server entered {status}: {json.dumps(show, indent=2)}")
        time.sleep(5)
    raise SmokeError(f"timeout waiting for ACTIVE (last={last})")


def extract_public_ipv4(server: dict) -> str:
    addresses = server.get("addresses") or server.get("Addresses")
    candidates: list[str] = []

    if isinstance(addresses, dict):
        for _net, vals in addresses.items():
            if isinstance(vals, list):
                for item in vals:
                    if isinstance(item, dict):
                        addr = item.get("addr") or item.get("address")
                        version = item.get("version") or item.get("OS-EXT-IPS:type")
                        if addr and "." in str(addr):
                            candidates.append(str(addr))
                    elif isinstance(item, str) and "." in item:
                        candidates.append(item)
            elif isinstance(vals, str):
                # formats like "Internet=1.2.3.4" or just IP
                for part in re.split(r"[,;\s]+", vals):
                    part = part.split("=")[-1]
                    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", part):
                        candidates.append(part)
    elif isinstance(addresses, str):
        for m in re.finditer(r"\b\d+\.\d+\.\d+\.\d+\b", addresses):
            candidates.append(m.group(0))

    # Fallback: openstack server show -c addresses -f value
    if not candidates:
        raw = openstack(
            ["server", "show", str(server.get("id")), "-c", "addresses", "-f", "value"],
            timeout=60,
        )
        if isinstance(raw, str):
            for m in re.finditer(r"\b\d+\.\d+\.\d+\.\d+\b", raw):
                candidates.append(m.group(0))

    # Prefer public-looking non-RFC1918 if available, else first
    def is_private(ip: str) -> bool:
        return (
            ip.startswith("10.")
            or ip.startswith("192.168.")
            or bool(re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", ip))
        )

    public = [ip for ip in candidates if not is_private(ip)]
    chosen = (public or candidates)
    if not chosen:
        raise SmokeError(f"no IPv4 found in addresses: {addresses!r}")
    return chosen[0]


def ssh_base(ip: str, user: str, identity: str) -> list[str]:
    return [
        "ssh",
        "-i",
        identity,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=12",
        f"{user}@{ip}",
    ]


def wait_for_ssh(ip: str, user: str, identity: str, timeout: int = DEFAULT_SSH_READY_TIMEOUT) -> None:
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        proc = run(
            ssh_base(ip, user, identity) + ["echo", "ssh-ready"],
            check=False,
            timeout=30,
        )
        if proc.returncode == 0 and "ssh-ready" in (proc.stdout or ""):
            write_status(f"ssh ready as {user}@{ip}")
            return
        last_err = (proc.stderr or proc.stdout or "").strip()
        write_status(f"ssh not ready yet: {last_err[:200]}")
        time.sleep(10)
    raise SmokeError(f"SSH not ready within {timeout}s for {user}@{ip}: {last_err}")


def ssh_run(
    ip: str,
    user: str,
    identity: str,
    remote_cmd: str,
    *,
    timeout: int,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run(
        ssh_base(ip, user, identity) + [remote_cmd],
        check=check,
        timeout=timeout,
    )


def run_probes(profile: str, ip: str, user: str, identity: str, cloud_init_timeout: int) -> list[str]:
    logs: list[str] = []

    write_status("waiting for cloud-init status --wait")
    # cloud-init may need root; use sudo -n
    cmd = f"sudo -n cloud-init status --wait --long || sudo -n cloud-init status --wait"
    proc = ssh_run(ip, user, identity, cmd, timeout=cloud_init_timeout, check=False)
    logs.append(f"$ {cmd}\nrc={proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    if proc.returncode != 0:
        write_status(f"cloud-init wait rc={proc.returncode} stderr={repr((proc.stderr or '')[:200])}")
        # cloud-init status --wait may have been interrupted by a power_state
        # reboot (cloud-init finishes, then VM reboots for e.g. kernel upgrade).
        # Strategy: probe SSH -- if it is down the VM is mid-reboot; wait for it
        # to come back, then re-check cloud-init status.  If SSH is already up
        # and cloud-init shows done/degraded, accept it.  Otherwise fail.
        write_status("cloud-init wait returned non-zero; probing for reboot")
        time.sleep(5)  # brief pause -- reboot may be in progress
        probe = run(
            ssh_base(ip, user, identity) + ["echo", "ssh-probe"],
            check=False, timeout=15,
        )
        if probe.returncode != 0 or "ssh-probe" not in (probe.stdout or ""):
            # SSH is down -- likely mid-reboot
            write_status("SSH down after cloud-init wait; waiting for reboot recovery")
            time.sleep(15)
            wait_for_ssh(ip, user, identity, timeout=DEFAULT_SSH_READY_TIMEOUT)
        # (Re-)check cloud-init status now that SSH is up
        recheck = ssh_run(
            ip, user, identity,
            "sudo -n cloud-init status --long || cloud-init status --long || true",
            timeout=120, check=False,
        )
        logs.append(f"recheck cloud-init status:\nrc={recheck.returncode}\n{recheck.stdout}\n{recheck.stderr}")
        write_status(f"recheck rc={recheck.returncode} stdout={repr((recheck.stdout or '')[:300])}")
        recheck_text = (recheck.stdout or "").lower()
        if re.search(r"^status:\s*(done|degraded)", recheck_text, re.M):
            write_status("cloud-init completed (confirmed after reconnect)")
            proc = recheck  # fall through to normal status evaluation
        else:
            # Genuine failure -- gather diagnostics
            diag = ssh_run(
                ip,
                user,
                identity,
                "sudo -n cloud-init status --long || true; "
                "sudo -n tail -n 200 /var/log/cloud-init-output.log || true; "
                "sudo -n tail -n 100 /var/log/cloud-init.log || true",
                timeout=120,
                check=False,
            )
            logs.append(f"diagnostics:\n{diag.stdout}\n{diag.stderr}")
            raise SmokeError("cloud-init status --wait failed")

    status_proc = ssh_run(
        ip,
        user,
        identity,
        "sudo -n cloud-init status --long || cloud-init status --long || true",
        timeout=60,
        check=False,
    )
    logs.append(f"cloud-init status:\n{status_proc.stdout}\n{status_proc.stderr}")
    status_text = f"{status_proc.stdout}\n{status_proc.stderr}"
    status_l = status_text.lower()
    if re.search(r"^status:\s*error\b", status_l, re.M):
        raise SmokeError(f"cloud-init finished with error\n{status_proc.stdout}")
    # Rocky/OpenStack often reports recoverable hostname warnings as degraded.
    # Treat pure recoverable hostname noise as acceptable; other degraded is fail.
    if "degraded" in status_l:
        recoverable_only = True
        # Prefer structured recoverable_errors section when present.
        if "recoverable_errors:" in status_l:
            after = status_text.split("recoverable_errors:", 1)[1]
            # Cut at next top-level-ish key if present.
            after = re.split(r"\n(?=\S)", after, maxsplit=1)[0]
            bad_lines = []
            for line in after.splitlines():
                s = line.strip()
                if not s or s.endswith(":") or s in {"-", "[]"}:
                    continue
                if "failed to non-persistently adjust the system hostname" in s.lower():
                    continue
                if s.lower() in {"warning:", "error:", "critical:"}:
                    continue
                bad_lines.append(s)
            recoverable_only = not bad_lines
        else:
            recoverable_only = (
                "failed to non-persistently adjust the system hostname" in status_l
                and "traceback" not in status_l
            )
        if recoverable_only:
            write_status("cloud-init degraded only due to recoverable hostname warnings; continuing")
        else:
            raise SmokeError(f"cloud-init finished degraded\n{status_proc.stdout}")

    if profile == "docker":
        write_status("running docker probes")
        # wait briefly for docker group / service settle
        for attempt in range(1, 13):
            ver = ssh_run(
                ip,
                user,
                identity,
                "sudo -n docker version",
                timeout=120,
                check=False,
            )
            logs.append(f"docker version attempt {attempt}:\nrc={ver.returncode}\n{ver.stdout}\n{ver.stderr}")
            if ver.returncode == 0:
                break
            time.sleep(10)
        else:
            raise SmokeError("docker version failed")

        hello = ssh_run(
            ip,
            user,
            identity,
            "sudo -n docker run --rm hello-world",
            timeout=300,
            check=False,
        )
        logs.append(f"docker hello-world:\nrc={hello.returncode}\n{hello.stdout}\n{hello.stderr}")
        if hello.returncode != 0:
            raise SmokeError("docker run --rm hello-world failed")
        if "Hello from Docker" not in (hello.stdout or ""):
            # some locales / versions still succeed; require success code primarily
            write_status("hello-world output missing expected banner; rc=0 so accepting")
    elif profile == "postgres":
        write_status("running postgres probes")
        # Check PostgreSQL is running and responding
        ver = ssh_run(
            ip, user, identity,
            "sudo -u postgres psql -c 'SELECT version()'",
            timeout=60, check=False,
        )
        logs.append(f"postgres version:\nrc={ver.returncode}\n{ver.stdout}\n{ver.stderr}")
        if ver.returncode != 0:
            raise SmokeError("psql SELECT version() failed")
        if "PostgreSQL" not in (ver.stdout or ""):
            raise SmokeError("psql output missing PostgreSQL version string")
        write_status("PostgreSQL responding")

        # Verify the app database was created
        appdb = ssh_run(
            ip, user, identity,
            "sudo -u postgres psql -d app -c 'SELECT current_database()'",
            timeout=60, check=False,
        )
        logs.append(f"postgres app db:\nrc={appdb.returncode}\n{appdb.stdout}\n{appdb.stderr}")
        if appdb.returncode != 0:
            raise SmokeError("psql connect to app database failed")
        if "app" not in (appdb.stdout or ""):
            raise SmokeError("app database not found in psql output")
        write_status("app database verified")

        # Verify the app role exists
        role = ssh_run(
            ip, user, identity,
            "sudo -u postgres psql -c \"SELECT rolname FROM pg_roles WHERE rolname='app'\"",
            timeout=60, check=False,
        )
        logs.append(f"postgres app role:\nrc={role.returncode}\n{role.stdout}\n{role.stderr}")
        if role.returncode != 0 or "app" not in (role.stdout or ""):
            raise SmokeError("app role not found")
        write_status("app role verified")
    else:
        write_status("running basic probes")
        basic = ssh_run(ip, user, identity, "uname -a && uptime", timeout=60, check=False)
        logs.append(f"basic:\nrc={basic.returncode}\n{basic.stdout}\n{basic.stderr}")
        if basic.returncode != 0:
            raise SmokeError("basic probe failed")

    return logs


def delete_server(server_id: str | None, name: str | None) -> None:
    target = server_id or name
    if not target:
        return
    write_status(f"deleting server {target}")
    try:
        openstack(["server", "delete", str(target), "--wait"], check=False, timeout=300)
    except SmokeError as exc:
        write_status(f"delete wait issue: {exc}")
    # confirm gone
    for _ in range(30):
        proc = run(
            ["openstack", "server", "show", str(target)],
            check=False,
            timeout=60,
        )
        if proc.returncode != 0:
            write_status(f"server {target} deleted")
            return
        time.sleep(5)
    write_status(f"WARNING: server {target} may still exist")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Gozunga cloud-init live smoke harness")
    p.add_argument("yaml_path", type=Path, help="Path to cloud-init YAML example")
    p.add_argument("--image", required=True, help="OpenStack image name")
    p.add_argument("--flavor", required=True, help="OpenStack flavor name")
    p.add_argument("--network", default=DEFAULT_NETWORK)
    p.add_argument("--keypair", default=DEFAULT_KEYPAIR)
    p.add_argument("--security-group", default=DEFAULT_SECURITY_GROUP)
    p.add_argument("--ssh-identity", default=DEFAULT_SSH_KEY)
    p.add_argument("--ssh-user", default=None, help="Override SSH username")
    p.add_argument("--name", default=None, help="Override server name")
    p.add_argument("--cloud-init-timeout", type=int, default=DEFAULT_CLOUD_INIT_TIMEOUT)
    p.add_argument("--ssh-timeout", type=int, default=DEFAULT_SSH_READY_TIMEOUT)
    p.add_argument("--probe", default=None, choices=["docker", "postgres", "basic"], help="Probe profile")
    p.add_argument(
        "--skip-ensure",
        action="store_true",
        help="Skip keypair/SG ensure checks",
    )
    p.add_argument(
        "--keep-on-failure",
        action="store_true",
        help="Do not delete server on failure (debug only)",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    yaml_path: Path = args.yaml_path.resolve()
    if not yaml_path.is_file():
        print(f"FAIL: yaml not found: {yaml_path}", file=sys.stderr)
        return 2

    server_name = args.name or unique_server_name(yaml_path, args.image)
    ssh_user = args.ssh_user or guess_ssh_user(args.image, yaml_path)
    profile = args.probe or guess_probe_profile(yaml_path)
    identity = os.path.expanduser(args.ssh_identity)

    server_id: str | None = None
    ip: str | None = None
    logs: list[str] = []
    failed: Exception | None = None

    write_status(
        f"START smoke yaml={yaml_path} image={args.image} flavor={args.flavor} "
        f"name={server_name} user={ssh_user} profile={profile}"
    )

    try:
        if not args.skip_ensure:
            # identity is private key; public key is sibling .pub
            pub = Path(identity + ".pub")
            if not pub.is_file():
                pub = Path(os.path.expanduser("~/.ssh/id_ed25519.pub"))
            ensure_local_pubkey_matches(args.keypair, pub)
            ensure_security_group(args.security_group)

        server_id = create_server(
            name=server_name,
            image=args.image,
            flavor=args.flavor,
            network=args.network,
            keypair=args.keypair,
            security_group=args.security_group,
            user_data=yaml_path,
        )
        server = wait_server_active(server_id)
        ip = extract_public_ipv4(server)
        write_status(f"public ipv4={ip}")
        wait_for_ssh(ip, ssh_user, identity, timeout=args.ssh_timeout)
        logs.extend(run_probes(profile, ip, ssh_user, identity, args.cloud_init_timeout))
        write_status("PROBES PASSED")
        print("=" * 72)
        print(f"PASS server={server_name} id={server_id} ip={ip} yaml={yaml_path.name}")
        print("=" * 72)
        for chunk in logs:
            print(chunk)
            print("-" * 40)
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level smoke harness
        failed = exc
        write_status(f"FAIL: {exc}")
        print("=" * 72)
        print(
            f"FAIL server={server_name} id={server_id} ip={ip} yaml={yaml_path.name}: {exc}"
        )
        print("=" * 72)
        traceback.print_exc()
        for chunk in logs:
            print(chunk)
            print("-" * 40)
        return 1
    finally:
        if failed and args.keep_on_failure:
            write_status(f"keeping server on failure: {server_name} ({server_id})")
        else:
            delete_server(server_id, server_name)
        write_status(f"END smoke name={server_name} result={'FAIL' if failed else 'PASS'}")


if __name__ == "__main__":
    sys.exit(main())
