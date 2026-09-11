# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added
- Deterministic AWS IPv4 GeoIP feed generator.
- Physical geography feeds for continents, countries, subdivisions, and localities.
- AWS Region and network border group feeds from `ip-ranges.json`.
- FortiGate external-resource examples.
- Automated validation and scheduled refresh workflows.
- Protected refresh pipeline that publishes generated feed changes through an automation branch and pull request.
- Automatic merge workflow that only merges validated feed-only PRs after the required `CI / test` check succeeds.

### Changed
- Scheduled refreshes no longer push generated feed updates directly to `main`.
- Automated refresh authentication now uses GitHub's short-lived `GITHUB_TOKEN`; no PAT or `FEED_BOT_TOKEN` repository secret is required.
- Automated CI is explicitly dispatched for the refresh branch, and post-merge CI is explicitly dispatched for `main`.
