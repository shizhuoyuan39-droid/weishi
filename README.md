# 한끼AI / 一餐 AI

**사진 한 장으로 끝나는, 한국 캠퍼스 식단관리**  
**拍一张餐盘，15 秒记完这一餐。**

> 산학연계 SW프로젝트(마이크로스톤) 결과물  
> 사진 기반 AI 식품 영양 분석 및 식단 관리 서비스

---

## 1. 프로젝트 소개

한국 대학 캠퍼스에서 식사하는 외국인 유학생은 학식 메뉴의 한국어 설명과 1인분 양을 이해하기 어려워 영양 관리가 사실상 불가능하다. 기존 칼로리 앱은 서구권 단품 중심이라 밥·국·반찬으로 구성된 한식 tray를 제대로 다루지 못하고, 수동 검색은 한 끼에 60~90초가 걸려 지속하기 어렵다.

한끼AI는 이 문제를 **“먹기 전 메뉴 확인 → 먹은 후 사진 한 장 → 주간 리포트”** 의 15초 흐름으로 해결하는 MVP다.

### 3단계 흐름

1. **보고 결정한다** — 오늘의 학식 메뉴 + kcal/단백질/나트륨/가격
2. **먹고 15초 기록한다** — tray 사진 1장 → 1~3개 음식 인식 → S/M/L 분량 보정 → 저장
3. **주간 리포트로 행동한다** — 단백질 gap, 나트륨, 7일 streak, 다음 행동 3개

---

## 2. 현재 상태 (정직한 범위)

| 구분 | 상태 |
|---|---|
| AI | CLIP zero-shot, 30개 한식 클래스, 5 crop + Top-3 fallback |
| 추론 | CPU 약 0.35~0.45초/장 (로컬), 터널 경유 약 0.9초 |
| 검증 | 샘플 3장 Top-1 3/3 (일반화 성능 아님) |
| Backend | FastAPI + SQLite, `/docs` Swagger |
| Frontend | 바닐라 HTML/CSS/JS PWA, 한/중 토글, 3화면 |
| Android | WebView APK, minSdk 24, targetSdk 35, 약 17KB |
| 데이터 | 30개 음식 로컬 영양 baseline, 2개 캠퍼스 × 7일 메뉴 |
| K-FIND | **미연동** (serviceKey 필요) |
| 파인튜닝 | **미수행** (zero-shot 데모) |
| 사용자 조사 | 60명 설문/10명 인터뷰/15명 일지 **계획만** |
| 오프라인 APK | **미지원** (모델을 APK에 내장하지 않음) |

> Top-1 80%는 **목표**이며 실제 달성 수치가 아니다.  
> APK는 서버 URL을 로드하는 WebView 껍데기이며, 서버가 꺼지면 동작하지 않는다.

### 샘플 3장 결과

| 음식 | Top-1 confidence |
|---|---|
| 비빔밥 | 0.968 |
| 김치찌개 | 0.546 (2위 순두부찌개 0.187) |
| 돈까스 | 0.844 |

---

## 3. 저장소 구조

```text
.
├── app/                    FastAPI + SQLite + PWA
│   ├── main.py             API endpoints
│   ├── ai.py               CLIP zero-shot
│   ├── db.py               SQLite schema / seed
│   ├── data.py             foods/menus loader
│   ├── data/foods.json     30 foods + nutrition
│   ├── data/menus.json     2 campuses × 7 days
│   ├── static/             PWA (HTML/CSS/JS)
│   └── samples/            sample images
├── android/                WebView APK + source
│   ├── HankkiAI/           Android project (no Gradle)
│   ├── HankkiAI.apk        installable APK
│   ├── build_apk.ps1       manual aapt2/javac/d8/apksigner build
│   └── README.md
├── docs/                   plan / AI context / HWP guide
├── data/                   nutrition + competitor XLSX
├── hwp/                    school HWP forms (filled)
└── images/                 product concept / UI images
```

---

## 4. 실행 방법

### Backend + Frontend

```bash
cd app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8788
```

- App: http://127.0.0.1:8788/
- API docs: http://127.0.0.1:8788/docs
- 첫 실행 시 `data/hankki.db` 생성 + 7일 demo seed

> 최초 실행 시 CLIP 모델(`openai/clip-vit-base-patch32`)을 내려받기 때문에 수백 MB의 캐시와 시간이 필요하다. `HF_HOME`을 `app/data/hf`로 두면 저장소 안에 캐시된다(커밋 제외).

### Android APK

```text
android/HankkiAI.apk
```

- Android 7.0+ (API 24)
- 설치 시 “알 수 없는 앱 설치” 허용
- 서버 URL은 `android/HankkiAI/src/com/hankki/ai/MainActivity.java`의 `APP_URL`
- 재빌드: `powershell -ExecutionPolicy Bypass -File android/build_apk.ps1`

---

## 5. API

| Method | Endpoint | 설명 |
|---|---|---|
| GET | `/api/health` | 서버/AI 상태 |
| GET | `/api/menu/today?campus=student` | 오늘의 학식 |
| POST | `/api/predict` | 이미지 → 음식 인식 |
| GET | `/api/nutrition/{food_id}` | 음식 영양 |
| GET | `/api/meals?day=YYYY-MM-DD` | 하루 기록 |
| GET | `/api/meals/week` | 주간 기록 |
| POST | `/api/meals` | 식사 저장 |
| DELETE | `/api/meals/{id}` | 식사 삭제 |
| GET | `/api/report/week` | 주간 리포트 |
| GET/PUT | `/api/profile` | 목표/캠퍼스 |
| GET | `/docs` | Swagger |

### 예시

```http
POST /api/predict
Content-Type: multipart/form-data
file=@bibimbap.jpg

→ 200
{
  "engine": "clip-zero-shot",
  "model": "openai/clip-vit-base-patch32",
  "latency_ms": 430,
  "items": [
    {
      "food_id": "bibimbap",
      "name_ko": "비빔밥",
      "name_zh": "拌饭",
      "confidence": 0.968,
      "portion": 1.0,
      "nutrition": {"kcal": 560, "protein": 18, "carbs": 85, "fat": 15, "sodium": 900}
    }
  ]
}
```

---

## 6. AI 구조

```text
image
  ├─ full image
  └─ 4 crops (left / right / top / bottom)
        ↓
CLIP image embedding
        ↓
30 text prompts (ko/en)
        ↓
cosine similarity → softmax
        ↓
Top-5 candidates
        ↓
unique + threshold(0.58) → 1~3 items
        ↓
S/M/L portion multiplier (0.75 / 1.0 / 1.25)
```

- 모델: `openai/clip-vit-base-patch32`
- 30 classes: 비빔밥, 김치찌개, 된장찌개, 순두부찌개, 돈까스, 제육덮밥, 닭갈비덮밥, 불고기덮밥, 카레라이스, 김밥, 라면, 떡볶이, 미역국, 콩나물국, 삼겹살, 불고기, 잡채, 계란후라이, 두부, 김치, 깍두기, 요구르트, 우유, 바나나, 사과, 고구마, 현미밥, 흰밥, 샐러드, 치킨
- 영양값은 **로컬 baseline(예시)** 이며 K-FIND 실데이터가 아니다.

---

## 7. 문서 / 산출물

| 파일 | 내용 |
|---|---|
| `docs/plan_ko_zh.pdf` | 22-page 제품 기획서 (중문 + 한국어 부록) |
| `docs/ai_context.md` | 다른 AI에게 첨부해 보고서를 쓰게 하는 전체 사실 자료 |
| `docs/hwp_guide.pdf` | HWP 양식 칸별 작성 가이드 |
| `docs/hwp_draft.pdf` | 결과보고서 + 장학금 신청서 초안 |
| `data/nutrition_competitors.xlsx` | 시장/경쟁/30종 음식/예측 데이터 |
| `hwp/result_report.hwp` | 학교 결과보고서 양식 (프로젝트 내용 채움) |
| `hwp/scholarship.hwp` | 학교 장학금 신청서 양식 (이유/추천의견 채움) |
| `images/` | 삼면 예측도, 포지셔닝, 12개월 예측, UI |

### HWP 작성 시 남은 `[ ]`

- `[멘토 재직회사명]`
- `[지도교수명]`
- `[멘토명]`
- `[팀원 1]` ~ `[팀원 4]`
- `[GitHub URL]` / `[아이디]`
- `[이름]`, `[학과]`, `[학번]`, `[학년]`, `[연락처]`, `[역할]`

> 서명은 자필/전자서명이 필요하며, GitHub 첫 페이지 캡처를 `오픈소스주소` 아래에 삽입해야 한다.

---

## 8. 팀 / 기간

| 역할 | 담당 |
|---|---|
| A | AI/데이터: 라벨링, CLIP/YOLO, 평가 |
| B | 백엔드/영양: FastAPI, SQLite, K-FIND, 메뉴 |
| C | 프론트/디자인: PWA, 3화면, 차트, 한/중 |
| D | PM/QA/문서: 조사, 테스트, 배포, HWP/PPT |

- 학생 4명 + 지도교수 1명 + 기업 멘토 1명
- 수행기간: 2026.04.01. ~ 2026.08.30. (학교 양식 기준)

---

## 9. 라이선스 / 데이터 출처

- 코드: 교육/포트폴리오 목적. 외부 배포 전 라이선스 확정 필요.
- 이미지: 샘플은 CC0/공개 이미지, 제품 이미지는 프로젝트 제작.
- 참고 데이터: 식약처 K-FIND, AI Hub, 공공데이터포털, Food-101, UECFood-256.
- 시장 데이터: Grand View Research, 교육부 《2026 교육기본통계》.

---

## 10. Known Limitations

- Zero-shot 정확도는 실제 급식 tray에서 검증되지 않았다.
- 다품목 인식은 최대 3개이나 실제로는 1개가 자주 나온다.
- K-FIND 실데이터가 아니라 로컬 30종 baseline이다.
- APK는 오프라인 AI가 아니며 서버가 필요하다.
- 로그인/멀티유저/결제/알림은 MVP 범위 밖이다.
- 사용자 조사와 50명 베타는 아직 수행하지 않았다.

---

## 11. Contact

- GitHub: [@shizhuoyuan39-droid](https://github.com/shizhuoyuan39-droid)
- Repository: https://github.com/shizhuoyuan39-droid/weishi
