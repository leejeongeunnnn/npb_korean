/* 마이팀 공간분석: 선수 프로필 · 출신지 단계구분도 · 원정 거리 분석 · 구장 날씨
   app.js 의 전역(DATA, MY_TEAM, esc, emptyBox, readable, colorOf, todayStr, allTeams)을 사용한다. */

const GEO_CACHE = {};
async function getJSON(path) {
  if (path in GEO_CACHE) return GEO_CACHE[path];
  try {
    const r = await fetch(`${path}?t=${Math.floor(Date.now() / 600000)}`, { cache: "no-store" });
    GEO_CACHE[path] = r.ok ? await r.json() : null;
  } catch (e) { GEO_CACHE[path] = null; }
  return GEO_CACHE[path];
}
const loadingBox = (msg = "불러오는 중...") => `<div class="empty"><div class="spinner" style="margin:0 auto 10px"></div>${esc(msg)}</div>`;
const PREP_MSG = "아직 수집되지 않았습니다. 하루 1회 자동 수집(새벽 4시 반)이 끝나면 표시됩니다.";

/* ---------- 공간 계산 유틸 ---------- */
const R_EARTH = 6371.0088;   // 지구 평균 반경(km)
const rad = (d) => d * Math.PI / 180, deg = (r) => r * 180 / Math.PI;
function haversine(a, b) {   // 대권거리(km)
  const dLat = rad(b[0] - a[0]), dLon = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(h)));
}
function bearing(a, b) {     // 초기 방위각(도, 북=0 시계방향)
  const y = Math.sin(rad(b[1] - a[1])) * Math.cos(rad(b[0]));
  const x = Math.cos(rad(a[0])) * Math.sin(rad(b[0])) - Math.sin(rad(a[0])) * Math.cos(rad(b[0])) * Math.cos(rad(b[1] - a[1]));
  return (deg(Math.atan2(y, x)) + 360) % 360;
}
const DIR16 = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동", "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"];
const dirName = (b) => DIR16[Math.round(b / 22.5) % 16];
function greatCircle(a, b, n = 48) {   // 대권 경로 보간점 (구면 선형보간)
  const [φ1, λ1, φ2, λ2] = [rad(a[0]), rad(a[1]), rad(b[0]), rad(b[1])];
  const d = 2 * Math.asin(Math.sqrt(Math.sin((φ2 - φ1) / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin((λ2 - λ1) / 2) ** 2));
  if (d === 0) return [a, b];
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const f = i / n, A = Math.sin((1 - f) * d) / Math.sin(d), B = Math.sin(f * d) / Math.sin(d);
    const x = A * Math.cos(φ1) * Math.cos(λ1) + B * Math.cos(φ2) * Math.cos(λ2);
    const y = A * Math.cos(φ1) * Math.sin(λ1) + B * Math.cos(φ2) * Math.sin(λ2);
    const z = A * Math.sin(φ1) + B * Math.sin(φ2);
    pts.push([deg(Math.atan2(z, Math.sqrt(x * x + y * y))), deg(Math.atan2(y, x))]);
  }
  return pts;
}
function pointInRing(pt, ring) {   // 광선 투사법 (ring: [lon,lat][])
  let inside = false; const [x, y] = [pt[1], pt[0]];
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function prefOfPoint(gj, latlon) {
  for (const f of gj.features)
    for (const poly of f.geometry.coordinates)
      if (pointInRing(latlon, poly[0]) && !poly.slice(1).some(h => pointInRing(latlon, h))) return f.properties;
  return null;
}
const median = (arr) => { if (!arr.length) return 0; const s = [...arr].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const km = (v) => `${Math.round(v).toLocaleString("ko-KR")} km`;
const pct = (a, b) => b ? `${Math.round(a / b * 100)}%` : "-";

/* 지도 공통 - 배경지도: Esri 다크 그레이 (API 키 불필요) */
const MAPS = {};
function baseTiles() {
  return L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
    attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ", maxZoom: 16,
  });
}
function makeMap(id, center = [36.5, 137.5], zoom = 5) {
  if (MAPS[id]) { MAPS[id].remove(); delete MAPS[id]; }
  if (typeof L === "undefined") return null;
  const m = L.map(id, { zoomSnap: 0.5, scrollWheelZoom: false }).setView(center, zoom);
  baseTiles().addTo(m);
  MAPS[id] = m;
  setTimeout(() => m.invalidateSize(), 150);
  return m;
}
const mapFallback = (el) => { el.innerHTML = emptyBox("지도 라이브러리를 불러오지 못했습니다. 새로고침해 보세요."); };

async function teamProfiles(teamName) {
  const idx = await getJSON("data/profiles/index.json");
  const code = idx && idx.teams && idx.teams[teamName] && idx.teams[teamName].code;
  if (!code) return null;
  const d = await getJSON(`data/profiles/${code}.json`);
  return d ? { ...d, updated_at: idx.updated_at } : null;
}
const normName = (s) => (s || "").replace(/[\s　]/g, "");
const PLAYER_POS = ["투수", "포수", "내야수", "외야수"];
const isPlayer = (p) => PLAYER_POS.includes(p.pos);   // 감독·코치 등 스태프 제외

/* ============================================================
   1) 선수 프로필
   ============================================================ */
const PF = { pos: "전체", q: "", ikusei: true, sort: "no" };
async function renderProfiles(el, team) {
  el.innerHTML = loadingBox("선수 프로필을 불러오는 중...");
  const d = await teamProfiles(team.name);
  if (!d || !d.players || !d.players.length) { el.innerHTML = emptyBox(PREP_MSG); return; }
  const players = d.players;
  const batMap = new Map((DATA.batters || []).map(b => [normName(b.name_jp), b]));
  const pitMap = new Map((DATA.pitchers || []).map(b => [normName(b.name_jp), b]));

  const draw = () => {
    let list = players.filter(p => (PF.pos === "전체" ? isPlayer(p) : PF.pos === "코칭스태프" ? !isPlayer(p) : p.pos === PF.pos) && (PF.ikusei || !p.ikusei)
      && (!PF.q || p.name.includes(PF.q) || p.name_jp.includes(PF.q) || (p.bp_ko || "").includes(PF.q)
          || (p.career || []).some(c => c.ko.includes(PF.q) || c.ja.includes(PF.q))));
    const num = (p) => parseInt(p.no) || 9999;
    const sorters = {
      no: (a, b) => num(a) - num(b), age: (a, b) => (a.age || 99) - (b.age || 99),
      height: (a, b) => (b.height || 0) - (a.height || 0), bp: (a, b) => (a.pref_id || 99) - (b.pref_id || 99),
    };
    list.sort(sorters[PF.sort]);
    const avg = (k) => { const v = list.map(p => p[k]).filter(Boolean); return v.length ? (v.reduce((a, b) => a + b, 0) / v.length) : 0; };
    const lefty = list.filter(p => (p.hand || "").startsWith("좌")).length;

    let h = `<div class="pf-summary">
      <div><b>${list.length}</b><span>명</span></div>
      <div><b>${avg("age").toFixed(1)}</b><span>평균 나이</span></div>
      <div><b>${avg("height").toFixed(1)}</b><span>평균 키(cm)</span></div>
      <div><b>${avg("weight").toFixed(1)}</b><span>평균 몸무게(kg)</span></div>
      <div><b>${pct(lefty, list.length)}</b><span>좌투 비율</span></div>
    </div><div class="pf-grid">`;
    list.forEach(p => {
      const bat = batMap.get(normName(p.name_jp)), pit = pitMap.get(normName(p.name_jp));
      const stat = pit ? `평균자책 ${Number(pit.era).toFixed(2)} · ${pit.w}승 ${pit.l}패 · ${pit.so}탈삼진`
                 : bat ? `타율 ${Number(bat.avg).toFixed(3).replace(/^0/, "")} · ${bat.hr}홈런 · ${bat.sb}도루` : "";
      h += `<div class="card pf-card">
        <div class="pf-head">
          <span class="pf-no" style="color:${readable(team.color)}">${esc(p.no || "-")}</span>
          <div class="pf-names"><div class="pf-name">${esc(p.name)}</div><div class="pf-jp">${esc(p.name_jp)}</div></div>
          <div class="pf-badges"><span class="pf-pos">${esc(p.pos)}</span>${p.ikusei ? '<span class="pf-ik">육성</span>' : ""}</div>
        </div>
        ${stat ? `<div class="pf-stat">📊 올해 ${esc(stat)}</div>` : ""}
        <div class="pf-row"><span>🎂</span>${esc(p.birth || "-")}${p.age ? ` (만 ${p.age}세)` : ""}</div>
        <div class="pf-row"><span>📍</span>${esc(p.bp_ko || "미상")}${p.region ? ` <em>${esc(p.region)}</em>` : ""}</div>
        <div class="pf-row"><span>📏</span>${p.height ? `${p.height}cm` : "-"} / ${p.weight ? `${p.weight}kg` : "-"} · ${esc(p.hand || "-")}${p.blood ? ` · ${esc(p.blood)}형` : ""}</div>
        <div class="pf-row"><span>🏫</span><span class="pf-career">${(p.career || []).map(c => `<span title="${esc(c.ja)}">${esc(c.ko || c.ja)}</span>${c.koshien ? '<i class="pf-koshien" title="고시엔(전국고교야구) 출전">고시엔</i>' : ""}`).join(" → ") || "-"}</span></div>
        <div class="pf-row"><span>📝</span>${esc(p.draft || "드래프트 정보 없음")}${p.years ? ` · 프로 ${p.years}년차` : ""}</div>
      </div>`;
    });
    h += `</div>`;
    el.querySelector("#pf-list").innerHTML = list.length ? h : emptyBox("조건에 맞는 선수가 없습니다.");
  };

  el.innerHTML = `<div class="controls pf-controls">
      <input id="pf-q" type="search" placeholder="이름·출신지·학교 검색" value="${esc(PF.q)}">
      <select id="pf-sort">
        <option value="no">등번호순</option><option value="age">나이 어린순</option>
        <option value="height">키 큰순</option><option value="bp">출신지(북→남)</option>
      </select>
      <label class="pf-check"><input type="checkbox" id="pf-ik" ${PF.ikusei ? "checked" : ""}> 육성선수 포함</label>
    </div>
    <div class="stage-tabs">${["전체", "투수", "포수", "내야수", "외야수", "코칭스태프"].map(x =>
      `<button class="stage-chip ${PF.pos === x ? "active" : ""}" data-pos="${x}">${x}</button>`).join("")}</div>
    <div id="pf-list"></div>
    <p class="hint">출처: Yahoo! 재팬 스포츠 선수 정보 (갱신 ${esc(d.updated_at || "")}). 이름은 번역 사전 또는 일본어 읽기를 국립국어원 표기법으로 옮긴 것이고, 학교명은 기계 번역이라 어색할 수 있어요(학교명에 마우스를 올리면 원문).</p>`;
  el.querySelector("#pf-sort").value = PF.sort;
  el.querySelector("#pf-q").addEventListener("input", (e) => { PF.q = e.target.value.trim(); draw(); });
  el.querySelector("#pf-sort").addEventListener("change", (e) => { PF.sort = e.target.value; draw(); });
  el.querySelector("#pf-ik").addEventListener("change", (e) => { PF.ikusei = e.target.checked; draw(); });
  el.querySelectorAll("[data-pos]").forEach(b => b.addEventListener("click", () => {
    PF.pos = b.dataset.pos; el.querySelectorAll("[data-pos]").forEach(x => x.classList.toggle("active", x === b)); draw();
  }));
  draw();
}

/* ============================================================
   2) 출신지 지도 (도도부현 단계구분도)
   ============================================================ */
const OG = { group: "전체", ikusei: true };
const ORIGIN_CLASSES = [0, 1, 2, 4, 7];          // 0 | 1 | 2-3 | 4-6 | 7+
function originColor(n) {
  if (!n) return "transparent";
  const pal = ["#3b2a0a", "#7c4a03", "#c2720a", "#f59e0b", "#fde68a"];
  let i = 0; ORIGIN_CLASSES.forEach((c, k) => { if (n >= c) i = k; });
  return pal[i];
}
async function renderOrigin(el, team) {
  el.innerHTML = loadingBox("출신지 지도를 준비하는 중...");
  const [d, gj, prefs] = await Promise.all([teamProfiles(team.name), getJSON("data/geo/prefectures.geojson"), getJSON("data/geo/prefectures.json")]);
  if (!d || !d.players || !d.players.length) { el.innerHTML = emptyBox(PREP_MSG); return; }
  if (!gj || !prefs) { el.innerHTML = emptyBox("경계 데이터를 불러오지 못했습니다."); return; }
  const prefById = new Map(prefs.map(p => [p.id, p]));
  const home = [team.lat, team.lon];
  const homePref = prefOfPoint(gj, home);
  const homeRegion = homePref ? prefById.get(homePref.id).region : null;

  el.innerHTML = `<div class="stage-tabs">${["전체", "투수", "야수"].map(x =>
      `<button class="stage-chip ${OG.group === x ? "active" : ""}" data-g="${x}">${x}</button>`).join("")}
      <label class="pf-check" style="margin-left:4px"><input type="checkbox" id="og-ik" ${OG.ikusei ? "checked" : ""}> 육성선수 포함</label></div>
    <div class="geo-layout">
      <div><div id="og-map" class="geo-map"></div>
        <div class="legend" id="og-legend"></div></div>
      <div id="og-side"></div>
    </div>
    <div id="og-stats"></div>
    <p class="hint">경계: 地球地図日本(일본 국토지리원) · 거리는 각 도도부현 현청 소재지에서 홈구장까지의 대권거리입니다. 해외 출신 선수는 지도 대신 아래 목록에 표시돼요.</p>`;

  let map = null, layer = null;
  const draw = () => {
    const ps = d.players.filter(p => isPlayer(p) && (OG.ikusei || !p.ikusei) &&
      (OG.group === "전체" || (OG.group === "투수" ? p.pos === "투수" : p.pos !== "투수")));
    const jp = ps.filter(p => p.bp_type === "pref"), abroad = ps.filter(p => p.bp_type === "country");
    const byPref = new Map(); jp.forEach(p => { if (!byPref.has(p.pref_id)) byPref.set(p.pref_id, []); byPref.get(p.pref_id).push(p); });

    // --- 지도
    if (!map) map = makeMap("og-map", [36.8, 137.5], 4.5);
    if (!map) { mapFallback(el.querySelector("#og-map")); }
    else {
      if (layer) layer.remove();
      layer = L.geoJSON(gj, {
        style: (f) => { const n = (byPref.get(f.properties.id) || []).length;
          return { color: "#475569", weight: .6, fillColor: n ? originColor(n) : "#1e293b", fillOpacity: n ? .9 : .35 }; },
        onEachFeature: (f, lyr) => {
          const list = byPref.get(f.properties.id) || [];
          lyr.bindTooltip(`${esc(f.properties.ko)} · ${list.length}명`, { sticky: true });
          lyr.on("click", () => showSide(f.properties, list));
          lyr.on("mouseover", () => lyr.setStyle({ weight: 2, color: "#fff" }));
          lyr.on("mouseout", () => layer.resetStyle(lyr));
        },
      }).addTo(map);
      L.marker(home, { icon: L.divIcon({ className: "home-pin", html: "⭐", iconSize: [22, 22] }) })
        .addTo(map).bindTooltip(`홈구장 · ${esc(team.stadium)}`);
    }
    el.querySelector("#og-legend").innerHTML = `<span>선수 수</span>${[["1", 1], ["2-3", 2], ["4-6", 4], ["7+", 7]].map(([t, n]) =>
      `<i style="background:${originColor(n)}"></i>${t}`).join("")}<i class="hp">⭐</i>홈구장`;

    // --- 공간 통계
    const dists = jp.map(p => { const pr = prefById.get(p.pref_id); return { p, km: haversine([pr.lat, pr.lon], home) }; });
    const localN = homePref ? jp.filter(p => p.pref_id === homePref.id).length : 0;
    const regionN = homeRegion ? jp.filter(p => p.region === homeRegion).length : 0;
    const far = dists.slice().sort((a, b) => b.km - a.km)[0];
    const regions = ["홋카이도", "도호쿠", "간토", "주부", "긴키", "주고쿠", "시코쿠", "규슈·오키나와"];
    const regCount = regions.map(r => [r, jp.filter(p => p.region === r).length]);
    const maxReg = Math.max(1, ...regCount.map(x => x[1]));
    const top = [...byPref.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 5);
    const countries = {}; abroad.forEach(p => { (countries[p.bp_ko] = countries[p.bp_ko] || []).push(p); });

    el.querySelector("#og-stats").innerHTML = `
      <div class="geo-kpis">
        <div><b>${jp.length}</b><span>일본 출신</span></div>
        <div><b>${abroad.length}</b><span>해외 출신</span></div>
        <div><b>${pct(localN, jp.length)}</b><span>연고지(${esc(homePref ? homePref.ko : "-")}) 출신</span></div>
        <div><b>${pct(regionN, jp.length)}</b><span>같은 지방(${esc(homeRegion || "-")})</span></div>
        <div><b>${dists.length ? km(dists.reduce((a, b) => a + b.km, 0) / dists.length) : "-"}</b><span>고향→홈구장 평균</span></div>
        <div><b>${dists.length ? km(median(dists.map(x => x.km))) : "-"}</b><span>중앙값</span></div>
      </div>
      <div class="geo-two">
        <div class="card"><div class="mt-ph">🗾 지방별 분포</div>
          ${regCount.map(([r, n]) => `<div class="bar-row ${r === homeRegion ? "mine" : ""}"><span>${r}</span>
            <div class="bar"><i style="width:${n / maxReg * 100}%"></i></div><b>${n}</b></div>`).join("")}</div>
        <div class="card"><div class="mt-ph">🏆 출신 선수가 많은 도도부현</div>
          ${top.map(([id, l], i) => `<div class="mt-pl"><span>${i + 1}. ${esc(prefById.get(id).ko)}</span><span class="num"><b>${l.length}명</b> · ${km(haversine([prefById.get(id).lat, prefById.get(id).lon], home))}</span></div>`).join("") || '<div class="hint">-</div>'}
          ${far ? `<div class="hint" style="margin:10px 0 0">가장 먼 고향: <b>${esc(far.p.name)}</b> (${esc(far.p.bp_ko)}, ${km(far.km)})</div>` : ""}
        </div>
      </div>
      <div class="card"><div class="mt-ph">🌏 해외 출신 (${abroad.length}명)</div>
        ${Object.keys(countries).length ? Object.entries(countries).sort((a, b) => b[1].length - a[1].length).map(([c, l]) =>
          `<div class="mt-pl"><span>${esc(c)}</span><span class="num wrap">${l.map(p => esc(p.name)).join(", ")}</span></div>`).join("") : '<div class="hint" style="margin:0">없음</div>'}
      </div>
      <button class="btn-ghost" id="og-compare">📊 12개 구단 연고지 출신 비율 비교</button><div id="og-cmp"></div>`;
    el.querySelector("#og-compare").addEventListener("click", () => compareLocal(el.querySelector("#og-cmp"), gj, prefById));
    showSide(homePref, homePref ? (byPref.get(homePref.id) || []) : []);
  };

  const showSide = (props, list) => {
    const side = el.querySelector("#og-side");
    if (!props) { side.innerHTML = ""; return; }
    side.innerHTML = `<div class="card og-side"><div class="mt-ph">📍 ${esc(props.ko)} 출신 <span class="mt-sub">${list.length}명</span></div>
      ${list.length ? list.map(p => `<div class="mt-pl"><span>${esc(p.name)} <em class="pf-jp">${esc(p.pos)}${p.ikusei ? "·육성" : ""}</em></span><span class="num">#${esc(p.no)} · ${p.age ? p.age + "세" : ""}</span></div>`).join("")
        : '<div class="hint" style="margin:0">이 지역 출신 선수가 없습니다. 지도에서 색칠된 지역을 눌러 보세요.</div>'}</div>`;
  };

  el.querySelectorAll("[data-g]").forEach(b => b.addEventListener("click", () => {
    OG.group = b.dataset.g; el.querySelectorAll("[data-g]").forEach(x => x.classList.toggle("active", x === b)); draw();
  }));
  el.querySelector("#og-ik").addEventListener("change", (e) => { OG.ikusei = e.target.checked; draw(); });
  draw();
}

async function compareLocal(box, gj, prefById) {
  box.innerHTML = loadingBox("12개 구단 프로필을 불러오는 중...");
  const rows = [];
  for (const t of allTeams()) {
    const d = await teamProfiles(t.name);
    if (!d) continue;
    const hp = prefOfPoint(gj, [t.lat, t.lon]);
    const jp = d.players.filter(p => isPlayer(p) && p.bp_type === "pref");
    const local = hp ? jp.filter(p => p.pref_id === hp.id).length : 0;
    const region = hp ? prefById.get(hp.id).region : "";
    const reg = jp.filter(p => p.region === region).length;
    const avgKm = jp.length ? jp.reduce((a, p) => { const pr = prefById.get(p.pref_id); return a + haversine([pr.lat, pr.lon], [t.lat, t.lon]); }, 0) / jp.length : 0;
    rows.push({ t, local: jp.length ? local / jp.length : 0, reg: jp.length ? reg / jp.length : 0, avgKm, hp });
  }
  rows.sort((a, b) => b.reg - a.reg);
  const max = Math.max(...rows.map(r => r.reg), 0.01);
  box.innerHTML = `<div class="card"><div class="mt-ph">같은 지방 출신 비율 (높을수록 '지역 밀착형' 선수 구성)</div>
    ${rows.map(r => `<div class="bar-row ${r.t.name === MY_TEAM ? "mine" : ""}"><span>${esc(r.t.name)}</span>
      <div class="bar"><i style="width:${r.reg / max * 100}%;background:${readable(r.t.color)}"></i></div>
      <b>${Math.round(r.reg * 100)}%</b></div>`).join("")}
    <div class="hint" style="margin:10px 0 0">같은 도도부현 출신 비율과 고향까지 평균 거리: ${rows.map(r => `${esc(r.t.name.split(" ")[0])} ${Math.round(r.local * 100)}%·${km(r.avgKm)}`).join(" / ")}</div></div>`;
}

/* ============================================================
   3) 원정 거리 분석
   ============================================================ */
const TV = { route: false };
function analyzeTravel(games, venues, home) {
  const withCoord = games.map(g => { const v = venues[g.venue] || {}; return { ...g, v, ll: (v.lat != null) ? [v.lat, v.lon] : null }; })
    .filter(g => g.ll && g.state !== "cancel");
  // 이동 경로: 시즌 첫 경기 전 홈구장에서 출발, 경기 구장이 바뀔 때마다 이동한 것으로 가정
  let pos = home, total = 0; const legs = [], monthly = {};
  withCoord.forEach(g => {
    const d = haversine(pos, g.ll);
    if (d > 1) { legs.push({ from: pos, to: g.ll, km: d, date: g.date }); total += d; monthly[g.date.slice(0, 7)] = (monthly[g.date.slice(0, 7)] || 0) + d; }
    pos = g.ll;
  });
  const away = withCoord.filter(g => !g.home);
  const byVenue = {};
  away.forEach(g => {
    const k = g.venue; const b = byVenue[k] || (byVenue[k] = { venue: k, v: g.v, ll: g.ll, n: 0, w: 0, l: 0, d: 0, km: haversine(home, g.ll) });
    b.n++; if (g.result === "W") b.w++; else if (g.result === "L") b.l++; else if (g.result === "D") b.d++;
  });
  return { withCoord, away, legs, total, monthly, byVenue: Object.values(byVenue).sort((a, b) => b.km - a.km) };
}
async function renderTravel(el, team) {
  el.innerHTML = loadingBox("시즌 일정을 분석하는 중...");
  const S = await getJSON("data/season.json");
  if (!S || !S.teams || !S.teams[team.name] || !S.teams[team.name].length) { el.innerHTML = emptyBox(PREP_MSG); return; }
  const home = [team.lat, team.lon];
  const A = analyzeTravel(S.teams[team.name], S.venues, home);
  const finals = A.withCoord.filter(g => g.result);
  const rec = (list) => { const w = list.filter(g => g.result === "W").length, l = list.filter(g => g.result === "L").length; return { w, l, pct: (w + l) ? w / (w + l) : 0 }; };
  const homeRec = rec(finals.filter(g => g.home)), awayRec = rec(finals.filter(g => !g.home));
  const bands = [[0, 100, "100km 미만"], [100, 400, "100~400km"], [400, 800, "400~800km"], [800, 99999, "800km 이상"]];
  const bandRec = bands.map(([a, b, label]) => ({ label, ...rec(finals.filter(g => !g.home && haversine(home, g.ll) >= a && haversine(home, g.ll) < b)) }));
  const avgAway = A.away.length ? A.away.reduce((s, g) => s + haversine(home, g.ll), 0) / A.away.length : 0;
  const farthest = A.byVenue[0];
  const months = Object.keys(A.monthly).sort(); const maxM = Math.max(1, ...Object.values(A.monthly));

  // 12개 구단 비교
  const all = allTeams().map(t => ({ t, total: S.teams[t.name] ? analyzeTravel(S.teams[t.name], S.venues, [t.lat, t.lon]).total : 0 }))
    .sort((a, b) => b.total - a.total);
  const maxT = Math.max(1, ...all.map(x => x.total));
  const myRank = all.findIndex(x => x.t.name === team.name) + 1;

  el.innerHTML = `
    <div class="geo-kpis">
      <div><b>${km(A.total)}</b><span>시즌 추정 이동거리</span></div>
      <div><b>${myRank}위</b><span>12개 구단 중 이동거리</span></div>
      <div><b>${A.away.length}</b><span>원정 경기</span></div>
      <div><b>${km(avgAway)}</b><span>평균 원정 거리</span></div>
      <div><b>${farthest ? km(farthest.km) : "-"}</b><span>최장 원정 ${farthest ? `(${esc(farthest.v.ko || farthest.venue)})` : ""}</span></div>
      <div><b>${A.legs.length}</b><span>이동 횟수</span></div>
    </div>
    <div class="stage-tabs"><button class="stage-chip ${!TV.route ? "active" : ""}" data-r="0">홈→원정 구장</button>
      <button class="stage-chip ${TV.route ? "active" : ""}" data-r="1">시즌 이동 경로</button></div>
    <div id="tv-map" class="geo-map tall"></div>
    <div class="legend">${TV.route ? '<span>선 굵기: 같은 구간 이동 횟수</span>' : '<span>원 크기: 원정 경기 수 · 선 색: 거리</span><i style="background:#22c55e"></i>~400km<i style="background:#f59e0b"></i>~800km<i style="background:#ef4444"></i>800km+'}<i class="hp">⭐</i>홈구장</div>
    <div class="geo-two">
      <div class="card"><div class="mt-ph">🏠 홈 vs ✈️ 원정 승률</div>
        <div class="bar-row"><span>홈</span><div class="bar"><i style="width:${homeRec.pct * 100}%;background:#22c55e"></i></div><b>${homeRec.w}승 ${homeRec.l}패 (${(homeRec.pct).toFixed(3).replace(/^0/, "")})</b></div>
        <div class="bar-row"><span>원정</span><div class="bar"><i style="width:${awayRec.pct * 100}%;background:#3b82f6"></i></div><b>${awayRec.w}승 ${awayRec.l}패 (${(awayRec.pct).toFixed(3).replace(/^0/, "")})</b></div>
        <div class="mt-ph" style="margin-top:14px">📏 원정 거리대별 승률</div>
        ${bandRec.map(b => `<div class="bar-row"><span>${b.label}</span><div class="bar"><i style="width:${b.pct * 100}%"></i></div><b>${b.w + b.l ? `${b.w}승 ${b.l}패` : "경기 없음"}</b></div>`).join("")}
        <div class="hint" style="margin:8px 0 0">거리가 멀수록 승률이 떨어지는지(원정 피로) 확인해 볼 수 있어요.</div>
      </div>
      <div class="card"><div class="mt-ph">📆 월별 이동거리</div>
        ${months.map(m => `<div class="bar-row"><span>${parseInt(m.slice(5))}월</span><div class="bar"><i style="width:${A.monthly[m] / maxM * 100}%"></i></div><b>${km(A.monthly[m])}</b></div>`).join("")}
      </div>
    </div>
    <div class="card"><div class="mt-ph">🏟️ 원정 구장별 거리 · 성적</div>
      <div class="table-scroll"><table class="stats"><thead><tr><th>구장</th><th>거리</th><th>방향</th><th>경기</th><th>성적</th></tr></thead><tbody>
      ${A.byVenue.map(b => `<tr><td class="pname">${esc(b.v.ko || b.venue)}${b.v.approx ? ' <em class="pf-jp" title="도시 위치로 근사">≈</em>' : ""}</td>
        <td class="num">${km(b.km)}</td><td>${dirName(bearing(home, b.ll))}</td><td class="num">${b.n}</td>
        <td class="num">${b.w}승 ${b.l}패${b.d ? ` ${b.d}무` : ""}</td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="card"><div class="mt-ph">📊 12개 구단 시즌 이동거리</div>
      ${all.map(x => `<div class="bar-row ${x.t.name === team.name ? "mine" : ""}"><span>${esc(x.t.name)}</span>
        <div class="bar"><i style="width:${x.total / maxT * 100}%;background:${readable(x.t.color)}"></i></div><b>${km(x.total)}</b></div>`).join("")}
    </div>
    <p class="hint">거리는 구장 좌표 사이의 대권거리(지구 반경 6,371km)이며 실제 이동 수단·경로와는 다릅니다. 시즌 이동거리는 시즌 시작 시 홈구장에서 출발해 경기 구장이 바뀔 때마다 직접 이동했다고 가정한 추정치예요. 시범경기(오픈전)는 빼고, 정규시즌${A.withCoord.some(g => g.kind === "cs" || g.kind === "japan_series") ? `과 포스트시즌 ${A.withCoord.filter(g => g.kind === "cs" || g.kind === "japan_series").length}경기` : ""}를 포함합니다. ≈ 표시는 지방 구장을 도시 위치로 근사한 경우입니다. (시즌 일정 갱신 ${esc(S.updated_at || "")})</p>`;

  const map = makeMap("tv-map", home, 5);
  if (!map) { mapFallback(el.querySelector("#tv-map")); }
  else {
    const bounds = [home];
    if (!TV.route) {
      A.byVenue.forEach(b => {
        const c = b.km < 400 ? "#22c55e" : b.km < 800 ? "#f59e0b" : "#ef4444";
        L.polyline(greatCircle(home, b.ll), { color: c, weight: 1.5 + Math.min(b.n, 12) * .35, opacity: .85 }).addTo(map);
        L.circleMarker(b.ll, { radius: 4 + Math.sqrt(b.n) * 2.2, color: "#fff", weight: 1.2, fillColor: c, fillOpacity: .9 })
          .addTo(map).bindTooltip(`<b>${esc(b.v.ko || b.venue)}</b><br>${km(b.km)} · ${dirName(bearing(home, b.ll))} · 원정 ${b.n}경기<br>${b.w}승 ${b.l}패`);
        bounds.push(b.ll);
      });
    } else {
      const seg = {};
      A.legs.forEach(l => { const k = [l.from, l.to].map(p => p.map(x => x.toFixed(3)).join(",")).sort().join("|"); (seg[k] = seg[k] || { ...l, n: 0 }).n++; });
      Object.values(seg).forEach(s => {
        L.polyline(greatCircle(s.from, s.to, 24), { color: readable(team.color), weight: 1 + Math.min(s.n, 10) * .6, opacity: .65 })
          .addTo(map).bindTooltip(`${km(s.km)} · ${s.n}회 이동`);
        bounds.push(s.to);
      });
    }
    L.marker(home, { icon: L.divIcon({ className: "home-pin", html: "⭐", iconSize: [22, 22] }) }).addTo(map).bindTooltip(`홈 · ${esc(team.stadium)}`);
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [24, 24] });
  }
  el.querySelectorAll("[data-r]").forEach(b => b.addEventListener("click", () => { TV.route = b.dataset.r === "1"; renderTravel(el, team); }));
}

/* ============================================================
   4) 구장 날씨 (Open-Meteo, 키 불필요)
   ============================================================ */
const WMO = {
  0: ["☀️", "맑음"], 1: ["🌤️", "대체로 맑음"], 2: ["⛅", "구름 조금"], 3: ["☁️", "흐림"], 45: ["🌫️", "안개"], 48: ["🌫️", "서리 안개"],
  51: ["🌦️", "약한 이슬비"], 53: ["🌦️", "이슬비"], 55: ["🌧️", "강한 이슬비"], 56: ["🌧️", "어는 이슬비"], 57: ["🌧️", "어는 이슬비"],
  61: ["🌧️", "약한 비"], 63: ["🌧️", "비"], 65: ["🌧️", "강한 비"], 66: ["🌧️", "어는 비"], 67: ["🌧️", "어는 비"],
  71: ["🌨️", "약한 눈"], 73: ["🌨️", "눈"], 75: ["❄️", "강한 눈"], 77: ["🌨️", "싸락눈"],
  80: ["🌦️", "소나기"], 81: ["🌧️", "소나기"], 82: ["⛈️", "강한 소나기"], 85: ["🌨️", "눈 소나기"], 86: ["🌨️", "강한 눈 소나기"],
  95: ["⛈️", "뇌우"], 96: ["⛈️", "우박 동반 뇌우"], 99: ["⛈️", "강한 우박 뇌우"],
};
const wmo = (c) => WMO[c] || ["❔", "정보 없음"];
const ROOF_KO = { dome: "🏟️ 돔 구장 · 날씨 영향 거의 없음", retractable: "🏟️ 개폐식 지붕 · 우천 시 닫음", open: "🌳 야외 구장 · 비 오면 취소될 수 있음" };
const windDir = (d) => DIR16[Math.round(d / 22.5) % 16];

async function fetchWeather(points) {
  const lat = points.map(p => p.lat.toFixed(4)).join(","), lon = points.map(p => p.lon.toFixed(4)).join(",");
  const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}`
    + "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m"
    + "&hourly=temperature_2m,precipitation_probability,weather_code,wind_speed_10m"
    + "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    + "&timezone=Asia%2FTokyo&forecast_days=4&wind_speed_unit=ms";
  const r = await fetch(url);
  if (!r.ok) throw new Error("weather " + r.status);
  const j = await r.json();
  return Array.isArray(j) ? j : [j];
}

async function renderWeather(el, team) {
  el.innerHTML = loadingBox("구장 날씨를 불러오는 중...");
  const S = await getJSON("data/season.json");
  const venues = { ...((S && S.venues) || {}) };
  const homeKey = Object.keys(venues).find(k => venues[k].lat && haversine([venues[k].lat, venues[k].lon], [team.lat, team.lon]) < 1.5);
  const homeRoof = homeKey ? venues[homeKey].roof : "open";
  const today = todayStr();

  // 다음 경기: 시즌 일정 → 없으면 30일 일정
  let next = null;
  const sg = S && S.teams && S.teams[team.name];
  if (sg) {
    const g = sg.find(x => x.date >= today && x.state !== "final" && x.state !== "cancel");
    if (g && venues[g.venue] && venues[g.venue].lat != null) next = { ...g, vinfo: venues[g.venue] };
  }
  // 경기 시작 시각은 30일 일정에서 찾기
  const sched = ((DATA.schedule && DATA.schedule.days) || []).flatMap(d => d.games.map(x => ({ ...x, date: d.date })));
  const startOf = (date) => { const g = sched.find(x => x.date === date && (x.home === team.name || x.away === team.name)); return g && g.start; };

  const spots = [{ key: "home", title: `🏠 홈구장 · ${team.stadium}`, lat: team.lat, lon: team.lon, roof: homeRoof }];
  if (next && haversine([next.vinfo.lat, next.vinfo.lon], [team.lat, team.lon]) > 1.5)
    spots.push({ key: "next", title: `✈️ 다음 경기 구장 · ${next.vinfo.ko}`, lat: next.vinfo.lat, lon: next.vinfo.lon, roof: next.vinfo.roof || "open" });
  const twelve = allTeams().map(t => {
    const k = Object.keys(venues).find(v => venues[v].lat && haversine([venues[v].lat, venues[v].lon], [t.lat, t.lon]) < 1.5);
    return { team: t, lat: t.lat, lon: t.lon, roof: k ? venues[k].roof : "open" };
  });

  let W;
  try { W = await fetchWeather([...spots, ...twelve]); }
  catch (e) { el.innerHTML = emptyBox("날씨 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."); return; }

  const card = (s, w) => {
    const c = w.current, [ic, desc] = wmo(c.weather_code);
    const isNext = s.key === "next" || (s.key === "home" && next && haversine([next.vinfo.lat, next.vinfo.lon], [team.lat, team.lon]) <= 1.5);
    let gameLine = "";
    if (isNext && next) {
      const st = startOf(next.date) || "18:00";
      const idx = w.hourly.time.indexOf(`${next.date}T${st.slice(0, 2).padStart(2, "0")}:00`);
      if (idx >= 0) {
        const pp = w.hourly.precipitation_probability[idx], [hi, hd] = wmo(w.hourly.weather_code[idx]);
        const risk = s.roof === "open" && pp >= 50;
        gameLine = `<div class="wx-game ${risk ? "risk" : ""}">⚾ ${esc(next.date.slice(5).replace("-", "/"))} ${esc(st)} 경기 시각 예보: ${hi} ${esc(hd)} · ${Math.round(w.hourly.temperature_2m[idx])}° · 강수확률 ${pp}%
          ${risk ? "<br>☔ 야외 구장이라 우천 취소 가능성이 있어요." : ""}</div>`;
      } else gameLine = `<div class="wx-game">⚾ 다음 경기(${esc(next.date)})는 예보 범위(4일) 밖이에요.</div>`;
    }
    const now = new Date(c.time); const hIdx = Math.max(0, w.hourly.time.findIndex(t => t >= c.time.slice(0, 13)));
    const hours = w.hourly.time.slice(hIdx, hIdx + 12).map((t, i) => ({ t: t.slice(11, 16), tmp: w.hourly.temperature_2m[hIdx + i], pp: w.hourly.precipitation_probability[hIdx + i], wc: w.hourly.weather_code[hIdx + i] }));
    return `<div class="card wx-card">
      <div class="mt-ph">${esc(s.title)}</div><div class="wx-roof">${ROOF_KO[s.roof] || ROOF_KO.open}</div>
      <div class="wx-now"><span class="wx-ic">${ic}</span><div><div class="wx-temp">${Math.round(c.temperature_2m)}°</div><div class="wx-desc">${esc(desc)} · 체감 ${Math.round(c.apparent_temperature)}°</div></div>
        <div class="wx-meta">💧 습도 ${c.relative_humidity_2m}%<br>🌬️ ${windDir(c.wind_direction_10m)}풍 ${c.wind_speed_10m.toFixed(1)}m/s<br>☔ 강수 ${c.precipitation}mm</div></div>
      ${gameLine}
      <div class="wx-hours">${hours.map(h => `<div><span>${h.t}</span><b>${wmo(h.wc)[0]}</b><span>${Math.round(h.tmp)}°</span><em>${h.pp}%</em></div>`).join("")}</div>
      <div class="wx-days">${w.daily.time.map((d, i) => `<div><span>${i === 0 ? "오늘" : ["일", "월", "화", "수", "목", "금", "토"][new Date(d + "T00:00:00+09:00").getDay()]}</span><b>${wmo(w.daily.weather_code[i])[0]}</b>
        <span>${Math.round(w.daily.temperature_2m_max[i])}° / ${Math.round(w.daily.temperature_2m_min[i])}°</span><em>☔ ${w.daily.precipitation_probability_max[i]}%</em></div>`).join("")}</div>
    </div>`;
  };

  const rows = twelve.map((s, i) => ({ s, w: W[spots.length + i] }));
  el.innerHTML = `<div class="wx-grid">${spots.map((s, i) => card(s, W[i])).join("")}</div>
    <div class="card"><div class="mt-ph">🗾 12개 구단 홈구장 현재 날씨</div>
      <div id="wx-map" class="geo-map"></div>
      <div class="table-scroll"><table class="stats"><thead><tr><th>구장</th><th>날씨</th><th>기온</th><th>오늘 강수확률</th><th>바람</th></tr></thead><tbody>
      ${rows.map(({ s, w }) => `<tr class="${s.team.name === team.name ? "mine-row" : ""}"><td class="pname">${esc(s.team.stadium)} <em class="pf-jp">${s.roof === "dome" ? "돔" : s.roof === "retractable" ? "개폐식" : "야외"}</em></td>
        <td>${wmo(w.current.weather_code)[0]} ${esc(wmo(w.current.weather_code)[1])}</td><td class="num">${Math.round(w.current.temperature_2m)}°</td>
        <td class="num">${w.daily.precipitation_probability_max[0]}%</td><td>${windDir(w.current.wind_direction_10m)} ${w.current.wind_speed_10m.toFixed(1)}m/s</td></tr>`).join("")}
      </tbody></table></div></div>
    <p class="hint">날씨: <a href="https://open-meteo.com/" target="_blank" rel="noopener" style="color:var(--accent-2)">Open-Meteo.com</a> (CC BY 4.0) · 구장 좌표 기준 예보이며 30분~1시간마다 바뀌어요.</p>`;

  const map = makeMap("wx-map", [36.2, 137.8], 4.5);
  if (map) rows.forEach(({ s, w }) => {
    const [ic] = wmo(w.current.weather_code);
    L.marker([s.lat, s.lon], { icon: L.divIcon({ className: "wx-pin", html: `<span>${ic}</span><b>${Math.round(w.current.temperature_2m)}°</b>`, iconSize: [54, 24] }) })
      .addTo(map).bindTooltip(`${esc(s.team.stadium)} · ${esc(wmo(w.current.weather_code)[1])} · 강수확률 ${w.daily.precipitation_probability_max[0]}%`);
  });
}

window.MT_GEO = { profiles: renderProfiles, origin: renderOrigin, travel: renderTravel, weather: renderWeather };
