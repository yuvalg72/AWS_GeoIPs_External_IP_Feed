#!/usr/bin/env python3
"""Validate generated IPv4 feed files for firewall consumption."""

from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path


def parse_feed(path: Path) -> list[ipaddress.IPv4Network]:
    raw_lines = path.read_text(encoding="ascii").splitlines()
    if not raw_lines:
        raise ValueError(f"Empty feed: {path}")
    networks: list[ipaddress.IPv4Network] = []
    seen: set[ipaddress.IPv4Network] = set()
    for line_number, line in enumerate(raw_lines, 1):
        if line != line.strip() or not line:
            raise ValueError(f"Whitespace/blank line in {path}:{line_number}")
        if line.startswith("#"):
            raise ValueError(f"Comments are not allowed in device feeds: {path}:{line_number}")
        try:
            network = ipaddress.ip_network(line, strict=True)
        except ValueError as exc:
            raise ValueError(f"Invalid canonical CIDR in {path}:{line_number}: {line}") from exc
        if network.version != 4:
            raise ValueError(f"IPv6 found in IPv4 feed {path}:{line_number}: {line}")
        if network in seen:
            raise ValueError(f"Duplicate CIDR in {path}: {line}")
        seen.add(network)
        networks.append(network)
    expected = sorted(networks, key=lambda net: (int(net.network_address), net.prefixlen))
    if networks != expected:
        raise ValueError(f"Feed is not deterministically sorted: {path}")
    return networks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("feeds/ipv4"))
    args = parser.parse_args()
    root = args.root
    if not root.is_dir():
        raise SystemExit(f"Feed root does not exist: {root}")

    txt_files = sorted(root.rglob("*.txt"))
    if not txt_files:
        raise SystemExit(f"No .txt feeds found under {root}")
    total_lines = 0
    for path in txt_files:
        total_lines += len(parse_feed(path))

    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise SystemExit("Unsupported or missing manifest schema_version")

    print(f"Validated {len(txt_files)} feed files with {total_lines} CIDR entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
