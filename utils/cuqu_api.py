"""Shared client + normalisation logic for the CUQU Dify plugin.

Everything in this module is dependency-light and side-effect free except
:func:`fetch_activities`, which performs one HTTPS GET against CUQU's public
activity API. Keeping the logic here (rather than inside the Tool classes)
means we can unit-test it locally without booting a Dify runtime.

Data source: https://cuqu.net/api/activity  (public, no key, returns the
latest ~100 activities in one shot; there is no usable paging parameter).
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

import requests

API_URL = "https://cuqu.net/api/activity"
CN_TZ = timezone(timedelta(hours=8))
UA = "cuqu-dify-plugin/0.0.1 (+https://cuqu.net)"
DEFAULT_TIMEOUT = 20

# [城市名, 纬度, 经度, 半径km] —— 与 agent.cuqu.net 网关同一张表，保持跨端口径一致
CITY_TABLE = [
    ["深圳", 22.5431, 114.0579, 30], ["香港", 22.3193, 114.1694, 22], ["广州", 23.1291, 113.2644, 35],
    ["东莞", 23.0207, 113.7518, 25], ["惠州", 23.1117, 114.4168, 30], ["佛山", 23.0215, 113.1218, 25],
    ["珠海", 22.2710, 113.5767, 25], ["澳门", 22.1987, 113.5439, 10], ["中山", 22.5218, 113.3923, 20],
    ["北京", 39.9042, 116.4074, 60], ["上海", 31.2304, 121.4737, 50], ["成都", 30.5728, 104.0668, 45],
    ["重庆", 29.5630, 106.5516, 50], ["杭州", 30.2741, 120.1551, 35], ["武汉", 30.5928, 114.3055, 35],
    ["西安", 34.3416, 108.9398, 40], ["南京", 32.0603, 118.7969, 35], ["苏州", 31.2989, 120.5853, 30],
    ["长沙", 28.2282, 112.9388, 30], ["天津", 39.3434, 117.3616, 40], ["郑州", 34.7466, 113.6254, 35],
    ["青岛", 36.0671, 120.3826, 30], ["厦门", 24.4798, 118.0894, 25], ["福州", 26.0745, 119.2965, 25],
    ["昆明", 25.0389, 102.7183, 30], ["贵阳", 26.6470, 106.6302, 25], ["南宁", 22.8170, 108.3665, 30],
    ["沈阳", 41.8057, 123.4315, 35], ["大连", 38.9140, 121.6147, 30], ["哈尔滨", 45.8038, 126.5349, 35],
    ["济南", 36.6512, 117.1201, 30], ["合肥", 31.8206, 117.2272, 30], ["南昌", 28.6820, 115.8579, 30],
    ["海口", 20.0444, 110.1999, 25], ["无锡", 31.4912, 120.3119, 25], ["宁波", 29.8683, 121.5440, 25],
]

MOCK_MARKERS = ("act_00", "act_01", "act_02", "小趣")


class UpstreamError(Exception):
    """Raised when the CUQU activity API is unreachable or returns bad shape."""


# --------------------------------------------------------------------------- #
# Geo helpers
# --------------------------------------------------------------------------- #
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def guess_city(location, latitude=None, longitude=None) -> str:
    """Text match wins; otherwise nearest city centre within its radius.

    The upstream API has no ``city`` field — ``location`` is free text in two
    shapes ("广东省深圳市龙岗区…" or a bare landmark like "车公庙").
    """
    loc = str(location or "")
    for name, _lat, _lng, _r in CITY_TABLE:
        if name in loc:
            return name
    if not latitude or not longitude:
        return ""
    best, best_ratio = "", float("inf")
    for name, clat, clng, radius in CITY_TABLE:
        ratio = haversine_km(float(latitude), float(longitude), clat, clng) / radius
        if ratio < best_ratio:
            best_ratio, best = ratio, name
    return best if best_ratio <= 1 else ""


# --------------------------------------------------------------------------- #
# Date parsing (mirrors the gateway's "never silently return empty" rule)
# --------------------------------------------------------------------------- #
def sh_date_str(offset_days: int = 0) -> str:
    d = datetime.now(CN_TZ) + timedelta(days=offset_days)
    return d.strftime("%Y-%m-%d")


def _weekday_of(date_str: str) -> int:
    # 0=周日 6=周六
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d.weekday() + 1) % 7


def _future_weekday(wd: int) -> list:
    for i in range(14):
        ds = sh_date_str(i)
        if _weekday_of(ds) == wd:
            return [ds]
    return []


def parse_date_filter(raw) -> dict:
    """Return ``{"mode": "none"|"in"|"invalid", "set": [...], "label": str}``.

    Unrecognised input -> mode ``invalid`` -> the caller **drops the filter**
    and says so in its note. Silently returning zero hits is the one thing an
    LLM-facing tool must never do.
    """
    s = str(raw or "").strip()
    if not s:
        return {"mode": "none", "set": [], "label": ""}
    if re.search(r"周末|礼拜末", s):
        dates = []
        for i in range(14):
            ds = sh_date_str(i)
            wd = _weekday_of(ds)
            if wd == 6:
                dates = [ds, sh_date_str(i + 1)]
                break
            if wd == 0:
                dates = [ds]
                break
        dates = list(dict.fromkeys(dates))
        return {"mode": "in", "set": dates, "label": f"{s}({'、'.join(dates)})"}
    if "六" in s:
        dates = _future_weekday(6)
        return {"mode": "in", "set": dates, "label": f"{s}({'、'.join(dates)})"}
    if re.search(r"日|天", s) and re.search(r"周|礼拜|星期", s):
        dates = _future_weekday(0)
        return {"mode": "in", "set": dates, "label": f"{s}({'、'.join(dates)})"}
    if re.search(r"今天|今晚", s):
        return {"mode": "in", "set": [sh_date_str(0)], "label": s}
    if "明天" in s:
        return {"mode": "in", "set": [sh_date_str(1)], "label": s}
    if "后天" in s:
        return {"mode": "in", "set": [sh_date_str(2)], "label": s}
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return {"mode": "in", "set": [f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"], "label": s}
    m = re.match(r"^(?:2026-)?(\d{1,2})[-/.](\d{1,2})$", s)
    if m:
        return {"mode": "in", "set": [f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"], "label": s}
    m = re.match(r"^(\d{1,2})月(\d{1,2})[日号]?$", s)
    if m:
        return {"mode": "in", "set": [f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"], "label": s}
    return {"mode": "invalid", "set": [], "label": s}


# --------------------------------------------------------------------------- #
# Fetch + normalise
# --------------------------------------------------------------------------- #
def fetch_activities(timeout: int = DEFAULT_TIMEOUT) -> list:
    """Return the raw ``data.list`` array. Raises :class:`UpstreamError`."""
    try:
        resp = requests.get(API_URL, headers={"User-Agent": UA}, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise UpstreamError(f"network error contacting CUQU API: {exc}") from exc
    if resp.status_code != 200:
        raise UpstreamError(f"CUQU API HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise UpstreamError(f"CUQU API returned non-JSON: {exc}") from exc
    if payload.get("code") != 0:
        raise UpstreamError(f"CUQU API error code={payload.get('code')} msg={payload.get('msg')}")
    return (payload.get("data") or {}).get("list") or []


def _millis_to_cn(ms) -> str:
    try:
        ms = int(ms or 0)
    except (TypeError, ValueError):
        return ""
    if ms <= 0:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=CN_TZ).strftime("%Y-%m-%d %H:%M")


def normalize(a: dict) -> dict:
    start_ms = a.get("start_time") or 0
    end_ms = a.get("end_time") or 0
    start = datetime.fromtimestamp(int(start_ms) / 1000, tz=CN_TZ) if start_ms else None
    end = datetime.fromtimestamp(int(end_ms) / 1000, tz=CN_TZ) if end_ms else None
    aid = str(a.get("_id") or "")
    return {
        "id": aid,
        "title": a.get("title"),
        "type": a.get("preference"),
        "date": start.strftime("%Y-%m-%d") if start else "",
        "time": (f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" if (start and end) else ""),
        "weekday": "一二三四五六日"[start.weekday()] if start else "",
        "location": a.get("location"),
        "city": guess_city(a.get("location"), a.get("latitude"), a.get("longitude")),
        "price": a.get("price"),
        "fee_type": a.get("fee_type"),
        "current_participants": a.get("current_participants"),
        "max_participants": a.get("max_participants"),
        "organizer": a.get("creator_name"),
        "cover": a.get("cover"),
        "url": f"https://cuqu.net/activities/list/{aid}.html" if aid else "",
        "start_millis": int(start_ms or 0),
        "end_cn": _millis_to_cn(end_ms),
    }


def load_items(timeout: int = DEFAULT_TIMEOUT) -> list:
    """Fetch + normalise + sort by start time ascending."""
    items = [normalize(a) for a in fetch_activities(timeout)]
    return sorted(items, key=lambda x: x["start_millis"])


def scan_mock_markers(items: list) -> list:
    """Return the first few items that look like the old hard-coded demo data.

    Used as a self-check: if this ever returns anything, the whole "real data"
    claim of the plugin is void.
    """
    bad = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # 同时兼容归一化前后的字段名，保证这道哨兵对 raw 与 normalised 数据都有效
        blob = "".join(
            str(it.get(k) or "")
            for k in ("id", "_id", "title", "organizer", "creator_name")
        )
        if any(m in blob for m in MOCK_MARKERS):
            bad.append(str(it.get("id") or it.get("_id") or ""))
    return bad
