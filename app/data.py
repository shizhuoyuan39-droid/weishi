"""Static food and campus menu data."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@lru_cache(maxsize=1)
def load_foods() -> list[dict[str, Any]]:
    with open(DATA_DIR / "foods.json", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def food_index() -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in load_foods()}


@lru_cache(maxsize=1)
def load_menus() -> list[dict[str, Any]]:
    with open(DATA_DIR / "menus.json", encoding="utf-8") as f:
        return json.load(f)["campuses"]


def get_food(food_id: str) -> dict[str, Any] | None:
    return food_index().get(food_id)


def all_foods() -> list[dict[str, Any]]:
    return load_foods()


def campuses() -> list[dict[str, Any]]:
    return [{"id": c["id"], "name_ko": c["name_ko"], "name_zh": c["name_zh"], "hours": c["hours"]} for c in load_menus()]


def weekday_key(d: date | None = None) -> str:
    d = d or date.today()
    return WEEKDAYS[d.weekday()]


def menu_for(campus_id: str, d: date | None = None) -> dict[str, Any] | None:
    d = d or date.today()
    campus = next((c for c in load_menus() if c["id"] == campus_id), None)
    if not campus:
        return None
    entries = campus["weekly"].get(weekday_key(d), [])
    items = []
    for entry in entries:
        food = get_food(entry["food_id"])
        if not food:
            continue
        item = dict(food)
        item["price"] = entry.get("price", 0)
        items.append(item)
    total = {
        "kcal": round(sum(i["kcal"] for i in items), 1),
        "protein": round(sum(i["protein"] for i in items), 1),
        "carbs": round(sum(i["carbs"] for i in items), 1),
        "fat": round(sum(i["fat"] for i in items), 1),
        "sodium": round(sum(i["sodium"] for i in items), 1),
    }
    return {
        "campus": {"id": campus["id"], "name_ko": campus["name_ko"], "name_zh": campus["name_zh"], "hours": campus["hours"]},
        "date": d.isoformat(),
        "weekday": weekday_key(d),
        "weekday_ko": WEEKDAY_KO[d.weekday()],
        "weekday_zh": WEEKDAY_ZH[d.weekday()],
        "items": items,
        "total": total,
    }
