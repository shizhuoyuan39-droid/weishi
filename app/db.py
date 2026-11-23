"""SQLite persistence for meals, goals and weekly reports."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "hankki.db"

DEFAULT_PROFILE = {
    "name": "Lina",
    "campus_id": "student",
    "goal_kcal": 1800,
    "goal_protein": 105,
    "goal_sodium": 2000,
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                campus_id TEXT NOT NULL DEFAULT 'student',
                goal_kcal REAL NOT NULL DEFAULT 1800,
                goal_protein REAL NOT NULL DEFAULT 105,
                goal_sodium REAL NOT NULL DEFAULT 2000
            );
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eaten_at TEXT NOT NULL,
                meal_type TEXT NOT NULL DEFAULT 'lunch',
                source TEXT NOT NULL DEFAULT 'manual',
                image_id TEXT,
                note TEXT,
                total_kcal REAL NOT NULL DEFAULT 0,
                total_protein REAL NOT NULL DEFAULT 0,
                total_carbs REAL NOT NULL DEFAULT 0,
                total_fat REAL NOT NULL DEFAULT 0,
                total_sodium REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meal_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
                food_id TEXT NOT NULL,
                name_ko TEXT NOT NULL,
                name_zh TEXT NOT NULL,
                portion REAL NOT NULL DEFAULT 1.0,
                kcal REAL NOT NULL DEFAULT 0,
                protein REAL NOT NULL DEFAULT 0,
                carbs REAL NOT NULL DEFAULT 0,
                fat REAL NOT NULL DEFAULT 0,
                sodium REAL NOT NULL DEFAULT 0,
                confidence REAL
            );
            CREATE INDEX IF NOT EXISTS idx_meals_eaten ON meals(eaten_at);
            CREATE INDEX IF NOT EXISTS idx_items_meal ON meal_items(meal_id);
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO profile (id, name, campus_id, goal_kcal, goal_protein, goal_sodium) VALUES (1, ?, ?, ?, ?, ?)",
            (DEFAULT_PROFILE["name"], DEFAULT_PROFILE["campus_id"], DEFAULT_PROFILE["goal_kcal"],
             DEFAULT_PROFILE["goal_protein"], DEFAULT_PROFILE["goal_sodium"]),
        )


def _row_to_meal(row: sqlite3.Row, items: list[sqlite3.Row]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "eaten_at": row["eaten_at"],
        "date": row["eaten_at"][:10],
        "meal_type": row["meal_type"],
        "source": row["source"],
        "image_id": row["image_id"],
        "note": row["note"],
        "total_kcal": round(row["total_kcal"], 1),
        "total_protein": round(row["total_protein"], 1),
        "total_carbs": round(row["total_carbs"], 1),
        "total_fat": round(row["total_fat"], 1),
        "total_sodium": round(row["total_sodium"], 1),
        "items": [
            {
                "id": i["id"],
                "food_id": i["food_id"],
                "name_ko": i["name_ko"],
                "name_zh": i["name_zh"],
                "portion": i["portion"],
                "nutrition": {
                    "kcal": round(i["kcal"], 1),
                    "protein": round(i["protein"], 1),
                    "carbs": round(i["carbs"], 1),
                    "fat": round(i["fat"], 1),
                    "sodium": round(i["sodium"], 1),
                },
                "confidence": i["confidence"],
            }
            for i in items
        ],
    }


def get_profile() -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return dict(row) if row else dict(DEFAULT_PROFILE)


def update_profile(data: dict[str, Any]) -> dict[str, Any]:
    current = get_profile()
    for key in ("name", "campus_id", "goal_kcal", "goal_protein", "goal_sodium"):
        if key in data and data[key] is not None:
            current[key] = data[key]
    with connect() as conn:
        conn.execute(
            "UPDATE profile SET name=?, campus_id=?, goal_kcal=?, goal_protein=?, goal_sodium=? WHERE id=1",
            (current["name"], current["campus_id"], current["goal_kcal"], current["goal_protein"], current["goal_sodium"]),
        )
    return get_profile()


def create_meal(
    eaten_at: datetime,
    meal_type: str,
    source: str,
    image_id: str | None,
    note: str | None,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    totals = {
        "kcal": sum(float(i["nutrition"]["kcal"]) for i in items),
        "protein": sum(float(i["nutrition"]["protein"]) for i in items),
        "carbs": sum(float(i["nutrition"]["carbs"]) for i in items),
        "fat": sum(float(i["nutrition"]["fat"]) for i in items),
        "sodium": sum(float(i["nutrition"]["sodium"]) for i in items),
    }
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO meals
               (eaten_at, meal_type, source, image_id, note, total_kcal, total_protein, total_carbs, total_fat, total_sodium, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                eaten_at.isoformat(timespec="minutes"), meal_type, source, image_id, note,
                totals["kcal"], totals["protein"], totals["carbs"], totals["fat"], totals["sodium"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        meal_id = cur.lastrowid
        for item in items:
            n = item["nutrition"]
            conn.execute(
                """INSERT INTO meal_items
                   (meal_id, food_id, name_ko, name_zh, portion, kcal, protein, carbs, fat, sodium, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meal_id, item["food_id"], item["name_ko"], item["name_zh"], item.get("portion", 1.0),
                    n["kcal"], n["protein"], n["carbs"], n["fat"], n["sodium"], item.get("confidence"),
                ),
            )
    meal = get_meal(meal_id)
    assert meal
    return meal


def get_meal(meal_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM meals WHERE id = ?", (meal_id,)).fetchone()
        if not row:
            return None
        items = conn.execute("SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id", (meal_id,)).fetchall()
        return _row_to_meal(row, items)


def list_meals(day: date | None = None) -> list[dict[str, Any]]:
    day = day or date.today()
    prefix = day.isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meals WHERE substr(eaten_at, 1, 10) = ? ORDER BY eaten_at", (prefix,)
        ).fetchall()
        meals = []
        for row in rows:
            items = conn.execute("SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id", (row["id"],)).fetchall()
            meals.append(_row_to_meal(row, items))
        return meals


def list_meals_range(start: date, end: date) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM meals
               WHERE substr(eaten_at,1,10) BETWEEN ? AND ?
               ORDER BY eaten_at DESC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        meals = []
        for row in rows:
            items = conn.execute("SELECT * FROM meal_items WHERE meal_id = ? ORDER BY id", (row["id"],)).fetchall()
            meals.append(_row_to_meal(row, items))
        return meals


def delete_meal(meal_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM meals WHERE id = ?", (meal_id,))
        return cur.rowcount > 0


def _day_totals(conn: sqlite3.Connection, day: date) -> dict[str, Any]:
    prefix = day.isoformat()
    row = conn.execute(
        """SELECT COUNT(*) AS n, COALESCE(SUM(total_kcal),0) AS kcal, COALESCE(SUM(total_protein),0) AS protein,
                  COALESCE(SUM(total_carbs),0) AS carbs, COALESCE(SUM(total_fat),0) AS fat,
                  COALESCE(SUM(total_sodium),0) AS sodium
           FROM meals WHERE substr(eaten_at,1,10) = ?""",
        (prefix,),
    ).fetchone()
    photo = conn.execute(
        "SELECT COUNT(*) FROM meals WHERE substr(eaten_at,1,10)=? AND source='photo'", (prefix,)
    ).fetchone()[0]
    return {
        "date": prefix,
        "logged": row["n"] > 0,
        "meals": row["n"],
        "photo_meals": photo,
        "kcal": round(row["kcal"], 1),
        "protein": round(row["protein"], 1),
        "carbs": round(row["carbs"], 1),
        "fat": round(row["fat"], 1),
        "sodium": round(row["sodium"], 1),
    }


def week_report(end: date | None = None) -> dict[str, Any]:
    end = end or date.today()
    start = end - timedelta(days=6)
    profile = get_profile()
    with connect() as conn:
        days = []
        d = start
        while d <= end:
            days.append(_day_totals(conn, d))
            d += timedelta(days=1)
        total_meals = conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]
        total_photo = conn.execute("SELECT COUNT(*) FROM meals WHERE source='photo'").fetchone()[0]

    logged_days = [x for x in days if x["logged"]]
    avg = lambda key: round(sum(x[key] for x in logged_days) / len(logged_days), 1) if logged_days else 0.0
    avg_kcal = avg("kcal")
    avg_protein = avg("protein")
    avg_sodium = avg("sodium")

    streak = 0
    with connect() as conn:
        cursor = end
        while True:
            row = conn.execute(
                "SELECT COUNT(*) FROM meals WHERE substr(eaten_at,1,10)=?", (cursor.isoformat(),)
            ).fetchone()[0]
            if row == 0:
                break
            streak += 1
            cursor -= timedelta(days=1)

    insights = []
    if logged_days and avg_protein < profile["goal_protein"] * 0.9:
        gap = round(profile["goal_protein"] - avg_protein)
        insights.append({
            "type": "protein",
            "title_ko": f"단백질이 {round((1 - avg_protein / profile['goal_protein']) * 100)}% 부족해요",
            "title_zh": f"蛋白质比目标少 {round((1 - avg_protein / profile['goal_protein']) * 100)}%",
            "body_ko": f"하루 평균 {avg_protein}g / 목표 {profile['goal_protein']}g. 다음 끼니에 두부·계란·닭가슴살을 더해보세요.",
            "body_zh": f"日均 {avg_protein}g / 目标 {profile['goal_protein']}g。下一餐加豆腐、鸡蛋或鸡胸肉。",
            "value": f"+{gap}g",
        })
    if logged_days and avg_sodium > profile["goal_sodium"]:
        pct = round((avg_sodium / profile["goal_sodium"] - 1) * 100)
        insights.append({
            "type": "sodium",
            "title_ko": f"나트륨이 {pct}% 높아요",
            "title_zh": f"钠摄入超标 {pct}%",
            "body_ko": "국물은 절반만, 장아찌·소스는 따로 두세요.",
            "body_zh": "汤喝一半，酱菜和酱料分开吃。",
            "value": f"{round(avg_sodium)}mg",
        })
    if streak >= 3:
        insights.append({
            "type": "streak",
            "title_ko": f"{streak}일 연속 기록 중",
            "title_zh": f"连续记录 {streak} 天",
            "body_ko": "기록 자체가 목표예요. 이번 주는 단백질 +1에 집중해보세요.",
            "body_zh": "记录本身就是目标。这周先专注“蛋白质 +1”。",
            "value": f"{streak} DAY",
        })
    if not insights:
        insights.append({
            "type": "start",
            "title_ko": "첫 끼를 기록해보세요",
            "title_zh": "先记录第一餐",
            "body_ko": "사진 한 장이면 15초 안에 끝나요.",
            "body_zh": "拍一张照片，15 秒就能记完。",
            "value": "15s",
        })

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "goals": {
            "kcal": profile["goal_kcal"],
            "protein": profile["goal_protein"],
            "sodium": profile["goal_sodium"],
        },
        "avg_kcal": avg_kcal,
        "avg_protein": avg_protein,
        "avg_sodium": avg_sodium,
        "days_logged": len(logged_days),
        "streak": streak,
        "total_meals": total_meals,
        "total_photo": total_photo,
        "photo_ratio": round(total_photo / total_meals, 3) if total_meals else 0,
        "insights": insights,
    }


def seed_demo_meals() -> int:
    """Create a small, clearly-labelled demo history when the DB is empty."""
    from data import get_food

    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM meals").fetchone()[0]
    if count:
        return 0

    plans = [
        (6, "lunch", ["bibimbap", "kimchi", "yogurt"], "photo"),
        (5, "lunch", ["dakgalbi", "miyeokguk", "kkakdugi"], "photo"),
        (4, "lunch", ["jeyuk", "kongnamul", "kimchi"], "manual"),
        (3, "lunch", ["donkatsu", "miyeokguk", "salad"], "photo"),
        (2, "lunch", ["bibimbap", "doenjang_jjigae", "kimchi"], "photo"),
        (1, "lunch", ["curry", "sundubu", "kkakdugi"], "manual"),
        (0, "lunch", ["bibimbap", "kimchi", "yogurt"], "photo"),
    ]
    made = 0
    for days_ago, meal_type, food_ids, source in plans:
        d = date.today() - timedelta(days=days_ago)
        eaten = datetime.combine(d, datetime.min.time()).replace(hour=12 if meal_type == "lunch" else 19)
        items = []
        for fid in food_ids:
            food = get_food(fid)
            if not food:
                continue
            items.append({
                "food_id": food["id"],
                "name_ko": food["ko"],
                "name_zh": food["zh"],
                "portion": 1.0,
                "confidence": None,
                "nutrition": {
                    "kcal": food["kcal"], "protein": food["protein"], "carbs": food["carbs"],
                    "fat": food["fat"], "sodium": food["sodium"],
                },
            })
        create_meal(eaten, meal_type, source, None, "demo seed", items)
        made += 1
    return made
