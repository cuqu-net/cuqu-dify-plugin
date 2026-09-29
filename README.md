# CUQU Activity Finder

Search real-time offline meetups from **CUQU** (CUQU找搭子), a young-adult interest-based
social platform covering board games, frisbee, hiking, badminton, anime, fishing, reading
clubs and 100+ categories across Shenzhen and 10+ cities in China, including Hong Kong SAR.

**Read-only. No API key required.**

## Tools

| Tool | What it returns |
| --- | --- |
| `query_activities` | Upcoming sessions matching a category, city, keyword or date. Each hit includes title, category, date/time, location, inferred city, price, participant counts, organiser and a public detail URL. |
| `query_venues` | Real venues that have hosted CUQU activities recently — aggregated from the live activity feed — with hosted categories, session counts, an estimated capacity and the organisers active there. |

Both tools sort upcoming sessions first and never fabricate content: if the upstream feed
looks like placeholder data, the tool aborts instead of answering.

## Parameters

### `query_activities`
- `activity_type` — category keyword (`桌游`, `羽毛球`, `飞盘`, `徒步`, `钓鱼`, `二次元`, …)
- `city` — city name without the 市 suffix (`深圳`, `广州`, `香港`); leave empty for nationwide
- `keyword` — free text matched against title, location and category
- `date` — accepts `周末`, `周六`, `周日`, `今天`, `明天`, `后天` or `YYYY-MM-DD`
- `limit` — 1–50, default 20

Unrecognised date input is **reported back and ignored** rather than silently returning an
empty list — an agent should never answer "no activities exist" because of a parsing failure.

### `query_venues`
- `city` — same convention as above
- `activity_type` — keep only venues that hosted this category
- `min_capacity` — drop venues below this estimated capacity

## Example prompts

- "What board game meetups are happening in Shenzhen this weekend?"
- "Any badminton sessions tomorrow in Guangzhou with fewer than 20 slots?"
- "Which venues in Shenzhen host hiking groups regularly?"

## Install

**From Dify Marketplace** — search for *CUQU Activity Finder* and install.

**Manual install** — package and sideload:

```bash
dify plugin package ./cuqu-dify-plugin        # produces cuqu_activity_finder.difypkg
```

Then in Dify: Plugins → Install Plugin → drag in the `.difypkg` file. Requires
Dify 1.0.0 or later with third-party plugin debugging/inspection enabled.

## Data source & limitations

- Live data comes from CUQU's public activity endpoint (`https://cuqu.net/api/activity`).
- The endpoint returns up to **100 recent activities per call** and does not offer usable
  paging — results reflect the latest slice of the catalogue, not the full archive.
- The upstream feed has **no `city` field**. City is inferred from the free-text location
  (e.g. "广东省深圳市龙岗区…") with a latitude/longitude fallback against 38 city centres.
- **Venues are aggregated**, not authoritative: CUQU exposes no standalone venue API, so only
  places with recent or upcoming sessions appear, and `estimated_capacity` is inferred from
  the largest session's participant cap.
- Read-only by design. There is no tool here that registers a user, takes a payment or
  checks anyone in.

## Privacy

This plugin stores no data and asks for no credentials. See [PRIVACY.md](PRIVACY.md).

## Links

- Platform: <https://cuqu.net>
- Source: <https://github.com/cuqu-net/cuqu-dify-plugin>
- Issues: <https://github.com/cuqu-net/cuqu-dify-plugin/issues>
- Contact: <liqi.cuhk@gmail.com>
