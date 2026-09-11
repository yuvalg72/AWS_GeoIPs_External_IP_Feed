#!/usr/bin/env python3
"""Generate FortiGate-friendly AWS IPv4 feeds from official AWS sources."""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import re
import shutil
import ssl
import sys
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Iterable

GEO_URL = "https://ip-ranges.amazonaws.com/geo-ip-feed.csv"
RANGES_URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"
EXPECTED_HOST = "ip-ranges.amazonaws.com"
MAX_SOURCE_BYTES = 25 * 1024 * 1024
USER_AGENT = "AWS_GeoIPs_External_IP_Feed/1.0 (+https://github.com/yuvalg72/AWS_GeoIPs_External_IP_Feed)"


def download(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != EXPECTED_HOST:
        raise ValueError(f"Refusing non-authoritative source URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        final = urllib.parse.urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != EXPECTED_HOST:
            raise ValueError(f"Unexpected redirect target: {response.geturl()}")
        data = response.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError(f"Source exceeded {MAX_SOURCE_BYTES} bytes: {url}")
    if not data:
        raise ValueError(f"Source returned no data: {url}")
    return data


def read_bytes(path: Path | None, url: str) -> bytes:
    return path.read_bytes() if path else download(url)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    result = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return result or "unknown"


def parse_ipv4(prefix: str) -> ipaddress.IPv4Network | None:
    try:
        network = ipaddress.ip_network(prefix.strip(), strict=False)
    except ValueError as exc:
        raise ValueError(f"Invalid CIDR: {prefix!r}") from exc
    if network.version != 4:
        return None
    return network


def collapse(networks: Iterable[ipaddress.IPv4Network]) -> list[ipaddress.IPv4Network]:
    unique = set(networks)
    return sorted(
        ipaddress.collapse_addresses(unique),
        key=lambda net: (int(net.network_address), net.prefixlen),
    )


def write_feed(path: Path, networks: Iterable[ipaddress.IPv4Network]) -> int:
    entries = collapse(networks)
    if not entries:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{network.with_prefixlen}\n" for network in entries), encoding="ascii")
    return len(entries)


def load_continent_map(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("country_continents.json must contain an object")
    return {str(k).upper(): slug(str(v)) for k, v in raw.items()}


def parse_geo(data: bytes):
    all_geo: set[ipaddress.IPv4Network] = set()
    countries: dict[str, set[ipaddress.IPv4Network]] = defaultdict(set)
    subdivisions: dict[str, set[ipaddress.IPv4Network]] = defaultdict(set)
    localities: dict[tuple[str, str, str], set[ipaddress.IPv4Network]] = defaultdict(set)

    text = data.decode("utf-8-sig")
    reader = csv.reader(text.splitlines())
    for line_number, row in enumerate(reader, 1):
        if not row or not any(field.strip() for field in row):
            continue
        if row[0].lstrip().startswith("#"):
            continue
        if len(row) < 4:
            raise ValueError(f"Geo feed line {line_number} has fewer than 4 columns: {row!r}")

        prefix, country, subdivision, locality = (field.strip() for field in row[:4])
        network = parse_ipv4(prefix)
        if network is None:
            continue
        country = country.upper()
        subdivision = subdivision.upper()
        if not country or not subdivision or not locality:
            raise ValueError(f"Geo feed line {line_number} has missing geography fields: {row!r}")

        all_geo.add(network)
        countries[country].add(network)
        subdivisions[subdivision].add(network)
        localities[(country, subdivision, locality)].add(network)

    if not all_geo:
        raise ValueError("Geo feed contained no IPv4 prefixes")
    return all_geo, countries, subdivisions, localities


def parse_ranges(data: bytes):
    document = json.loads(data.decode("utf-8"))
    prefixes = document.get("prefixes")
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError("ip-ranges.json has no prefixes array")

    all_published: set[ipaddress.IPv4Network] = set()
    aws_regions: dict[str, set[ipaddress.IPv4Network]] = defaultdict(set)
    border_groups: dict[str, set[ipaddress.IPv4Network]] = defaultdict(set)

    for entry in prefixes:
        if not isinstance(entry, dict):
            raise ValueError("Invalid entry in ip-ranges.json prefixes")
        prefix = entry.get("ip_prefix", "")
        region = str(entry.get("region", "")).strip()
        border_group = str(entry.get("network_border_group", "")).strip()
        network = parse_ipv4(prefix)
        if network is None:
            continue
        if not region or not border_group:
            raise ValueError(f"Missing region/network_border_group for {prefix}")
        all_published.add(network)
        aws_regions[region].add(network)
        border_groups[border_group].add(network)

    return document, all_published, aws_regions, border_groups


def generate(output: Path, geo_data: bytes, ranges_data: bytes | None, continent_map_path: Path) -> dict:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    continent_map = load_continent_map(continent_map_path)
    all_geo, countries, subdivisions, localities = parse_geo(geo_data)

    continents: dict[str, set[ipaddress.IPv4Network]] = defaultdict(set)
    unknown_countries: set[str] = set()
    for country, networks in countries.items():
        continent = continent_map.get(country, "unknown")
        if continent == "unknown":
            unknown_countries.add(country)
        continents[continent].update(networks)

    counts: dict[str, object] = {}
    counts["geo_all"] = write_feed(output / "all.txt", all_geo)
    counts["continents"] = {}
    for continent, networks in sorted(continents.items()):
        count = write_feed(output / "continents" / f"{continent}.txt", networks)
        counts["continents"][continent] = count
        write_feed(output / "hierarchy" / continent / "all.txt", networks)

    counts["countries"] = {}
    for country, networks in sorted(countries.items()):
        count = write_feed(output / "countries" / f"{country}.txt", networks)
        counts["countries"][country] = count
        continent = continent_map.get(country, "unknown")
        write_feed(output / "hierarchy" / continent / "countries" / country / "all.txt", networks)

    counts["subdivisions"] = {}
    country_for_subdivision: dict[str, str] = {}
    for country, subdivision, _ in localities:
        prior = country_for_subdivision.setdefault(subdivision, country)
        if prior != country:
            raise ValueError(f"Subdivision {subdivision} is associated with multiple countries")

    for subdivision, networks in sorted(subdivisions.items()):
        count = write_feed(output / "subdivisions" / f"{subdivision}.txt", networks)
        counts["subdivisions"][subdivision] = count
        country = country_for_subdivision[subdivision]
        continent = continent_map.get(country, "unknown")
        write_feed(output / "hierarchy" / continent / "countries" / country / "subdivisions" / subdivision / "all.txt", networks)

    counts["localities"] = {}
    seen_paths: dict[Path, str] = {}
    for (country, subdivision, locality), networks in sorted(localities.items()):
        locality_slug = slug(locality)
        relative = Path(country) / subdivision / f"{locality_slug}.txt"
        canonical_path = output / "localities" / relative
        prior = seen_paths.get(canonical_path)
        if prior is not None and prior != locality:
            digest = hashlib.sha256(locality.encode("utf-8")).hexdigest()[:8]
            locality_slug = f"{locality_slug}-{digest}"
            relative = Path(country) / subdivision / f"{locality_slug}.txt"
            canonical_path = output / "localities" / relative
        seen_paths[canonical_path] = locality
        count = write_feed(canonical_path, networks)
        counts["localities"][f"{country}/{subdivision}/{locality}"] = count
        continent = continent_map.get(country, "unknown")
        write_feed(output / "hierarchy" / continent / "countries" / country / "subdivisions" / subdivision / "localities" / f"{locality_slug}.txt", networks)

    manifest: dict[str, object] = {
        "schema_version": 1,
        "sources": {"geo_ip_feed": {"url": GEO_URL, "sha256": sha256(geo_data)}},
        "counts": counts,
        "unknown_country_codes": sorted(unknown_countries),
    }

    if ranges_data is not None:
        document, all_published, aws_regions, border_groups = parse_ranges(ranges_data)
        counts["aws_published_all"] = write_feed(output / "aws-published-all.txt", all_published)
        counts["aws_regions"] = {}
        for region, networks in sorted(aws_regions.items()):
            counts["aws_regions"][region] = write_feed(output / "aws-regions" / f"{slug(region)}.txt", networks)
        counts["network_border_groups"] = {}
        for border_group, networks in sorted(border_groups.items()):
            counts["network_border_groups"][border_group] = write_feed(output / "network-border-groups" / f"{slug(border_group)}.txt", networks)
        manifest["sources"]["ip_ranges"] = {
            "url": RANGES_URL,
            "sha256": sha256(ranges_data),
            "sync_token": document.get("syncToken"),
            "create_date": document.get("createDate"),
        }

    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geo-file", type=Path, help="Use a local geo-ip-feed.csv instead of downloading")
    parser.add_argument("--ranges-file", type=Path, help="Use a local ip-ranges.json instead of downloading")
    parser.add_argument("--skip-ranges", action="store_true", help="Generate physical geography feeds only and skip AWS Region/NBG feeds")
    parser.add_argument("--output", type=Path, default=Path("feeds/ipv4"))
    parser.add_argument("--continent-map", type=Path, default=Path("data/country_continents.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    geo_data = read_bytes(args.geo_file, GEO_URL)
    ranges_data = None if args.skip_ranges else read_bytes(args.ranges_file, RANGES_URL)
    manifest = generate(args.output, geo_data, ranges_data, args.continent_map)
    print(json.dumps({"status": "ok", "counts": manifest["counts"]}, sort_keys=True))
    if manifest["unknown_country_codes"]:
        print("WARNING: unmapped country codes placed under continent 'unknown': " + ", ".join(manifest["unknown_country_codes"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
