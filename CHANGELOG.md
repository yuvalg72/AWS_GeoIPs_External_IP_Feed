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

### Changed
- Scheduled refreshes no longer push generated feed updates directly to `main`.
- Automated refresh authentication uses GitHub's short-lived `GITHUB_TOKEN`; no PAT or `FEED_BOT_TOKEN` repository secret is required.
- Automated CI is explicitly dispatched for the refresh branch, and post-merge CI is explicitly dispatched for `main`.
- The refresh workflow now waits for the exact dispatched CI run, verifies the successful `test` check on the automation commit, validates the PR contract and changed-file scope, and performs the guarded squash merge itself.
- Removed the separate `workflow_run` merge workflow because GitHub's recursive workflow suppression prevented that chain from firing when the upstream dispatch was created with `GITHUB_TOKEN`.
