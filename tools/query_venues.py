"""query_venues — venues aggregated from CUQU's real activity feed.

CUQU has no standalone venue endpoint (/api/venue and friends all 404), so
instead of shipping a hard-coded venue list, we aggregate places that have
actually hosted recent or upcoming sessions. Real data, zero backend work.
"""
from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.cuqu_api import UpstreamError, guess_city, load_items, scan_mock_markers

NOTE = (
    "Venue records are aggregated from CUQU's real activity feed; the platform has no "
    "standalone venue API, so only places with recent or upcoming sessions appear."
)


class QueryVenuesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        city = str((tool_parameters.get("city") or "")).strip().rstrip("市")
        activity_type = str((tool_parameters.get("activity_type") or "")).strip()
        try:
            min_capacity = int(tool_parameters.get("min_capacity") or 0)
        except (TypeError, ValueError):
            min_capacity = 0

        try:
            items = load_items()
        except UpstreamError as exc:
            yield self.create_text_message(
                f"CUQU activity API is unavailable right now: {exc}. Please retry later."
            )
            return
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(f"Unexpected error querying CUQU venues: {exc}")
            return

        bad = scan_mock_markers(items)
        if bad:
            yield self.create_text_message(
                "Upstream returned suspicious placeholder data (ids: "
                + ", ".join(bad[:3])
                + "). Aborting rather than inventing venue records."
            )
            return

        now_ms = int(time.time() * 1000)
        venues: dict[str, dict[str, Any]] = {}
        for it in items:
            loc = str(it.get("location") or "").strip()
            if not loc:
                continue
            cat = str(it.get("type") or "")
            if activity_type and activity_type not in cat:
                continue
            c = str(it.get("city") or "")
            if city and not (c == city or city in loc):
                continue
            cap = int(it.get("max_participants") or 0)
            v = venues.get(loc)
            if v is None:
                v = {
                    "venue_name": loc,
                    "city": c,
                    "categories": [],
                    "activity_count": 0,
                    "upcoming_count": 0,
                    "estimated_capacity": 0,
                    "latest_activity": "",
                    "latest_start": 0,
                    "organizers": [],
                }
                venues[loc] = v
            v["activity_count"] += 1
            if cat and cat not in v["categories"]:
                v["categories"].append(cat)
            org = str(it.get("organizer") or "")
            if org and org not in v["organizers"]:
                v["organizers"].append(org)
            start = int(it.get("start_millis") or 0)
            if start >= now_ms:
                v["upcoming_count"] += 1
            v["estimated_capacity"] = max(v["estimated_capacity"], cap)
            if start >= v["latest_start"]:
                v["latest_start"] = start
                v["latest_activity"] = str(it.get("title") or "")

        records = []
        for v in venues.values():
            v["categories"] = v["categories"][:6]
            v["organizers"] = v["organizers"][:3]
            v.pop("latest_start", None)
            v["capacity_note"] = (
                "estimated_capacity is inferred from the largest session's participant cap, "
                "not an official venue capacity."
            )
            records.append(v)
        if min_capacity:
            records = [v for v in records if v["estimated_capacity"] >= min_capacity]
        records.sort(
            key=lambda v: (v["upcoming_count"], v["activity_count"]),
            reverse=True,
        )

        payload: dict[str, Any] = {
            "success": True,
            "total": len(records),
            "note": NOTE,
            "city": city or "全国",
            "venues": records[:30],
        }
        yield self.create_json_message(payload)
        yield self.create_text_message(self._render_text(payload))

    @staticmethod
    def _render_text(payload: dict[str, Any]) -> str:
        venues = payload.get("venues") or []
        if not venues:
            return f"No venues matched city={payload.get('city')}. {payload.get('note','')}"
        lines = [f"Found {payload['total']} venues (showing {len(venues)}) for city={payload.get('city')}:"]
        for v in venues:
            lines.append(
                f"- {v['venue_name']} [{v['city']}] | categories: {', '.join(v['categories']) or '-'} "
                f"| sessions {v['activity_count']} (upcoming {v['upcoming_count']}) "
                f"| est. capacity {v['estimated_capacity']} | latest: {v['latest_activity']}"
            )
        lines.append(payload.get("note", ""))
        return "\n".join(lines)
