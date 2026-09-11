# Security Policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting/security advisory feature for this repository when available. Do not include credentials, customer data, private IP plans, or other secrets in public issues.

## Feed integrity

The generator accepts live data only from `https://ip-ranges.amazonaws.com`, validates TLS with the operating system trust store, restricts redirects to the same authoritative host, validates every emitted entry as canonical IPv4 CIDR, and publishes plain-text feeds without executable content.
