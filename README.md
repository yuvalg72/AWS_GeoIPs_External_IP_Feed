# AWS GeoIPs External IP Feed

Plain-text AWS IPv4 feeds designed for firewalls and other network devices that can consume external address lists, including FortiGate `config system external-resource`.

Each `.txt` feed contains exactly one canonical IPv4 CIDR per line, with no headers, comments, JSON, or CSV. This makes the files directly consumable in the same general model as Cloudflare's public IP feeds.

## Authoritative sources

The repository is generated from two AWS-published sources:

- `https://ip-ranges.amazonaws.com/geo-ip-feed.csv` for physical geolocation according to RFC 8805. AWS explicitly notes that this feed accounts for Local Zones, which can be physically located away from their parent AWS Region.
- `https://ip-ranges.amazonaws.com/ip-ranges.json` for AWS Region and `network_border_group` membership.

The generator never derives an AWS Region from a city, state, or country. Physical geography and AWS routing geography are kept as separate views because they are not equivalent.

## Feed model

```text
All AWS geolocated IPv4
├── continents
│   └── continent
│       └── country
│           └── subdivision
│               └── locality
├── AWS Regions
│   └── us-east-1, us-east-2, eu-west-1, ...
└── Network Border Groups
    └── us-east-1, us-east-1-atl-1, us-west-2-lax-1, ...
```

The repository exposes both short canonical paths for devices and a duplicated hierarchy for human browsing.

```text
feeds/ipv4/
├── all.txt
├── aws-published-all.txt
├── continents/<continent>.txt
├── countries/<CC>.txt
├── subdivisions/<CC-SUBDIVISION>.txt
├── localities/<CC>/<CC-SUBDIVISION>/<locality>.txt
├── aws-regions/<aws-region>.txt
├── network-border-groups/<network-border-group>.txt
├── hierarchy/<continent>/...
└── manifest.json
```

`all.txt` is the union of IPv4 prefixes present in the AWS geolocation feed. `aws-published-all.txt` is the union of IPv4 prefixes published in `ip-ranges.json`. The two files intentionally have different source semantics.

## Direct feed URLs

All AWS GeoIP IPv4:

```text
https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/all.txt
```

United States:

```text
https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/countries/US.txt
```

Ohio, United States (`US-OH`):

```text
https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/subdivisions/US-OH.txt
```

AWS Region `us-east-1`:

```text
https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/aws-regions/us-east-1.txt
```

AWS Network Border Group `us-west-2-lax-1`:

```text
https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/network-border-groups/us-west-2-lax-1.txt
```

## FortiGate examples

```fortios
config system external-resource
    edit "AWS_GeoIP_US"
        set status enable
        set type address
        set resource "https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/countries/US.txt"
        set refresh-rate 1440
        set server-identity-check full
        set comments "AWS Geographic IPs USA Only"
    next
    edit "AWS_GeoIP_US-OH"
        set status enable
        set type address
        set resource "https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/subdivisions/US-OH.txt"
        set refresh-rate 1440
        set server-identity-check full
        set comments "AWS Geographic IPs USA Ohio Only"
    next
    edit "AWS_GeoIP_US-EAST-1"
        set status enable
        set type address
        set resource "https://raw.githubusercontent.com/yuvalg72/AWS_GeoIPs_External_IP_Feed/main/feeds/ipv4/aws-regions/us-east-1.txt"
        set refresh-rate 1440
        set server-identity-check full
        set comments "AWS IP ranges for AWS Region us-east-1"
    next
end
```

A copy-ready configuration is also available at `examples/fortigate-external-resources.conf`.

## Generation and refresh

The project uses Python's standard library only. No third-party runtime packages are required.

```bash
python3 scripts/generate_feeds.py
python3 scripts/validate_feeds.py feeds/ipv4
```

The scheduled workflow checks the authoritative AWS sources every six hours and commits only when generated feed content changes. `manifest.json` records source hashes and the `ip-ranges.json` publication metadata so changes can be audited.

For offline testing or controlled builds:

```bash
python3 scripts/generate_feeds.py \
  --geo-file /path/to/geo-ip-feed.csv \
  --ranges-file /path/to/ip-ranges.json
```

## Safety and semantics

- IPv6 is intentionally excluded from `feeds/ipv4`.
- CIDRs are validated, de-duplicated, collapsed where safe within the same feed, and deterministically sorted.
- AWS Region membership comes only from the `region` field in `ip-ranges.json`.
- Local Zone-aware physical location comes only from `geo-ip-feed.csv`.
- Network Border Group feeds expose AWS's routing-location granularity for Local Zones and other border groups.
- If a new country appears before it is mapped to a continent, its country/subdivision/locality feeds are still generated and its hierarchy is placed under `unknown` so data is not silently dropped.
- AWS documents that `ip-ranges.json` does not cover every AWS service and does not include BYOIP ranges. Region/NBG feeds inherit those source limitations.
- `raw.githubusercontent.com` is a convenient public distribution endpoint, but it is not an AWS or firewall-vendor SLA. Critical environments may prefer to mirror the generated `.txt` feeds internally.

## Maintenance status

Active. The repository is intended to continuously regenerate and validate its public IPv4 feeds from the authoritative AWS sources every six hours.

## License

The generator code and repository documentation are licensed under the MIT License. AWS-published source data remains attributable to AWS and is not relicensed by this repository.
