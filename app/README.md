# 한끼AI / 一餐 AI — working demo

한국 캠퍼스 AI 식단관리 서비스의 **실제로 돌아가는 MVP**입니다.  
不是概念稿：这里有一个真的 CLIP 模型、真的 FastAPI、真的 SQLite 记录和真的周报。

- **AI**: CLIP zero-shot, 30 Korean food classes, multi-region top-3
- **API**: FastAPI + Swagger (`/docs`)
- **DB**: SQLite (meals, items, goals)
- **Frontend**: single-page PWA-style vanilla HTML/CSS/JS
- **Demo data**: 7 days of seeded meals so the report is not empty

---

## 1. What works

| Feature | Endpoint | Status |
|---|---|---|
| Campus menu + nutrition totals | `GET /api/menu/today?campus=student` | ✅ |
| Food nutrition lookup | `GET /api/nutrition/{food_id}?portion=1` | ✅ |
| Photo → dish recognition | `POST /api/predict` (multipart) | ✅ |
| Save a meal | `POST /api/meals` | ✅ |
| Today's meals | `GET /api/meals?day=YYYY-MM-DD` | ✅ |
| Week report + insights | `GET /api/report/week?end=YYYY-MM-DD` | ✅ |
| Week meal list | `GET /api/meals/week?end=YYYY-MM-DD` | ✅ |
| Goals | `GET/PUT /api/profile` | ✅ |
| Swagger docs | `/docs` | ✅ |
| Share page / plan | `/share/` | ✅ |

The demo seeds 8 meals across the last 7 days **only if the DB is empty**. Set `SEED_DEMO=0` to start clean.

---

## 2. Quick start (Windows)

```powershell
cd E:\bridge\state\slang-agent\hankki-ai\app
.\.venv\Scripts\Activate.ps1
# or:
# .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8788
uvicorn main:app --host 127.0.0.1 --port 8788
```

Open:

- App: <http://127.0.0.1:8788/>
- API docs: <http://127.0.0.1:8788/docs>
- Share page: <http://127.0.0.1:8788/share/>

The first start downloads `openai/clip-vit-base-patch32` (~600MB) to `data/hf`.  
Set a mirror if HuggingFace is slow:

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

If the model cannot download, the rest of the app (menu, meals, report) still works; `/api/predict` returns `503` until the model is ready.

### Fresh install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
```

---

## 3. Try the AI

### From the UI

1. Open `/`
2. Tap **기록 / 记录**
3. Choose a sample (`bibimbap`, `kimchi_jjigae`, `donkatsu`) or upload your own photo
4. Tap **AI로 인식하기**
5. Adjust S/M/L, remove/add items, then **이대로 기록하기**
6. Open **리포트 / 报告** to see the week update

### From curl

```bash
curl -X POST http://127.0.0.1:8788/api/predict \
  -F "file=@samples/bibimbap.jpg"
```

Response shape:

```json
{
  "engine": "clip-zero-shot",
  "model": "openai/clip-vit-base-patch32",
  "latency_ms": 1830,
  "uncertain": false,
  "items": [
    {
      "food_id": "bibimbap",
      "name_ko": "비빔밥",
      "name_zh": "拌饭",
      "confidence": 0.91,
      "portion": 1.0,
      "nutrition": {"kcal": 560, "protein": 18, "carbs": 85, "fat": 15, "sodium": 900}
    }
  ],
  "alternatives": [...],
  "image_id": "…",
  "image_url": "/uploads/…"
}
```

Save a meal:

```bash
curl -X POST http://127.0.0.1:8788/api/meals \
  -H "Content-Type: application/json" \
  -d '{"meal_type":"lunch","source":"manual","items":[{"food_id":"bibimbap","portion":1.0}]}'
```

---

## 4. AI design (honest version)

This is **zero-shot CLIP**, not a model trained on 3,000 Korean trays.

- Image → CLIP embedding
- Cosine similarity against 30 Korean-food prompt sets
- Softmax → top-5
- Full image + 4 overlapping crops → up to 3 unique items
- Every result is **editable**; low confidence triggers top-3 fallback

What this means:

- ✅ It is real inference, real API, real latency.
- ✅ It works reasonably on clean, centered photos (bibimbap / stew / cutlet).
- ⚠️ It is **not** production-accurate on cluttered cafeteria trays, small side dishes, or occluded food.
- ⚠️ Portion is `S/M/L` (0.75 / 1.0 / 1.25), not grams. Do not claim gram-level accuracy.

The plan's next step is to fine-tune YOLOv8 + EfficientNet on 2,000–3,000 labelled trays; this demo proves the **API contract and user flow** first.

---

## 5. Data

- 30 foods with Korean/Chinese names, serving, kcal, protein, carbs, fat, sodium: `data/foods.json`
- 2 campus menus × 7 days: `data/menus.json`
- Nutrition values are **design baselines**; replace with 식약처 K-FIND values before submission.
- Sample photos are CC0 from Wikimedia Commons:
  - `bibimbap.jpg` — “Beef Bibimbap - SAERO 2025-11-06”, Andy Li, CC0
  - `kimchi_jjigae.jpg` — “Kimchi jjigae - Kogi, Brighton 2023-11-15”, Andy Li, CC0
  - `donkatsu.jpg` — “吉列豬扒定食”, Andy Li, CC0

---

## 6. Project layout

```text
app/
  main.py          FastAPI routes + static mounts
  ai.py            CLIP zero-shot classifier
  db.py            SQLite schema, meals, week report
  data.py          foods / menus loader
  data/
    foods.json
    menus.json
    hankki.db      created on first run
  static/
    index.html
    styles.css
    app.js
    manifest.json
  samples/
  uploads/
  requirements.txt
  run.ps1
  Dockerfile
  README.md
```

The share page is mounted at `/share/` from `../share`.

---

## 7. Demo script (60 seconds)

1. **Today** — “中午 12 点，学生馆门口，先看今天吃什么。”（point at menu + totals）
2. **Camera** — choose `bibimbap`, tap AI; show top result + confidence + alternatives.
3. **Adjust** — change portion M → L; remove a side; show total recalculation.
4. **Save** — toast; Today updates.
5. **Report** — show protein gap, sodium warning, 7-day streak.
6. **API** — open `/docs`, show `POST /api/predict` is real.

---

## 8. Limitations / next

- Replace zero-shot CLIP with a fine-tuned 30-class model (YOLOv8 + EfficientNet).
- Add real K-FIND API mapping and a full 30-class nutrition table.
- Add auth / multi-user; current DB is single-user demo.
- Add image cleanup job (uploads are kept for demo).
- Add tests with `pytest` + `httpx` (not included to keep install light).

---

## 9. License / course use

Code: MIT for course project use.  
Data/photos: see credits above.  
Product name **한끼AI** is a working title (가칭).
