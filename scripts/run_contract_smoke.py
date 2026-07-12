#!/usr/bin/env python3
"""Run a smoke contract YAML via gozunga_smoke.py."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - fallback parser for simple contracts
    yaml = None


def load_contract(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise SystemExit(f"contract must be a mapping: {path}")
        return data

    # Minimal fallback for simple key: value contracts (no nested structures needed)
    data: dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("- "):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val == "":
            continue
        if val.isdigit():
            data[key] = int(val)
        else:
            data[key] = val
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Gozunga smoke contract")
    parser.add_argument("contract", type=Path)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args(argv)

    contract_path = args.contract.resolve()
    if not contract_path.is_file():
        print(f"contract not found: {contract_path}", file=sys.stderr)
        return 2

    data = load_contract(contract_path)
    repo = args.repo_root.resolve()
    example = data.get("example")
    image = data.get("image")
    flavor = data.get("flavor")
    if not example or not image or not flavor:
        print("contract requires example, image, flavor", file=sys.stderr)
        return 2

    yaml_path = (repo / str(example)).resolve()
    smoke = (repo / "scripts" / "gozunga_smoke.py").resolve()
    cmd = [
        sys.executable,
        str(smoke),
        str(yaml_path),
        "--image",
        str(image),
        "--flavor",
        str(flavor),
        "--network",
        str(data.get("network") or "Internet"),
        "--keypair",
        str(data.get("keypair") or "openclaw-chester"),
        "--security-group",
        str(data.get("security_group") or "cloudinit-smoke"),
    ]
    if data.get("ssh_user"):
        cmd.extend(["--ssh-user", str(data["ssh_user"])])
    if data.get("probe"):
        cmd.extend(["--probe", str(data["probe"])])
    if data.get("cloud_init_timeout_seconds"):
        cmd.extend(["--cloud-init-timeout", str(data["cloud_init_timeout_seconds"])])

    print("exec:", " ".join(cmd), flush=True)
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
