/* 한끼AI demo frontend — vanilla JS, no build step. */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  lang: localStorage.getItem("hankki-lang") || "ko",
  campus: localStorage.getItem("hankki-campus") || "student",
  health: null,
  menu: null,
  meals: { items: [], total_kcal: 0, total_protein: 0 },
  report: null,
  weekMeals: [],
  foods: [],
  samples: [],
  file: null,
  previewUrl: null,
  prediction: null,
  items: [],
  alternatives: [],
  busy: false,
};

const UI = {
  menuTitle: { ko: "오늘의 학식", zh: "今日食堂" },
  tipTitle: { ko: "AI 한 끼 제안", zh: "AI 一餐建议" },
  tipBody: { ko: "국물은 절반만, 계란을 더하면 단백질 +6g", zh: "汤喝一半，加个鸡蛋更均衡" },
  tipCn: { ko: "汤喝一半，加个鸡蛋更均衡", zh: "국물은 절반만, 계란 +6g" },
  recentTitle: { ko: "최근 기록", zh: "最近记录" },
  reportLink: { ko: "리포트 ›", zh: "报告 ›" },
  fabLabel: { ko: "사진으로 기록", zh: "拍照记录" },
  cameraTitle: { ko: "AI 식사 기록", zh: "AI 饮食记录" },
  cameraLead: { ko: "주요 음식 1–3개를 인식합니다. 결과는 항상 수정할 수 있어요.", zh: "识别 1–3 个主要菜品；结果永远可以修改。" },
  dropTitle: { ko: "사진을 찍거나 업로드", zh: "拍照或上传照片" },
  dropSub: { ko: "JPG / PNG · 최대 12MB", zh: "JPG / PNG · 最大 12MB" },
  samplesTitle: { ko: "샘플로 체험", zh: "用样张体验" },
  samplesHint: { ko: "API 없이 바로 인식", zh: "无需准备图片" },
  predictLabel: { ko: "AI로 인식하기", zh: "AI 识别" },
  loadingTitle: { ko: "AI가 사진을 읽고 있어요", zh: "AI 正在读这张照片" },
  loadingSub: { ko: "CLIP zero-shot · CPU · 1–3초", zh: "CLIP zero-shot · CPU · 1–3 秒" },
  resultTitle: { ko: "이렇게 인식했어요", zh: "识别结果" },
  resultSub: { ko: "결과가 다르면 직접 수정하세요.", zh: "结果不对可以直接改。" },
  altTitle: { ko: "다른 후보", zh: "其他候选" },
  altHint: { ko: "클릭해서 추가", zh: "点击添加" },
  saveMeal: { ko: "이대로 기록하기", zh: "就按这个记录" },
  saveHint: { ko: "저장 후 오늘 리포트에 반영됩니다.", zh: "保存后会进入今天的报告。" },
  reportTitle: { ko: "이번 주 리포트", zh: "本周报告" },
  chartTitle: { ko: "하루 단백질", zh: "每日蛋白质" },
  logTitle: { ko: "이번 주 기록", zh: "本周记录" },
  logHint: { ko: "demo seed 포함", zh: "含演示数据" },
};

const WD_KO = ["일", "월", "화", "수", "목", "금", "토"];
const WD_ZH = ["日", "一", "二", "三", "四", "五", "六"];

function t(key) {
  const item = UI[key];
  return item ? item[state.lang] || item.ko : key;
}

function fmt(n) {
  const v = Number(n || 0);
  return Math.round(v).toLocaleString("ko-KR");
}

function esc(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function isoDay(d = new Date()) {
  const x = new Date(d);
  return `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
}

function dateLabel(d = new Date()) {
  const x = new Date(d);
  if (state.lang === "zh") return `${x.getMonth() + 1}月${x.getDate()}日 周${WD_ZH[x.getDay()]}`;
  return `${x.getMonth() + 1}월 ${x.getDate()}일 ${WD_KO[x.getDay()]}요일`;
}

function timeLabel(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2400);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  let body = null;
  const text = await res.text();
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!res.ok) {
    const detail = body && body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return body;
}

function applyLang() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "ko";
  localStorage.setItem("hankki-lang", state.lang);
  $("#langBtn").textContent = state.lang === "ko" ? "中" : "KO";
  Object.keys(UI).forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.textContent = t(id);
  });
  $$("[data-ko][data-zh]").forEach((el) => { el.textContent = el.dataset[state.lang]; });
  renderAll();
}

function setView(name) {
  $$(".view").forEach((v) => { v.hidden = v.id !== `view-${name}`; });
  $$(".tab[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  if (name === "report") loadReport();
  if (name === "camera") loadSamples();
}

async function refreshAll() {
  api("/api/health").then((health) => {
    state.health = health;
    const dot = $("#liveDot");
    if (health.ai && health.ai.ready) {
      dot.className = "live-dot on";
      dot.title = `AI ready · ${health.ai.model}`;
    } else {
      dot.className = "live-dot err";
      dot.title = (health.ai && health.ai.error) || "AI loading";
    }
  }).catch((e) => {
    const dot = $("#liveDot");
    dot.className = "live-dot err";
    dot.title = e.message;
  });

  const [menu, meals, report] = await Promise.all([
    api(`/api/menu/today?campus=${encodeURIComponent(state.campus)}`).catch(() => null),
    api(`/api/meals?day=${isoDay()}`).catch(() => null),
    api(`/api/report/week?end=${isoDay()}`).catch(() => null),
  ]);
  state.menu = menu;
  state.meals = meals || { items: [], total_kcal: 0, total_protein: 0 };
  state.report = report;
  renderToday();
  renderReport();
  renderMenu();
}

function renderAll() {
  renderToday();
  renderMenu();
  renderReport();
  if (state.prediction) renderResult();
  if (state.samples.length) renderSamples();
}

function renderToday() {
  $("#dateLine").textContent = dateLabel();
  const goal = (state.report && state.report.goals && state.report.goals.kcal) || 1800;
  const consumed = state.meals.total_kcal || 0;
  const remaining = Math.max(0, Math.round(goal - consumed));
  const pct = Math.min(100, Math.round((consumed / goal) * 100));
  $("#helloTitle").innerHTML = state.lang === "zh"
    ? `今天午餐，<br>还剩 <em>${fmt(remaining)} kcal</em>`
    : `오늘 점심,<br><em>${fmt(remaining)} kcal</em> 남았어요`;
  $("#helloSub").textContent = state.lang === "zh"
    ? `已摄入 ${fmt(consumed)} · 目标 ${fmt(goal)} kcal`
    : `섭취 ${fmt(consumed)} · 목표 ${fmt(goal)} kcal`;
  const ring = $("#ring");
  ring.style.setProperty("--p", String(pct));
  $("#ringPct").textContent = `${pct}%`;
  $("#ringLabel").textContent = state.lang === "zh" ? "完成" : "달성";

  const protein = state.meals.items.reduce((s, m) => s + (m.total_protein || 0), 0);
  const sodium = state.meals.items.reduce((s, m) => s + (m.total_sodium || 0), 0);
  $("#todayProtein").textContent = `${Math.round(protein)}g`;
  $("#todaySodium").textContent = `${fmt(sodium)}mg`;
  $("#todayMeals").textContent = String(state.meals.items.length);

  const insight = state.report && state.report.insights && state.report.insights[0];
  if (insight) {
    $("#tipTitle").textContent = state.lang === "zh" ? insight.title_zh : insight.title_ko;
    $("#tipBody").textContent = state.lang === "zh" ? insight.body_zh : insight.body_ko;
    $("#tipCn").textContent = state.lang === "zh" ? insight.body_ko : insight.body_zh;
  }

  const list = $("#recentList");
  const meals = (state.meals.items || []).slice(-3).reverse();
  if (!meals.length) {
    list.innerHTML = `<div class="empty">${state.lang === "zh" ? "还没有记录。拍一张餐盘，15 秒记完。" : "아직 기록이 없어요. tray 사진 한 장으로 15초면 끝나요."}</div>`;
    return;
  }
  list.innerHTML = meals.map((m) => {
    const names = m.items.map((i) => state.lang === "zh" ? i.name_zh : i.name_ko).join(" · ");
    return `<div class="recent">
      <span class="time">${timeLabel(m.eaten_at)}</span>
      <div class="desc"><b>${esc(names)}</b><span>${m.source === "photo" ? (state.lang === "zh" ? "照片记录" : "사진 기록") : (state.lang === "zh" ? "手动记录" : "수동 기록")}</span></div>
      <span class="kcal">${fmt(m.total_kcal)} kcal</span>
    </div>`;
  }).join("");
}

function renderMenu() {
  const card = $("#menuCard");
  if (!state.menu) {
    card.innerHTML = `<div class="empty">${state.lang === "zh" ? "今天没有菜单数据。" : "오늘 메뉴를 불러오지 못했어요."}</div>`;
    return;
  }
  const menu = state.menu;
  $("#campusBtn").textContent = `${state.lang === "zh" ? menu.campus.name_zh : menu.campus.name_ko} ›`;
  const main = menu.items[0];
  if (!main) {
    card.innerHTML = `<div class="empty">${state.lang === "zh" ? "今天休息。" : "오늘은 운영하지 않아요."}</div>`;
    return;
  }
  const price = menu.items.reduce((s, i) => s + (i.price || 0), 0);
  const highProtein = menu.total.protein >= 25;
  const highSodium = menu.total.sodium >= 1500;
  const badgeText = highProtein
    ? (state.lang === "zh" ? "高蛋白" : "고단백")
    : highSodium
      ? (state.lang === "zh" ? "高钠" : "고나트륨")
      : (state.lang === "zh" ? "均衡" : "균형");
  const badgeStyle = highSodium && !highProtein ? "background:#F6DCD4;color:#9B3C2C" : "";
  const rows = menu.items.map((i) => `<div class="mrow"><span>${esc(state.lang === "zh" ? i.zh : i.ko)} <span class="zh">${esc(state.lang === "zh" ? i.ko : i.zh)}</span></span><b>${fmt(i.kcal)} kcal</b></div>`).join("");
  card.innerHTML = `
    <div class="menu-top">
      <div class="menu-emoji">🍚</div>
      <div class="menu-title"><b>${esc(state.lang === "zh" ? main.zh : main.ko)}</b><span>${esc(state.lang === "zh" ? menu.campus.name_zh : menu.campus.name_ko)} · ${esc(menu.campus.hours)}</span></div>
      <span class="badge" style="${badgeStyle}">${badgeText}</span>
    </div>
    <div class="menu-list">${rows}</div>
    <div class="menu-total"><span>${state.lang === "zh" ? "合计" : "총"} ${fmt(menu.total.kcal)} kcal · ${state.lang === "zh" ? "蛋白质" : "단백질"} ${Math.round(menu.total.protein)}g</span><span>${price ? (state.lang === "zh" ? `1人 ${fmt(price)}韩元` : `1인 ${fmt(price)}원`) : ""}</span></div>
    <div class="menu-actions">
      <button class="btn ghost" data-menu-action="detail">${state.lang === "zh" ? "查看菜单" : "식단 보기"}</button>
      <button class="btn primary" data-menu-action="camera">${state.lang === "zh" ? "拍照记录" : "사진으로 기록"}</button>
    </div>`;
}

function renderReport() {
  const report = state.report;
  if (!report) return;
  $("#reportRange").textContent = `${report.start} – ${report.end} · ${state.lang === "zh" ? "本周营养报告" : "이번 주 영양 리포트"}`;
  const primary = report.insights[0] || {};
  const title = state.lang === "zh" ? primary.title_zh : primary.title_ko;
  const body = state.lang === "zh" ? primary.body_zh : primary.body_ko;
  const pretty = esc(title || "").replace(/(\d+%)/, "<em>$1</em>");
  $("#reportHeadline").innerHTML = `<h1>${pretty || (state.lang === "zh" ? "本周报告" : "이번 주 리포트")}</h1><p>${esc(body || "")}</p>`;

  const goal = report.goals.protein || 105;
  const max = Math.max(goal * 1.15, ...report.days.map((d) => d.protein), 1);
  const bars = report.days.map((d) => {
    const h = Math.max(6, Math.round((d.protein / max) * 100));
    const low = d.protein < goal;
    const wd = new Date(d.date + "T00:00:00").getDay();
    const label = state.lang === "zh" ? WD_ZH[wd] : WD_KO[wd];
    return `<div class="barcol"><div class="bar ${low ? "low" : ""}" style="height:${h}%"><span class="v">${Math.round(d.protein)}</span></div><span class="d">${label}</span></div>`;
  }).join("");
  const goalTop = Math.max(4, Math.round((1 - goal / max) * 100));
  $("#chart").innerHTML = `<div class="goal" style="top:${goalTop}%"></div><div class="bars">${bars}</div>`;
  $("#chartGoal").textContent = state.lang === "zh" ? `目标 ${goal}g` : `목표 ${goal}g`;
  $("#chartTitle").textContent = t("chartTitle");

  const insights = report.insights.slice(0, 2);
  $("#insightRow").innerHTML = insights.map((i) => `<div class="insight"><div class="k">${esc(i.type.toUpperCase())}</div><b>${esc(state.lang === "zh" ? i.title_zh : i.title_ko)}</b><span>${esc(state.lang === "zh" ? i.body_zh : i.body_ko)}</span></div>`).join("");

  $("#streakCard").innerHTML = `
    <span class="flame">🔥</span>
    <div><b>${state.lang === "zh" ? `连续记录 ${report.streak} 天` : `${report.streak}일 연속 기록 중`}</b>
      <p>${state.lang === "zh" ? "记录本身就是目标。下周先做“蛋白质 +1”。" : "기록 자체가 목표예요. 이번 주는 단백질 +1에 집중해보세요."}</p>
      <span class="cn">${state.lang === "zh" ? "기록 자체가 목표" : "记录本身就是目标"}</span>
    </div>
    <div class="num">${report.streak}<small>DAY STREAK</small></div>`;

  const meals = state.weekMeals || [];
  $("#reportMeals").innerHTML = meals.length
    ? meals.slice(0, 8).map((m) => {
        const names = m.items.map((i) => state.lang === "zh" ? i.name_zh : i.name_ko).join(" · ");
        return `<div class="recent"><span class="time">${m.date.slice(5)}</span><div class="desc"><b>${esc(names)}</b><span>${timeLabel(m.eaten_at)} · ${m.source}</span></div><span class="kcal">${fmt(m.total_kcal)} kcal</span></div>`;
      }).join("")
    : `<div class="empty">${state.lang === "zh" ? "这周还没有记录。" : "이번 주 기록이 없어요."}</div>`;
}

async function loadReport() {
  try {
    const [report, week] = await Promise.all([
      api(`/api/report/week?end=${isoDay()}`),
      api(`/api/meals/week?end=${isoDay()}`),
    ]);
    state.report = report;
    state.weekMeals = week.items || [];
    renderReport();
  } catch (e) {
    toast(e.message);
  }
}

/* ---------- camera ---------- */
async function loadSamples() {
  if (state.samples.length) { renderSamples(); return; }
  try {
    const data = await api("/api/samples");
    state.samples = data.items || [];
    renderSamples();
  } catch { /* ignore */ }
}

function renderSamples() {
  const box = $("#samples");
  if (!state.samples.length) { box.innerHTML = ""; return; }
  box.innerHTML = state.samples.map((s) => `<button class="sample" data-sample="${esc(s.url)}" title="${esc(s.name)}"><img src="${esc(s.url)}" alt=""><span>${esc(s.name.replace(/\.[a-z]+$/i, ""))}</span></button>`).join("");
}

function setFile(file) {
  if (!file || !file.type.startsWith("image/")) { toast(state.lang === "zh" ? "请选择图片文件" : "이미지 파일만 가능해요"); return; }
  if (file.size > 12 * 1024 * 1024) { toast(state.lang === "zh" ? "图片超过 12MB" : "12MB 이하만 가능해요"); return; }
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.file = file;
  state.previewUrl = URL.createObjectURL(file);
  $("#previewImg").src = state.previewUrl;
  $("#previewWrap").hidden = false;
  $("#previewBadge").textContent = "READY";
  $("#predictBtn").disabled = false;
  $("#result").hidden = true;
  state.prediction = null;
  state.items = [];
  $("#previewWrap").scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearImage() {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.file = null;
  state.previewUrl = null;
  state.prediction = null;
  state.items = [];
  $("#previewWrap").hidden = true;
  $("#result").hidden = true;
  $("#predictBtn").disabled = true;
  $("#fileInput").value = "";
}

async function predict() {
  if (!state.file || state.busy) return;
  state.busy = true;
  $("#predictBtn").disabled = true;
  $("#loading").hidden = false;
  $("#result").hidden = true;
  const started = performance.now();
  try {
    const form = new FormData();
    form.append("file", state.file, state.file.name || "meal.jpg");
    const result = await api("/api/predict", { method: "POST", body: form });
    state.prediction = result;
    state.items = (result.items || []).map((it) => ({ ...it, portion: 1.0 }));
    state.alternatives = result.alternatives || [];
    $("#previewBadge").textContent = `AI · ${(result.latency_ms / 1000).toFixed(1)}s`;
    renderResult();
    $("#result").hidden = false;
    $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
    if (result.uncertain) toast(state.lang === "zh" ? "置信度偏低，请确认或改选" : "확신도가 낮아요. 결과를 확인해 주세요.");
  } catch (e) {
    toast(e.message);
  } finally {
    state.busy = false;
    $("#predictBtn").disabled = !state.file;
    $("#loading").hidden = true;
  }
}

function itemNutrition(item) {
  const base = item.nutrition || {};
  const p = item.portion || 1;
  return {
    kcal: (base.kcal || 0) * p,
    protein: (base.protein || 0) * p,
    carbs: (base.carbs || 0) * p,
    fat: (base.fat || 0) * p,
    sodium: (base.sodium || 0) * p,
  };
}

function totals() {
  return state.items.reduce((acc, it) => {
    const n = itemNutrition(it);
    Object.keys(acc).forEach((k) => { acc[k] += n[k]; });
    return acc;
  }, { kcal: 0, protein: 0, carbs: 0, fat: 0, sodium: 0 });
}

function renderResult() {
  if (!state.prediction) return;
  const total = totals();
  $("#resultCount").textContent = state.lang === "zh" ? `${state.items.length} 项` : `${state.items.length}개`;
  $("#resultMacro").innerHTML = `
    <div><b>${fmt(total.kcal)}<i>kcal</i></b><span>${state.lang === "zh" ? "热量" : "칼로리"}</span></div>
    <div><b>${fmt(total.carbs)}<i>g</i></b><span>${state.lang === "zh" ? "碳水" : "탄수화물"}</span></div>
    <div><b>${fmt(total.protein)}<i>g</i></b><span>${state.lang === "zh" ? "蛋白质" : "단백질"}</span></div>
    <div><b>${fmt(total.fat)}<i>g</i></b><span>${state.lang === "zh" ? "脂肪" : "지방"}</span></div>`;
  $("#resultItems").innerHTML = state.items.map((it, idx) => {
    const n = itemNutrition(it);
    return `<div class="item">
      <span class="swatch"></span>
      <div class="nm"><b>${esc(state.lang === "zh" ? it.name_zh : it.name_ko)}</b><span>${esc(state.lang === "zh" ? it.name_ko : it.name_zh)} · ${Math.round((it.confidence || 0) * 100)}% · ${fmt(n.kcal)} kcal</span></div>
      <button class="del" data-del="${idx}" aria-label="remove">×</button>
    </div>
    <div class="portion" data-portion-wrap="${idx}">
      <button data-portion="0.75" data-idx="${idx}" class="${it.portion === 0.75 ? "on" : ""}">S</button>
      <button data-portion="1" data-idx="${idx}" class="${it.portion === 1 ? "on" : ""}">M</button>
      <button data-portion="1.25" data-idx="${idx}" class="${it.portion === 1.25 ? "on" : ""}">L</button>
    </div>`;
  }).join("") || `<div class="empty">${state.lang === "zh" ? "没有识别到菜品，请手动添加。" : "인식된 음식이 없어요. 직접 추가해 주세요."}</div>`;

  const selected = new Set(state.items.map((i) => i.food_id));
  const alts = state.alternatives.filter((a) => !selected.has(a.food_id) && (a.confidence || 0) >= 0.03).slice(0, 5);
  $("#alts").innerHTML = alts.map((a) => `<button class="alt" data-alt="${esc(a.food_id)}">${esc(state.lang === "zh" ? a.name_zh : a.name_ko)} <span class="conf">${Math.round((a.confidence || 0) * 100)}%</span></button>`).join("") || `<span class="tiny">${state.lang === "zh" ? "没有更多候选" : "더 이상 후보가 없어요"}</span>`;
}

function addAlternative(foodId) {
  const alt = state.alternatives.find((a) => a.food_id === foodId);
  if (!alt) return;
  if (state.items.some((i) => i.food_id === foodId)) { toast(state.lang === "zh" ? "已经在列表里" : "이미 목록에 있어요"); return; }
  state.items.push({ ...alt, portion: 1.0, confidence: alt.confidence || 0 });
  renderResult();
}

async function loadFoods() {
  if (state.foods.length) return;
  try {
    const data = await api("/api/foods");
    state.foods = data.items || [];
    const sel = $("#manualSelect");
    sel.innerHTML = `<option value="">${state.lang === "zh" ? "+ 手动添加菜品" : "+ 음식 직접 추가"}</option>` + state.foods.map((f) => `<option value="${esc(f.id)}">${esc(state.lang === "zh" ? f.zh : f.ko)} · ${fmt(f.kcal)} kcal</option>`).join("");
  } catch { /* ignore */ }
}

function manualAdd() {
  const id = $("#manualSelect").value;
  if (!id) return;
  const food = state.foods.find((f) => f.id === id);
  if (!food) return;
  if (state.items.some((i) => i.food_id === id)) { toast(state.lang === "zh" ? "已经在列表里" : "이미 목록에 있어요"); return; }
  state.items.push({
    food_id: food.id,
    name_ko: food.ko,
    name_zh: food.zh,
    confidence: 1,
    portion: 1,
    nutrition: { kcal: food.kcal, protein: food.protein, carbs: food.carbs, fat: food.fat, sodium: food.sodium },
  });
  renderResult();
  $("#manualSelect").value = "";
}

async function saveMeal() {
  if (state.busy) return;
  if (!state.items.length) { toast(state.lang === "zh" ? "至少添加一项" : "최소 한 개는 추가해 주세요"); return; }
  state.busy = true;
  $("#saveMeal").disabled = true;
  try {
    const hour = new Date().getHours();
    const mealType = hour < 10 ? "breakfast" : hour < 15 ? "lunch" : hour < 21 ? "dinner" : "snack";
    await api("/api/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meal_type: mealType,
        source: "photo",
        image_id: state.prediction ? state.prediction.image_id : null,
        items: state.items.map((i) => ({ food_id: i.food_id, portion: i.portion, confidence: i.confidence })),
      }),
    });
    toast(state.lang === "zh" ? "已记录，去报告看看" : "기록 완료! 리포트에서 확인하세요");
    clearImage();
    await refreshAll();
    setView("today");
  } catch (e) {
    toast(e.message);
  } finally {
    state.busy = false;
    $("#saveMeal").disabled = false;
  }
}

async function shareReport() {
  const text = state.lang === "zh" ? "한끼AI 本周营养报告" : "한끼AI 이번 주 영양 리포트";
  if (navigator.share) {
    try { await navigator.share({ title: "한끼AI", text, url: location.href }); return; } catch { /* cancelled */ }
  }
  try { await navigator.clipboard.writeText(location.href); toast(state.lang === "zh" ? "链接已复制" : "링크를 복사했어요"); }
  catch { toast(location.href); }
}

/* ---------- events ---------- */
function bind() {
  $("#langBtn").addEventListener("click", () => { state.lang = state.lang === "ko" ? "zh" : "ko"; applyLang(); loadFoods(); });
  $$(".tab[data-view]").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  $$("[data-goto]").forEach((el) => el.addEventListener("click", (e) => { e.preventDefault(); setView(el.dataset.goto); }));
  $("#fabCamera").addEventListener("click", () => setView("camera"));
  $("#campusBtn").addEventListener("click", async (e) => {
    e.preventDefault();
    state.campus = state.campus === "student" ? "engineering" : "student";
    localStorage.setItem("hankki-campus", state.campus);
    try { state.menu = await api(`/api/menu/today?campus=${state.campus}`); renderMenu(); }
    catch { toast("메뉴를 불러오지 못했어요"); }
  });
  $("#menuCard").addEventListener("click", (e) => {
    const btn = e.target.closest("[data-menu-action]");
    if (!btn) return;
    if (btn.dataset.menuAction === "camera") setView("camera");
    else toast(state.lang === "zh" ? "完整菜单在 MVP 后可展开" : "전체 메뉴는 MVP 이후 제공할게요");
  });
  $("#dropzone").addEventListener("click", () => $("#fileInput").click());
  $("#fileInput").addEventListener("change", (e) => { const f = e.target.files && e.target.files[0]; if (f) setFile(f); });
  ["dragenter", "dragover"].forEach((ev) => $("#dropzone").addEventListener(ev, (e) => { e.preventDefault(); $("#dropzone").classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => $("#dropzone").addEventListener(ev, (e) => { e.preventDefault(); $("#dropzone").classList.remove("drag"); }));
  $("#dropzone").addEventListener("drop", (e) => { const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) setFile(f); });
  $("#clearImage").addEventListener("click", clearImage);
  $("#predictBtn").addEventListener("click", predict);
  $("#samples").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-sample]");
    if (!btn) return;
    try {
      const res = await fetch(btn.dataset.sample);
      const blob = await res.blob();
      const name = btn.dataset.sample.split("/").pop() || "sample.jpg";
      setFile(new File([blob], name, { type: blob.type || "image/jpeg" }));
    } catch { toast("샘플을 불러오지 못했어요"); }
  });
  $("#resultItems").addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) { state.items.splice(Number(del.dataset.del), 1); renderResult(); return; }
    const p = e.target.closest("[data-portion]");
    if (p) {
      const idx = Number(p.dataset.idx);
      if (state.items[idx]) { state.items[idx].portion = Number(p.dataset.portion); renderResult(); }
    }
  });
  $("#alts").addEventListener("click", (e) => { const b = e.target.closest("[data-alt]"); if (b) addAlternative(b.dataset.alt); });
  $("#manualAdd").addEventListener("click", manualAdd);
  $("#manualSelect").addEventListener("focus", loadFoods);
  $("#saveMeal").addEventListener("click", saveMeal);
  $("#shareReport").addEventListener("click", shareReport);
}

async function init() {
  const params = new URLSearchParams(location.search);
  if (params.get("lang") === "zh") state.lang = "zh";
  if (params.get("lang") === "ko") state.lang = "ko";
  bind();
  applyLang();
  await refreshAll();
  await loadFoods();
  const view = params.get("view");
  if (["today", "camera", "report"].includes(view)) setView(view);
  else setView("today");
  const sample = params.get("sample");
  if (sample) {
    try {
      const res = await fetch(`/samples/${encodeURIComponent(sample)}`);
      if (res.ok) {
        const blob = await res.blob();
        setView("camera");
        setFile(new File([blob], sample, { type: blob.type || "image/jpeg" }));
        if (params.get("predict") === "1") setTimeout(predict, 300);
      }
    } catch { /* ignore */ }
  }
}

init();
