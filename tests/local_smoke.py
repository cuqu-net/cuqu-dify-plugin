#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local smoke test for the CUQU Dify plugin — pure logic layer, no Dify runtime.

Every positive assertion is paired with a control case that MUST fail, so a
green run proves the assertions actually bite (a validator that can never fail
is worthless — this is the rule we learned from the gateway rollouts).

Run:  python tests/local_smoke.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import cuqu_api as api  # noqa: E402

GREEN, RED, YELL, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    flag = GREEN + "PASS" + RESET if ok else RED + "FAIL" + RESET
    print(f"[{flag}] {name}" + (f"  -> {detail}" if detail else ""))


def main():
    # ---- 1. live fetch ---------------------------------------------------- #
    items = api.load_items()
    check("真实接口可取到活动", len(items) > 0, f"{len(items)} 条")

    # ---- 2. no mock markers in live data ---------------------------------- #
    bad = api.scan_mock_markers(items)
    check("实时数据无 mock 特征", not bad, f"命中 {bad[:3]}" if bad else "0 命中")

    # ---- 3. control: mock scanner must actually catch mock ---------------- #
    fake = [
        {"_id": "act_001", "title": "周末桌游局", "preference": "桌游聚会",
         "location": "深圳南山", "creator_name": "小趣", "start_time": 0, "end_time": 0}
    ]
    check("[对照] 扫描器能识破 mock（必须检出）", len(api.scan_mock_markers(fake)) == 1,
          "act_001/小趣 已识别")

    # ---- 4. city filter narrows results ----------------------------------- #
    now = int(time.time() * 1000)
    upcoming = [x for x in items if (x.get("start_millis") or 0) >= now]
    sz = [x for x in upcoming if x.get("city") == "深圳"]
    check("城市过滤有效（深圳 < 全国）", 0 < len(sz) < len(upcoming),
          f"深圳 {len(sz)} / 全国未开始 {len(upcoming)}")

    # ---- 5. control: impossible city must return zero --------------------- #
    ghost = [x for x in upcoming if x.get("city") == "珠穆朗玛"]
    check("[对照] 不存在的城市返回 0（必须为 0）", len(ghost) == 0, f"{len(ghost)} 条")

    # ---- 6. control: broken endpoint must raise --------------------------- #
    saved = api.API_URL
    api.API_URL = "https://cuqu.net/api/__not_exist__"
    try:
        api.fetch_activities(timeout=15)
        raised = False
        detail = "竟然没报错"
    except api.UpstreamError as exc:
        raised = True
        detail = str(exc)[:60]
    except Exception as exc:  # noqa: BLE001
        raised = True
        detail = f"{type(exc).__name__}: {exc}"[:60]
    finally:
        api.API_URL = saved
    check("[对照] 错误端点必须抛错（不能静默空）", raised, detail)

    # ---- 7. date parsing -------------------------------------------------- #
    cases = [
        ("周末", "in", 1),
        ("明天", "in", 1),
        ("2026-10-03", "in", 1),
        ("瞎写的日期", "invalid", 0),
        ("", "none", 0),
    ]
    all_ok, detail = True, []
    for raw, mode, min_len in cases:
        r = api.parse_date_filter(raw)
        ok = r["mode"] == mode and len(r["set"]) >= min_len
        all_ok = all_ok and ok
        detail.append(f"{raw or '(空)'}->{r['mode']}{r['set']}")
    check("日期解析（模糊+精确+不可识别）", all_ok, "; ".join(detail))

    # ---- 8. geo fallback -------------------------------------------------- #
    ok = api.guess_city("广东省深圳市南山区科苑大道") == "深圳"
    ok = ok and api.guess_city("", 22.54, 114.05) == "深圳"
    ok = ok and api.guess_city("车公庙", 22.53, 114.02) == "深圳"
    ok = ok and api.guess_city("", 45.0, 90.0) == ""
    check("城市判定（文本+经纬度兜底）", ok)

    total = len(results)
    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 62)
    print(f"{total - len(failed)}/{total} PASS" + ("" if not failed else f"  {len(failed)} FAIL"))
    if failed:
        for n, _o, d in failed:
            print(YELL + f"  FAIL: {n}  {d}" + RESET)
    print("=" * 62)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
