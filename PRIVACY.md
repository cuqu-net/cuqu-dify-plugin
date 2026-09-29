# Privacy Policy — CUQU Activity Finder

Last updated: 2026-09-29

This document describes what the CUQU Activity Finder plugin for Dify does and does not do
with data. It applies to the plugin published as `cuqu_activity_finder` by author `cuqu-net`.

## No credentials are collected

The plugin requires **no API key, no login and no authorisation flow**. `credentials_for_provider`
is intentionally empty. The underlying CUQU activity endpoint is a public, read-only HTTP GET.

## What data leaves your Dify instance

When a tool is invoked, the plugin performs exactly one outbound request per call:

- **Request**: `GET https://cuqu.net/api/activity`
- **Payload**: none, apart from standard HTTP headers including our User-Agent
  (`cuqu-dify-plugin/<version>`)
- **What the parameters your LLM provides are used for**: `activity_type`, `city`, `keyword`
  and `date` are used **locally inside the plugin** to filter the response that was already
  downloaded. They are never sent to CUQU as separate queries, and no user identity,
  conversation content or workflow data is forwarded to CUQU.

CUQU's own operator may log this public request (IP address, User-Agent, timestamp) according
to its website policies. See <https://cuqu.net> for platform terms.

## What the plugin stores

Nothing. The plugin:

- holds no persistent storage (the `storage` permission is disabled in the manifest),
- writes no files outside its own runtime,
- keeps no caches between invocations — every call re-fetches live data.

## What this plugin never does

- It does **not** register users for activities, create orders, process payments or check
  anyone in. It is strictly read-only.
- It does **not** send personally identifiable information to third party services beyond
  the single anonymous GET request described above.

## Children's data and sensitive categories

The plugin does not knowingly collect personal information from anyone. It only returns
publicly published meetup metadata (titles, times, locations, prices, organiser display names).

## Contact

Questions or data requests:

- Email: <liqi.cuhk@gmail.com>
- Issue tracker: <https://github.com/cuqu-net/cuqu-dify-plugin/issues>

## Changes

If the behaviour above changes (for example, if a write tool is ever added), this document
will be updated together with the plugin version and the change will be visible in the
repository history.
