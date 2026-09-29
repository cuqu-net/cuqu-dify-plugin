"""query_activities — live search over CUQU's public activity feed.

Port of the same logic that backs the agent.cuqu.net MCP gateway (v1.7), so an
agent gets identical answers whichever transport it reaches us through.
"""
from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from utils.cuqu_api import UpstreamError, load_items, parse_date_filter, scan_mock_markers

DEFAULT_LIMIT = 20
MAX_LIMIT = 50


class QueryActivitiesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        activity_type = str((tool_parameters.get("activity_type") or "")).strip()
        city = str((tool_parameters.get("city") or "")).strip().rstrip("市")
        keyword = str((tool_parameters.get("keyword") or "")).strip()
        date_raw = tool_parameters.get("date")
        try:
            limit = int(tool_parameters.get("limit") or DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
        limit = max(1, min(limit, MAX_LIMIT))

        try:
            items = load_items()
        except UpstreamError as exc:
            yield self.create_text_message(
                f"CUQU activity API is unavailable right now: {exc}. Please retry later."
            )
            return
        except Exception as exc:  # noqa: BLE001
            yield self.create_text_message(f"Unexpected error querying CUQU: {exc}")
            return

        # 真实数据守护：一旦出现硬编码 demo 特征，宁可报错也不要让 agent 编造活动
        bad = scan_mock_markers(items)
        if bad:
            yield self.create_text_message(
                "Upstream returned suspicious placeholder data (ids: "
                + ", ".join(bad[:3])
                + "). Aborting so no fabricated activities are shown."
            )
            return

        df = parse_date_filter(date_raw)
        hits = items
        if activity_type:
            hits = [x for x in hits if activity_type in str(x.get("type") or "")]
        if df["mode"] == "in":
            hits = [x for x in hits if x.get("date") in df["set"]]
        if city:
            hits = [
                x
                for x in hits
                if str(x.get("city") or "") == city or city in str(x.get("location") or "")
            ]
        if keyword:
            hits = [
                x
                for x in hits
                if keyword in str(x.get("title") or "")
                or keyword in str(x.get("location") or "")
                or keyword in str(x.get("type") or "")
            ]

        now_ms = int(time.time() * 1000)
        upcoming = [x for x in hits if (x.get("start_millis") or 0) >= now_ms]
        shown_source = upcoming or hits

        breakdown: dict[str, int] = {}
        for x in upcoming:
            key = x.get("city") or "其他"
            breakdown[key] = breakdown.get(key, 0) + 1
        city_breakdown = [
            {"city": k, "upcoming_count": v}
            for k, v in sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)[:8]
        ]

        notes = [
            "Live data from the CUQU backend. Only upcoming sessions are returned by default; "
            "the upstream endpoint returns up to 100 activities per call with no paging.",
        ]
        if df["mode"] == "in":
            notes.append(f"Date '{df['label']}' resolved to concrete dates {', '.join(df['set'])}.")
        if df["mode"] == "invalid":
            notes.append(
                f"Date '{df['label']}' could not be parsed, so the date filter was ignored "
                "(accepted: 周末 / 周六 / 周日 / 今天 / 明天 / 后天 / YYYY-MM-DD)."
            )

        page = shown_source[:limit]
        payload: dict[str, Any] = {
            "success": True,
            "total": len(shown_source),
            "returned": len(page),
            "note": " ".join(notes),
            "city": city or "全国",
            "city_breakdown": city_breakdown,
            "items": page,
        }
        if not page:
            notes.append(
                "No match for these filters. Try clearing `date`, broadening `activity_type`, "
                "or switching city using `city_breakdown`."
            )
            payload["note"] = " ".join(notes)
            payload["args_echo"] = {
                k: v for k, v in tool_parameters.items() if v not in (None, "")
            }

        yield self.create_json_message(payload)
        yield self.create_text_message(self._render_text(payload))

    @staticmethod
    def _render_text(payload: dict[str, Any]) -> str:
        if not payload.get("items"):
            head = f"Found 0 activities for city={payload.get('city')}."
            cities = payload.get("city_breakdown") or []
            if cities:
                head += " Upcoming sessions available in: " + ", ".join(
                    f"{c['city']}({c['upcoming_count']})" for c in cities
                )
            return head + "\n" + payload.get("note", "")

        lines = [
            f"Found {payload['total']} matching activities (showing {payload['returned']}) "
            f"for city={payload.get('city')}:"
        ]
        for it in payload["items"]:
            lines.append(
                f"- {it.get('date')} ({it.get('weekday')}) {it.get('time')} | {it.get('title')} "
                f"| {it.get('type')} | {it.get('location')} [{it.get('city')}] "
                f"| ¥{it.get('price')} | {it.get('current_participants')}/{it.get('max_participants')} "
                f"| 主理人 {it.get('organizer')} | {it.get('url')}"
            )
        lines.append(payload.get("note", ""))
        return "\n".join(lines)
