# ADR 0004 — Site location is private config

**Status:** accepted
**Date:** 2026-10-17

## Context
StormSafe is built for one outdoor pool facility, and the code needs that site's location: it decides which lightning and weather data the model trains on and what each forecast covers. The repo is public, and a location published next to the owner's name can point to where they live. Nothing about the system depends on the location being public.

## Decision
- **Site config** is the facility's latitude, longitude, and time zone. It is never committed or published: not in code, docs, `.env.example`, tests, manifests, commit messages, PR text, or published artifacts.
- **Where it lives:**
  - On the owner's machine: the git-ignored `.env`.
  - In the cluster: a `stormsafe-site` Secret, created by hand, like other credentials.
  - In CI: nowhere. Tests use obviously fake values.
- `.env.example` lists the site keys with blank values. Settings refuse to load without them.
- Docs describe the site generically: *an outdoor pool facility within GOES-19 Geostationary Lightning Mapper coverage* (the Americas), which is the one real constraint on where the system can run.
- Experiment tracking (MLflow) stays local. The published model card describes the site without coordinates.
- **Guards:**
  - A test fails if any tracked file contains the site values from the local `.env`. It runs on the owner's machine; CI has no `.env` and skips it.
  - The `reviewer` persona flags site values in any diff.

## Consequences
- One extra setup step on a new machine and when building the cluster.
- Results can't be reproduced exactly without the site config; the data pipeline runs for any site within GLM coverage.
- The project reads as a reusable service for any site, not a one-off.
- Site config is human-only (`CLAUDE.md`).

## Alternatives considered
- **Publish the location:** rejected for the owner's privacy.
- **Publish a different, real location and use it instead:** workable, but the owner wants the system to serve the actual site.
- **Encrypted config in the repo (for example, SOPS):** key management overhead for three values.
