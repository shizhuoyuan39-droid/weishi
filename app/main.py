"""한끼AI / 一餐 AI — FastAPI backend.

Run:
    uvicorn main:app --reload --port 8788
Docs:
    http://127.0.0.1:8788/docs
"""
from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
from ai import FoodAI
from data import all_foods, campuses, get_food, menu_for

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SAMPLE_DIR = BASE_DIR / "samples"
UPLOAD_DIR = BASE_DIR / "uploads"
SHARE_DIR = BASE_DIR.parent / "share"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

ai = FoodAI(all_foods())


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if os.getenv("SEED_DEMO", "1") != "0":
        try:
            made = db.seed_demo_meals()
            if made:
                print(f"[db] seeded {made} demo meals", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[db] seed failed: {exc}", flush=True)
    try:
        await asyncio.to_thread(ai.load)
    except Exception as exc:  # noqa: BLE001
        print(f"[ai] unavailable: {exc}", flush=True)
    yield


app = FastAPI(
    title="한끼AI API",
    version="1.0.0",
    description="Korean campus AI nutrition assistant — photo recognition, menu, meals and weekly report.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if SAMPLE_DIR.exists():
    app.mount("/samples", StaticFiles(directory=SAMPLE_DIR), name="samples")
if SHARE_DIR.exists():
    app.mount("/share", StaticFiles(directory=str(SHARE_DIR), html=True), name="share")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------- schemas ----------
class MealItemIn(BaseModel):
    food_id: str
    portion: float = Field(default=1.0, ge=0.25, le=3.0)
    confidence: float | None = None


class MealIn(BaseModel):
    eaten_at: datetime | None = None
    meal_type: str = Field(default="lunch", pattern="^(breakfast|lunch|dinner|snack)$")
    source: str = Field(default="manual", pattern="^(manual|photo|demo)$")
    image_id: str | None = None
    note: str | None = None
    items: list[MealItemIn] = Field(min_length=1, max_length=12)


class ProfileIn(BaseModel):
    name: str | None = None
    campus_id: str | None = None
    goal_kcal: float | None = Field(default=None, ge=800, le=5000)
    goal_protein: float | None = Field(default=None, ge=20, le=400)
    goal_sodium: float | None = Field(default=None, ge=500, le=10000)


def _item_nutrition(food: dict[str, Any], portion: float) -> dict[str, float]:
    return {
        "kcal": round(food["kcal"] * portion, 1),
        "protein": round(food["protein"] * portion, 1),
        "carbs": round(food["carbs"] * portion, 1),
        "fat": round(food["fat"] * portion, 1),
        "sodium": round(food["sodium"] * portion, 1),
    }


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc


# ---------- pages ----------
@app.get("/", include_in_schema=False)
def index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return {"message": "Frontend not built", "docs": "/docs"}
    return FileResponse(index_file)


# ---------- api ----------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "time": datetime.now().isoformat(timespec="seconds"),
        "ai": ai.status(),
        "foods": len(all_foods()),
        "campuses": campuses(),
        "nutrition_source": "local 30-class baseline (K-FIND adapter pending)",
        "demo_seed": os.getenv("SEED_DEMO", "1") != "0",
    }


@app.get("/api/foods")
def foods():
    return {"items": all_foods()}


@app.get("/api/nutrition/{food_id}")
def nutrition(food_id: str, portion: float = Query(1.0, ge=0.25, le=3.0)):
    food = get_food(food_id)
    if not food:
        raise HTTPException(status_code=404, detail="food not found")
    return {"food": food, "portion": portion, "nutrition": _item_nutrition(food, portion)}


@app.get("/api/menu/today")
def menu_today(campus: str | None = None, day: str | None = None):
    profile = db.get_profile()
    campus_id = campus or profile["campus_id"]
    d = _parse_date(day)
    result = menu_for(campus_id, d)
    if not result:
        raise HTTPException(status_code=404, detail="campus not found")
    return result


@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if not ai.ready:
        raise HTTPException(status_code=503, detail=f"AI model not ready: {ai.error}")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="image too large (max 12MB)")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="only image uploads are supported")
    image_id = f"{uuid.uuid4().hex[:16]}.jpg"
    (UPLOAD_DIR / image_id).write_bytes(raw)
    try:
        result = await asyncio.to_thread(ai.predict, raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"prediction failed: {exc}") from exc
    result["image_id"] = image_id
    result["image_url"] = f"/uploads/{image_id}"
    return result


@app.get("/api/meals")
def meals(day: str | None = None):
    d = _parse_date(day)
    items = db.list_meals(d)
    return {
        "date": d.isoformat(),
        "items": items,
        "total_kcal": round(sum(x["total_kcal"] for x in items), 1),
        "total_protein": round(sum(x["total_protein"] for x in items), 1),
    }


@app.get("/api/meals/week")
def meals_week(end: str | None = None):
    d = _parse_date(end)
    start = d - timedelta(days=6)
    items = db.list_meals_range(start, d)
    return {"start": start.isoformat(), "end": d.isoformat(), "items": items}


@app.post("/api/meals", status_code=201)
def create_meal(payload: MealIn):
    items = []
    for entry in payload.items:
        food = get_food(entry.food_id)
        if not food:
            raise HTTPException(status_code=404, detail=f"food not found: {entry.food_id}")
        items.append({
            "food_id": food["id"],
            "name_ko": food["ko"],
            "name_zh": food["zh"],
            "portion": entry.portion,
            "confidence": entry.confidence,
            "nutrition": _item_nutrition(food, entry.portion),
        })
    eaten_at = payload.eaten_at or datetime.combine(date.today(), time(12, 0))
    meal = db.create_meal(eaten_at, payload.meal_type, payload.source, payload.image_id, payload.note, items)
    return meal


@app.delete("/api/meals/{meal_id}")
def remove_meal(meal_id: int):
    if not db.delete_meal(meal_id):
        raise HTTPException(status_code=404, detail="meal not found")
    return {"deleted": True, "id": meal_id}


@app.get("/api/report/week")
def report_week(end: str | None = None):
    d = _parse_date(end)
    return db.week_report(d)


@app.get("/api/profile")
def profile():
    return db.get_profile()


@app.put("/api/profile")
def set_profile(payload: ProfileIn):
    return db.update_profile(payload.model_dump(exclude_none=True))


@app.get("/api/samples")
def samples():
    files = sorted([p.name for p in SAMPLE_DIR.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}])
    return {"items": [{"name": f, "url": f"/samples/{f}"} for f in files]}


@app.get("/api/stats")
def stats():
    return {
        "foods": len(all_foods()),
        "meals": db.week_report()["total_meals"],
        "model": ai.status(),
    }
