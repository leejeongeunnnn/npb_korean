/* NPB 정적 대시보드 - data/*.json 을 읽어 7개 탭을 렌더링 */

const DATA = {};
const FILES = ["meta", "standings", "schedule", "postseason", "batters", "pitchers", "news", "news_teams", "teams"];

/* ---------- 마이팀 (보는 사람 브라우저에 저장) ---------- */
const MYTEAM_KEY = "npb_myteam";
let MY_TEAM = null;
function loadMyTeam() {
  try { MY_TEAM = localStorage.getItem(MYTEAM_KEY) || null; } catch (e) { MY_TEAM = null; }
}
function saveMyTeam(name) {
  MY_TEAM = name || null;
  try { name ? localStorage.setItem(MYTEAM_KEY, name) : localStorage.removeItem(MYTEAM_KEY); } catch (e) { /* 저장 불가 환경이면 이번 방문 동안만 유지 */ }
}
const isMine = (name) => !!MY_TEAM && name === MY_TEAM;
/* 어두운 구단색(오릭스 등)은 어두운 배경에서 안 보이므로 밝게 보정 */
function readable(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return "#94a3b8";
  const n = parseInt(m[1], 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  if (lum >= 0.35) return hex;
  const mix = (c) => Math.round(c + (255 - c) * 0.55);
  return `#${[mix(r), mix(g), mix(b)].map(x => x.toString(16).padStart(2, "0")).join("")}`;
}

/* ---------- 실시간 점수 (live 브랜치의 live.json) ----------
   GitHub Pages 주소(아이디.github.io/저장소)에서 저장소를 알아내 GitHub API로 읽는다.
   API 한도(IP당 시간당 60회)를 넘으면 raw.githubusercontent.com(약 5분 캐시)으로 대체. */
const FALLBACK_REPO = "leejeongeunnnn/npb_korean";
const LIVE_POLL_MS = 75 * 1000;
function repoSlug() {
  const h = location.hostname;
  if (h.endsWith(".github.io")) {
    const owner = h.split(".")[0];
    const repo = location.pathname.split("/").filter(Boolean)[0];
    if (repo) return `${owner}/${repo}`;
  }
  return FALLBACK_REPO;
}
async function fetchLive() {
  const slug = repoSlug();
  const tries = [
    () => fetch(`https://api.github.com/repos/${slug}/contents/live.json?ref=live`,
                { cache: "no-store", headers: { Accept: "application/vnd.github.raw+json" } }),
    () => fetch(`https://raw.githubusercontent.com/${slug}/live/live.json?t=${Date.now()}`, { cache: "no-store" }),
  ];
  for (const t of tries) {
    try {
      const r = await t();
      if (r.ok) return await r.json();
    } catch (e) { /* 다음 방법 시도 */ }
  }
  return null;
}
/* 일본/한국 기준 오늘 날짜 (YYYY-MM-DD) */
function todayStr() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}
/* live.json 이 오늘 것이면 그 경기 목록 반환 */
function liveGamesToday() {
  const L = DATA.live;
  return (L && L.date === todayStr() && Array.isArray(L.games)) ? L.games : null;
}

async function loadAll() {
  await Promise.all(FILES.map(async (f) => {
    try {
      const res = await fetch(`data/${f}.json?t=${Date.now()}`, { cache: "no-store" });
      DATA[f] = res.ok ? await res.json() : null;
    } catch (e) {
      DATA[f] = null;
    }
  }));
}

/* ---------- 유틸 ---------- */
const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstChild; };
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const emptyBox = (msg) => `<div class="empty">${esc(msg)}</div>`;
const SEED_MSG = "아직 자동 수집 전입니다. GitHub Actions가 처음 실행되면 데이터가 표시됩니다.";

/* 팀 색상 조회 (teams.json 기반) */
let TEAM_COLOR = {};
function buildTeamColorMap() {
  const t = DATA.teams;
  if (!t) return;
  [...(t.central || []), ...(t.pacific || [])].forEach(tm => { TEAM_COLOR[tm.name] = tm.color; });
}
const colorOf = (name) => TEAM_COLOR[name] || "#64748b";

/* ---------- 1. 경기 일정 ---------- */
function gameCard(g) {
  const live = g.state === "live" || (g.status && g.status.includes("진행 중"));
  const showScore = g.state === "final" || live || (g.state === undefined && g.score_home !== "" && g.score_away !== "");
  let hw = "", aw = "";
  if (g.state === "final") {
    const sh = parseInt(g.score_home), sa = parseInt(g.score_away);
    if (sh > sa) hw = "winner"; else if (sa > sh) aw = "winner";
  }
  const sc = (v) => showScore && v !== "" ? esc(v) : "-";
  const mine = isMine(g.home) || isMine(g.away);
  return `<div class="game ${live ? "is-live" : ""} ${mine ? "is-mine" : ""}">
    ${(g.series || live || mine) ? `<div class="series">${mine ? '<span class="mine-star">⭐</span> ' : ""}${live ? '<span class="live-pill">LIVE</span> ' : ""}${esc(g.series || "")}</div>` : ""}
    <div class="game-row">
      <span class="game-team"><span class="dot" style="background:${colorOf(g.away)}"></span>${esc(g.away)}</span>
      <span class="game-score ${aw}">${sc(g.score_away)}</span>
    </div>
    <div class="game-row">
      <span class="game-team"><span class="dot" style="background:${colorOf(g.home)}"></span>${esc(g.home)} <span class="home-tag">홈</span></span>
      <span class="game-score ${hw}">${sc(g.score_home)}</span>
    </div>
    <div class="game-meta">
      <span>${esc(g.venue || "")}</span>
      <span class="${live ? "status-live" : ""}">${esc(g.status || "")}</span>
    </div>
  </div>`;
}

function renderSchedule() {
  const p = document.getElementById("panel-schedule");
  const data = DATA.schedule;
  const today = todayStr();
  let html = `<h2 class="section-title">🔥 경기 일정 &amp; 결과 (30일)</h2>`;

  const days = (data && data.days) ? data.days.filter(d => d.games && d.games.length).map(d => ({ ...d })) : [];

  // 오늘 경기는 실시간 데이터가 있으면 그것으로 교체
  const liveGames = liveGamesToday();
  let todayDay = days.find(d => d.date === today);
  if (liveGames && liveGames.length) {
    if (todayDay) todayDay.games = liveGames;
    else {
      const d = new Date(today + "T00:00:00+09:00");
      todayDay = { date: today, display: `${d.getMonth() + 1}월 ${d.getDate()}일`, games: liveGames };
      days.push(todayDay);
    }
  }
  if (!days.length) { p.innerHTML = html + emptyBox(SEED_MSG); return; }

  // 실시간 상태 안내
  const L = DATA.live;
  const anyLive = liveGames && liveGames.some(g => g.state === "live");
  if (liveGames) {
    const t = (L.updated_at || "").slice(11, 16);
    html += `<div class="live-banner ${anyLive ? "on" : ""}">
      ${anyLive ? '<span class="live-dot"></span> 경기 진행 중 · 점수 실시간 반영' : "📡 오늘 경기 실시간 정보"}
      <span class="lb-time">마지막 갱신 ${esc(t)} · 화면은 75초마다 자동 새로고침</span></div>`;
  } else {
    html += `<p class="hint">경기가 있는 시간대에는 점수가 1~2분 간격으로 자동 반영됩니다.</p>`;
  }

  const group = (title, list, cls = "") => {
    if (!list.length) return "";
    let h = `<h3 class="sched-sub ${cls}">${title}</h3>`;
    list.forEach(day => {
      h += `<div class="day-group"><div class="day-head">${esc(day.display)} ${day.date === today ? '<span class="today-badge">오늘</span>' : ""}</div><div class="game-grid">`;
      day.games.forEach(g => h += gameCard(g));
      h += `</div></div>`;
    });
    return h;
  };
  const upcoming = days.filter(d => d.date > today).sort((a, b) => a.date.localeCompare(b.date));
  const past = days.filter(d => d.date < today).sort((a, b) => b.date.localeCompare(a.date));
  html += group("📍 오늘 경기", todayDay && todayDay.games.length ? [todayDay] : []);
  html += group("🗓️ 예정 경기", upcoming);
  html += group("✅ 지난 경기 결과", past);
  p.innerHTML = html;
}

/* ---------- 2. 순위 ---------- */
function renderStandings() {
  const p = document.getElementById("panel-standings");
  const s = DATA.standings;
  let html = `<h2 class="section-title">🏆 리그 순위표</h2>`;
  const hasData = s && ((s.central && s.central.length) || (s.pacific && s.pacific.length));
  if (!hasData) { p.innerHTML = html + emptyBox(SEED_MSG); return; }

  const table = (teams) => {
    let t = `<table class="rank"><thead><tr><th>순위</th><th>팀</th><th>경기</th><th>승</th><th>패</th><th>무</th><th>승률</th><th>게임차</th></tr></thead><tbody>`;
    teams.forEach(r => {
      t += `<tr class="${isMine(r.team) ? "mine-row" : ""}">
        <td>${esc(r.rank)}</td>
        <td class="team"><span class="dot" style="display:inline-block;background:${esc(r.color)};margin-right:6px"></span>${esc(r.team)}${isMine(r.team) ? " ⭐" : ""}</td>
        <td class="num">${esc(r.games)}</td><td class="num">${esc(r.win)}</td><td class="num">${esc(r.loss)}</td>
        <td class="num">${esc(r.draw)}</td><td class="num">${esc(r.pct)}</td><td class="num">${esc(r.gb)}</td>
      </tr>`;
    });
    return t + `</tbody></table>`;
  };

  html += `<div class="standings-wrap">
    <div class="card league-card"><h3>🔵 센트럴 리그</h3>${(s.central && s.central.length) ? table(s.central) : emptyBox("데이터 없음")}</div>
    <div class="card league-card"><h3>🔴 퍼시픽 리그</h3>${(s.pacific && s.pacific.length) ? table(s.pacific) : emptyBox("데이터 없음")}</div>
  </div>`;
  p.innerHTML = html;
}

/* ---------- 3. 포스트시즌 ---------- */
function renderPostseason() {
  const p = document.getElementById("panel-postseason");
  const ps = DATA.postseason;
  let html = `<h2 class="section-title">🍁 포스트시즌 (클라이맥스 시리즈 &amp; 일본시리즈)</h2>`;
  html += `<p class="hint">2026 시즌 포스트시즌 전체 일정입니다. 진행 중인 경기 스코어는 자동 갱신됩니다.</p>`;

  const L = DATA.live;
  const live = (L && L.date === todayStr() && L.postseason && L.postseason.length) ? L.postseason
             : (ps && ps.live) ? ps.live : [];
  if (live.length) {
    html += `<div class="card"><h3 style="margin-bottom:10px;font-size:.92rem">🔴 실시간 / 최근 경기</h3>`;
    live.forEach(g => {
      html += `<div class="ps-game card" style="margin-bottom:8px">
        <div class="ps-badge">${esc(g.stage)}</div>
        <div><div class="ps-match">${esc(g.away)} ${esc(g.score_away || "")} vs ${esc(g.score_home || "")} ${esc(g.home)}</div>
        <div class="ps-info">${esc(g.venue)} · ${esc(g.status)}</div></div>
      </div>`;
    });
    html += `</div>`;
  }

  const master = (ps && ps.master) ? ps.master : [];
  if (!master.length) { p.innerHTML = html + emptyBox("포스트시즌 일정 데이터가 없습니다."); return; }

  const stages = [...new Set(master.map(m => m.stage))];
  html += `<div class="stage-tabs" id="ps-stage-tabs">`;
  stages.forEach((st, i) => html += `<button class="stage-chip ${i === 0 ? "active" : ""}" data-stage="${esc(st)}">${esc(st)}</button>`);
  html += `</div><div id="ps-list"></div>`;
  p.innerHTML = html;

  const listEl = p.querySelector("#ps-list");
  const draw = (stage) => {
    let h = "";
    master.filter(m => m.stage === stage).forEach(m => {
      h += `<div class="card ps-game">
        <div class="ps-badge">${esc(m.league.replace(" 리그", ""))}<br>${esc(m.game_num)}</div>
        <div>
          <div class="ps-match">${esc(m.away)} <span style="color:var(--muted)">@</span> ${esc(m.home)}</div>
          <div class="ps-info">📅 ${esc(m.date_display)} ${esc(m.time)} · 🏟️ ${esc(m.venue)}</div>
          <span class="ps-rules">📋 ${esc(m.rules)}</span>
        </div>
      </div>`;
    });
    listEl.innerHTML = h;
  };
  draw(stages[0]);
  p.querySelectorAll(".stage-chip").forEach(c => c.addEventListener("click", () => {
    p.querySelectorAll(".stage-chip").forEach(x => x.classList.remove("active"));
    c.classList.add("active");
    draw(c.dataset.stage);
  }));
}

/* ---------- 4. 선수 성적 (타자 / 투수) ---------- */
const PLAYER_MODES = {
  bat: {
    label: "🏏 타자", file: "batters", title: "규정타석 타자 성적",
    sort: { key: "avg", dir: -1 },
    cols: [
      { k: "avg", label: "타율", f: "rate" }, { k: "hr", label: "홈런" },
      { k: "obp", label: "출루율", f: "rate" }, { k: "slg", label: "장타율", f: "rate" }, { k: "sb", label: "도루" },
    ],
  },
  pit: {
    label: "⚾ 투수", file: "pitchers", title: "규정투구회 투수 성적",
    sort: { key: "era", dir: 1 },
    cols: [
      { k: "era", label: "평균자책", f: "f2", asc: 1 }, { k: "g", label: "경기" }, { k: "w", label: "승" }, { k: "l", label: "패" },
      { k: "sv", label: "세이브" }, { k: "hld", label: "홀드" }, { k: "ip", label: "이닝", show: "ip_disp" },
      { k: "so", label: "탈삼진" }, { k: "whip", label: "WHIP", f: "f2", asc: 1 }, { k: "pct", label: "승률", f: "rate" },
    ],
  },
};
let playerMode = "bat";
const playerSorts = { bat: { ...PLAYER_MODES.bat.sort }, pit: { ...PLAYER_MODES.pit.sort } };

function renderPlayers() {
  const p = document.getElementById("panel-players");
  const M = PLAYER_MODES[playerMode];
  const rowsAll = DATA[M.file] || [];
  let html = `<h2 class="section-title">🏃 선수 성적</h2>
    <div class="stage-tabs">${Object.entries(PLAYER_MODES).map(([k, m]) =>
      `<button class="stage-chip ${k === playerMode ? "active" : ""}" data-mode="${k}">${m.label}</button>`).join("")}</div>
    <p class="hint">NPB 공식(npb.jp) ${M.title}입니다. 구단으로 거르거나 표 머리글을 눌러 정렬할 수 있어요.${playerMode === "pit" ? " 평균자책점·WHIP는 낮을수록 좋습니다." : ""}</p>`;

  if (!rowsAll.length) {
    p.innerHTML = html + emptyBox(SEED_MSG);
  } else {
    const teams = [...new Set(rowsAll.map(b => b.team))].sort();
    html += `<div class="controls"><select id="pteam"><option value="">전체 구단</option>${MY_TEAM && teams.includes(MY_TEAM) ? `<option value="${esc(MY_TEAM)}">⭐ 마이팀만 보기</option>` : ""}${teams.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select></div>
      <div class="table-scroll"><div id="ptable"></div></div>`;
    p.innerHTML = html;
  }
  p.querySelectorAll("[data-mode]").forEach(b => b.addEventListener("click", () => { playerMode = b.dataset.mode; renderPlayers(); }));
  if (!rowsAll.length) return;

  const fmt = (c, r) => {
    const v = r[c.show || c.k];
    if (c.f === "rate") return Number(v).toFixed(3).replace(/^0/, "");
    if (c.f === "f2") return Number(v).toFixed(2);
    return esc(v);
  };
  const draw = () => {
    const S = playerSorts[playerMode];
    const filter = p.querySelector("#pteam").value;
    const rows = rowsAll.filter(b => !filter || b.team === filter).sort((a, b) => {
      const va = a[S.key], vb = b[S.key];
      return typeof va === "string" ? S.dir * va.localeCompare(vb) : S.dir * (va - vb);
    });
    const head = [{ k: "name", label: "선수" }, { k: "team", label: "구단" }, ...M.cols];
    let t = `<table class="stats"><thead><tr><th>#</th>`;
    head.forEach(c => t += `<th data-k="${c.k}">${esc(c.label)}${S.key === c.k ? (S.dir < 0 ? " ▼" : " ▲") : ""}</th>`);
    t += `</tr></thead><tbody>`;
    rows.forEach((r, i) => {
      t += `<tr class="${isMine(r.team) ? "mine-row" : ""}"><td class="num rank-no">${i + 1}</td><td class="pname">${esc(r.name)}</td>
        <td class="pteam"><span class="dot" style="display:inline-block;background:${esc(r.color)};margin-right:5px"></span>${esc(r.team)}</td>
        ${M.cols.map(c => `<td class="num">${fmt(c, r)}</td>`).join("")}</tr>`;
    });
    p.querySelector("#ptable").innerHTML = t + `</tbody></table>`;
    p.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
      const k = th.dataset.k, col = head.find(c => c.k === k);
      if (S.key === k) S.dir *= -1;
      else { S.key = k; S.dir = (k === "name" || k === "team" || (col && col.asc)) ? 1 : -1; }
      draw();
    }));
  };
  p.querySelector("#pteam").addEventListener("change", draw);
  draw();
}

/* ---------- 5. 구장 ---------- */
let mapInited = false;
function renderStadiums() {
  const p = document.getElementById("panel-stadiums");
  const t = DATA.teams;
  if (p.dataset.done) return;
  let html = `<h2 class="section-title">🏟️ 구단별 홈 구장 안내</h2>`;
  html += `<p class="hint">지도의 마커를 누르면 구장 정보가 표시됩니다.</p><div id="map"></div><div class="stadium-grid">`;
  const all = [...((t && t.central) || []), ...((t && t.pacific) || [])];
  all.forEach(tm => {
    html += `<div class="card stadium-card">
      <div class="sc-name">🏟️ ${esc(tm.stadium)}</div>
      <div class="sc-team" style="color:${esc(tm.color)}">${esc(tm.name)}</div>
      <div class="sc-row">📍 ${esc(tm.address)}</div>
      <div class="sc-row">🪑 ${esc(tm.capacity)}</div>
      <div style="margin-top:8px"><a href="${esc(tm.website)}" target="_blank" rel="noopener">공식 홈페이지 →</a>
      &nbsp; <a href="https://www.google.com/maps/search/?api=1&query=${tm.lat},${tm.lon}" target="_blank" rel="noopener">지도 보기 →</a></div>
    </div>`;
  });
  html += `</div>`;
  p.innerHTML = html;
  p.dataset.done = "1";

  if (typeof L !== "undefined" && all.length) {
    const map = L.map("map").setView([36.2, 138.3], 5);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap &copy; CARTO", maxZoom: 18,
    }).addTo(map);
    all.forEach(tm => {
      L.circleMarker([tm.lat, tm.lon], { radius: 9, color: "#fff", weight: 2, fillColor: tm.color, fillOpacity: .95 })
        .addTo(map)
        .bindPopup(`<b>${esc(tm.stadium)}</b><br>${esc(tm.name)}<br>${esc(tm.address)}`);
    });
    setTimeout(() => map.invalidateSize(), 200);
  }
}

/* ---------- 6. 팀 소개 ---------- */
function renderTeams() {
  const p = document.getElementById("panel-teams");
  const t = DATA.teams;
  let html = `<h2 class="section-title">📣 12개 구단 소개</h2>`;
  if (!t) { p.innerHTML = html + emptyBox("팀 데이터를 불러오지 못했습니다."); return; }
  const block = (title, list) => {
    let h = `<div class="team-league-title">${title}</div><div class="team-grid">`;
    list.forEach(tm => {
      h += `<div class="card team-card" style="border-top-color:${esc(tm.color)}">
        <div class="tc-head"><span class="tc-name">${esc(tm.name)}</span><span class="tc-year">창단 ${esc(tm.founded)}</span></div>
        <div class="tc-jp">${esc(tm.name_jp)}</div>
        <div class="tc-intro">${esc(tm.intro)}</div>
        <div class="tc-foot">🏟️ ${esc(tm.stadium)} · 🪑 ${esc(tm.capacity)}</div>
      </div>`;
    });
    return h + `</div>`;
  };
  html += block("🔵 센트럴 리그", t.central || []);
  html += block("🔴 퍼시픽 리그", t.pacific || []);
  p.innerHTML = html;
}

/* ---------- 7. 뉴스 ---------- */
function renderNews() {
  const p = document.getElementById("panel-news");
  const news = DATA.news || [];
  let html = `<h2 class="section-title">📰 오늘의 일본 프로야구 기사</h2>`;
  html += `<p class="hint">Google 뉴스(일본)에서 수집해 한국어로 번역·요약한 최신 야구 기사입니다. 제목을 누르면 원문으로 이동합니다.</p>`;
  if (!news.length) { p.innerHTML = html + emptyBox(SEED_MSG); return; }

  // 오늘의 기사 요약 (분야별 · 구단별 건수)
  const count = (key) => news.reduce((m, n) => (m[n[key]] = (m[n[key]] || 0) + 1, m), {});
  const byCat = Object.entries(count("category")).sort((a, b) => b[1] - a[1]);
  const byTeam = Object.entries(count("team")).filter(([t]) => t !== "NPB 종합").sort((a, b) => b[1] - a[1]).slice(0, 5);
  const todayN = news.filter(n => n.is_today).length;
  html += `<div class="card news-digest">
    <div class="nd-title">📝 오늘의 기사 요약</div>
    <div class="nd-line">최근 기사 <b>${news.length}건</b> 중 오늘 나온 기사 <b>${todayN}건</b></div>
    <div class="nd-line">분야별: ${byCat.map(([c, n]) => `${esc(c)} <b>${n}</b>`).join(" · ")}</div>
    ${byTeam.length ? `<div class="nd-line">많이 언급된 구단: ${byTeam.map(([t, n]) => `<span style="color:${colorOf(t)};font-weight:700">${esc(t)}</span> ${n}건`).join(" · ")}</div>` : ""}
  </div>`;

  const cats = byCat.map(([c]) => c);
  html += `<div class="controls"><select id="ncat"><option value="">전체 분야</option>${MY_TEAM ? `<option value="__mine">⭐ 마이팀 기사만</option>` : ""}${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select></div><div id="nlist"></div>`;
  p.innerHTML = html;

  const draw = () => {
    const f = p.querySelector("#ncat").value;
    const list = news.filter(n => !f || (f === "__mine" ? isMine(n.team) : n.category === f));
    let h = "";
    list.forEach(n => {
      h += `<div class="card news-card" style="border-left:4px solid ${esc(n.color)}">
        <div class="news-top"><span class="news-cat">${esc(n.category)}</span><span style="color:${esc(n.color)};font-size:.76rem;font-weight:700">${esc(n.team)}</span></div>
        <div class="news-title"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></div>
        ${n.summary ? `<div class="news-summary">${esc(n.summary)}</div>` : ""}
        <div class="news-meta"><span>🕑 ${esc(n.time)}</span><span>📰 ${esc(n.media)}</span></div>
      </div>`;
    });
    p.querySelector("#nlist").innerHTML = h || emptyBox("해당 분야 기사가 없습니다.");
  };
  p.querySelector("#ncat").addEventListener("change", draw);
  draw();
}

/* ---------- 탭 전환 ---------- */
/* ---------- 0. 마이팀 ---------- */
function allTeams() {
  const t = DATA.teams || {};
  return [...(t.central || []).map(x => ({ ...x, league: "센트럴 리그" })),
          ...(t.pacific || []).map(x => ({ ...x, league: "퍼시픽 리그" }))];
}
/* 오늘 경기는 실시간 데이터로 바꾼 전체 경기 목록 (날짜 포함) */
function allGamesWithDate() {
  const today = todayStr(), out = [];
  const days = (DATA.schedule && DATA.schedule.days) || [];
  const liveG = liveGamesToday();
  days.forEach(d => {
    const games = (d.date === today && liveG && liveG.length) ? liveG : d.games;
    games.forEach(g => out.push({ ...g, date: d.date, display: d.display }));
  });
  if (liveG && liveG.length && !days.some(d => d.date === today))
    liveG.forEach(g => out.push({ ...g, date: today, display: "오늘" }));
  return out;
}
const isFinal = (g) => g.state ? g.state === "final" : (g.status === "경기 종료");

function renderTeamPicker(p, current) {
  const block = (league) => allTeams().filter(t => t.league === league).map(t =>
    `<button class="pick-team ${t.name === current ? "active" : ""}" data-team="${esc(t.name)}" style="--tc:${readable(t.color)}">
       <span class="dot" style="background:${readable(t.color)}"></span>${esc(t.name)}</button>`).join("");
  p.innerHTML = `<h2 class="section-title">⭐ 마이팀 설정</h2>
    <p class="hint">응원하는 구단을 고르면 이 탭에 순위·다음 경기·최근 경기 흐름·주요 선수·관련 기사가 모이고, 다른 탭에서도 내 팀이 ⭐로 강조됩니다. 선택은 이 브라우저에 저장돼요.</p>
    <div class="team-league-title">🔵 센트럴 리그</div><div class="pick-grid">${block("센트럴 리그")}</div>
    <div class="team-league-title">🔴 퍼시픽 리그</div><div class="pick-grid">${block("퍼시픽 리그")}</div>
    ${current ? `<div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
       <button class="btn-ghost" id="pick-cancel">← 돌아가기</button>
       <button class="btn-ghost danger" id="pick-clear">마이팀 해제</button></div>` : ""}`;
  p.querySelectorAll(".pick-team").forEach(b => b.addEventListener("click", () => setMyTeam(b.dataset.team)));
  const c = p.querySelector("#pick-cancel"); if (c) c.addEventListener("click", () => renderMyTeam());
  const x = p.querySelector("#pick-clear"); if (x) x.addEventListener("click", () => setMyTeam(null));
}

const MT_SUBS = [["overview", "📋 개요"], ["profiles", "👤 선수 프로필"], ["origin", "🗾 출신지 지도"], ["travel", "✈️ 원정 거리"], ["weather", "🌤️ 구장 날씨"]];
let MT_SUB = "overview";
function renderMyTeam(forcePicker = false) {
  const p = document.getElementById("panel-myteam");
  const team = allTeams().find(t => t.name === MY_TEAM);
  if (forcePicker || !team) { renderTeamPicker(p, team && team.name); return; }

  const color = readable(team.color);
  const leagueKey = team.league === "센트럴 리그" ? "central" : "pacific";
  const st = ((DATA.standings || {})[leagueKey] || []).find(r => r.team === team.name);
  const today = todayStr();
  const games = allGamesWithDate().filter(g => g.home === team.name || g.away === team.name);
  const side = (g) => g.home === team.name
    ? { opp: g.away, my: g.score_home, op: g.score_away, where: "홈" }
    : { opp: g.home, my: g.score_away, op: g.score_home, where: "원정" };

  // 오늘 / 다음 경기
  const todayGames = games.filter(g => g.date === today);
  const nextGame = todayGames.find(g => g.state !== "final" && g.state !== "cancel")
    || games.filter(g => g.date > today && g.state !== "cancel").sort((a, b) => a.date.localeCompare(b.date))[0];
  // 최근 10경기
  const recent = games.filter(g => isFinal(g) && g.date <= today).sort((a, b) => b.date.localeCompare(a.date)).slice(0, 10);
  let w = 0, l = 0, d = 0;
  const chips = recent.map(g => {
    const s = side(g), my = parseInt(s.my), op = parseInt(s.op);
    const r = my > op ? "W" : my < op ? "L" : "D";
    r === "W" ? w++ : r === "L" ? l++ : d++;
    return { r, g, s };
  });

  let html = `<div class="mt-hero" style="--tc:${color}">
    <div class="mt-top">
      <div><div class="mt-league">${esc(team.league)}</div><div class="mt-name">⭐ ${esc(team.name)}</div></div>
      <button class="btn-ghost" id="mt-change">팀 변경</button>
    </div>
    ${st ? `<div class="mt-stats">
      <div><b>${esc(st.rank)}</b><span>순위</span></div>
      <div><b>${esc(st.win)}-${esc(st.loss)}-${esc(st.draw)}</b><span>승-패-무</span></div>
      <div><b>${esc(st.pct)}</b><span>승률</span></div>
      <div><b>${esc(st.gb)}</b><span>1위와 차</span></div>
    </div>` : `<div class="hint" style="margin:8px 0 0">순위 데이터 수집 전입니다.</div>`}
  </div>`;

  // 하위 탭 (개요 / 선수 프로필 / 출신지 지도 / 원정 거리 / 구장 날씨)
  html += `<div class="mt-subnav">${MT_SUBS.map(([k, label]) =>
    `<button class="stage-chip ${k === MT_SUB ? "active" : ""}" data-sub="${k}">${label}</button>`).join("")}</div>`;
  const bindCommon = () => {
    p.querySelector("#mt-change").addEventListener("click", () => renderMyTeam(true));
    p.querySelectorAll("[data-sub]").forEach(b => b.addEventListener("click", () => { MT_SUB = b.dataset.sub; renderMyTeam(); }));
  };
  if (MT_SUB !== "overview" && window.MT_GEO && MT_GEO[MT_SUB]) {
    p.innerHTML = html + `<div id="mt-body"></div>`;
    bindCommon();
    MT_GEO[MT_SUB](p.querySelector("#mt-body"), team);
    return;
  }

  // 다음 경기 카드
  html += `<h3 class="sched-sub">📍 ${nextGame && nextGame.date === today ? "오늘 경기" : "다음 경기"}</h3>`;
  if (nextGame) {
    const s = side(nextGame);
    html += `<div class="card mt-next">
      <div class="mt-next-date">${esc(nextGame.date === today ? "오늘" : nextGame.display)} · ${esc(nextGame.status || "")}${nextGame.series ? ` · ${esc(nextGame.series)}` : ""}</div>
      ${gameCard(nextGame)}
      <div class="hint" style="margin:8px 0 0">vs <b style="color:${readable(colorOf(s.opp))}">${esc(s.opp)}</b> · ${s.where} 경기 · 🏟️ ${esc(nextGame.venue || "")}</div>
    </div>`;
  } else {
    const out = st && parseInt(st.rank) > 3;
    html += emptyBox(out ? "정규시즌이 끝나 남은 경기가 없습니다. (포스트시즌 미진출)" : "가까운 시일 내 예정된 경기가 없습니다.");
  }

  // 최근 10경기
  html += `<h3 class="sched-sub">📈 최근 ${recent.length}경기 흐름 <span class="mt-sub">${w}승 ${l}패${d ? ` ${d}무` : ""}</span></h3>`;
  if (chips.length) {
    html += `<div class="form-row">${chips.slice().reverse().map(c => `<span class="form-chip ${c.r}" title="${esc(c.g.display)} vs ${esc(c.s.opp)} ${esc(c.s.my)}:${esc(c.s.op)}">${c.r === "W" ? "승" : c.r === "L" ? "패" : "무"}</span>`).join("")}</div>
      <div class="card"><table class="rank mt-results"><tbody>${chips.map(c => `<tr>
        <td class="mt-date">${esc(c.g.display)}</td>
        <td><span class="form-chip sm ${c.r}">${c.r === "W" ? "승" : c.r === "L" ? "패" : "무"}</span></td>
        <td class="team">${c.s.where === "홈" ? "vs" : "@"} ${esc(c.s.opp)}</td>
        <td class="num"><b>${esc(c.s.my)}</b> : ${esc(c.s.op)}</td></tr>`).join("")}</tbody></table></div>`;
  } else html += emptyBox("최근 경기 결과가 없습니다.");

  // 예정 경기 (다음 경기 제외 최대 5)
  const upcoming = games.filter(g => g.date >= today && g !== nextGame && g.state !== "final" && g.state !== "cancel")
    .sort((a, b) => a.date.localeCompare(b.date)).slice(0, 5);
  if (upcoming.length) {
    html += `<h3 class="sched-sub">🗓️ 이후 일정</h3><div class="card"><table class="rank mt-results"><tbody>${upcoming.map(g => {
      const s = side(g);
      return `<tr><td class="mt-date">${esc(g.display)}</td><td class="team">${s.where === "홈" ? "vs" : "@"} ${esc(s.opp)}</td><td>${esc(g.status || "")}</td></tr>`;
    }).join("")}</tbody></table></div>`;
  }

  // 포스트시즌
  const token = team.name.split(" ")[0];
  const psAll = ((DATA.postseason || {}).master || []).filter(m => (m.home || "").startsWith(token) || (m.away || "").startsWith(token));
  if (psAll.length) {
    const stages = [...new Set(psAll.map(m => m.stage))];
    const known = new Set(games.map(g => g.display));
    const extra = psAll.filter(m => !known.has(m.date_display));
    const rule = (stage) => (psAll.find(m => m.stage === stage && /전 \d선승제/.test(m.rules)) || psAll.find(m => m.stage === stage)).rules;
    html += `<h3 class="sched-sub">🍁 포스트시즌</h3><div class="card">
      ${stages.map(sg => `<div class="mt-pl"><span>🏟️ <b>${esc(sg)}</b> 진출</span><span class="num">${esc(rule(sg))}</span></div>`).join("")}
      ${extra.length ? `<div class="hint" style="margin:10px 0 4px">아직 대진이 확정되지 않은 경기</div>${extra.map(m =>
        `<div class="mt-pl"><span>${esc(m.date_display)} · ${esc(m.game_num)}</span><span class="num">${esc(m.time)} · ${esc(m.venue)}</span></div>`).join("")}`
        : `<div class="hint" style="margin:10px 0 0">경기별 실제 대진은 위의 '다음 경기'와 '이후 일정'에 나와 있어요.</div>`}
    </div>`;
  } else if (st && parseInt(st.rank) > 3) {
    html += `<h3 class="sched-sub">🍁 포스트시즌</h3>${emptyBox(`리그 ${st.rank}로 이번 시즌 클라이맥스 시리즈에 진출하지 못했습니다.`)}`;
  }

  // 주요 선수
  const bats = (DATA.batters || []).filter(b => b.team === team.name).sort((a, b) => b.avg - a.avg).slice(0, 3);
  const pits = (DATA.pitchers || []).filter(b => b.team === team.name).sort((a, b) => a.era - b.era).slice(0, 3);
  const rate = (v) => Number(v).toFixed(3).replace(/^0/, "");
  html += `<h3 class="sched-sub">🏃 주요 선수 <span class="mt-sub">규정타석·규정투구회 기준</span></h3><div class="mt-players">
    <div class="card"><div class="mt-ph">🏏 타자</div>${bats.length ? bats.map(b => `<div class="mt-pl"><span>${esc(b.name)}</span><span class="num">타율 <b>${rate(b.avg)}</b> · ${esc(b.hr)}홈런</span></div>`).join("") : '<div class="hint" style="margin:0">해당 선수 없음</div>'}</div>
    <div class="card"><div class="mt-ph">⚾ 투수</div>${pits.length ? pits.map(b => `<div class="mt-pl"><span>${esc(b.name)}</span><span class="num">평균자책 <b>${Number(b.era).toFixed(2)}</b> · ${esc(b.w)}승</span></div>`).join("") : '<div class="hint" style="margin:0">해당 선수 없음</div>'}</div>
  </div>`;

  // 기사
  const seen = new Set();
  const news = [...(((DATA.news_teams || {})[team.name]) || []), ...((DATA.news || []).filter(n => n.team === team.name))]
    .filter(n => !seen.has(n.title) && seen.add(n.title)).slice(0, 8);
  html += `<h3 class="sched-sub">📰 ${esc(team.name)} 기사</h3>`;
  html += news.length ? news.map(n => `<div class="card news-card" style="border-left:4px solid ${color}">
      <div class="news-top"><span class="news-cat">${esc(n.category)}</span></div>
      <div class="news-title"><a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a></div>
      <div class="news-meta"><span>🕑 ${esc(n.time)}</span><span>📰 ${esc(n.media)}</span></div></div>`).join("")
    : emptyBox("최근 기사가 아직 수집되지 않았습니다.");

  // 구단 정보
  html += `<h3 class="sched-sub">🏟️ 구단 정보</h3><div class="card">
    <div class="tc-intro" style="font-size:.85rem;line-height:1.65;color:#cdd6e4">${esc(team.intro)}</div>
    <div class="hint" style="margin:10px 0 0">창단 ${esc(team.founded)} · 🏟️ ${esc(team.stadium)} (${esc(team.capacity)}) ·
      <a href="${esc(team.website)}" target="_blank" rel="noopener" style="color:var(--accent-2)">공식 홈페이지 →</a></div></div>`;

  p.innerHTML = html;
  bindCommon();
}

function applyMyTeamTheme() {
  const team = allTeams().find(t => t.name === MY_TEAM);
  document.documentElement.style.setProperty("--mine", team ? readable(team.color) : "var(--accent)");
  const chip = document.getElementById("myteam-chip");
  if (chip) chip.innerHTML = team ? `⭐ ${esc(team.name)}` : "⭐ 마이팀 설정";
}

function setMyTeam(name) {
  saveMyTeam(name);
  applyMyTeamTheme();
  Object.keys(rendered).forEach(k => rendered[k] = false);   // 강조 표시를 위해 모든 탭 다시 그림
  activate("myteam");
}

const RENDERERS = {
  myteam: () => renderMyTeam(),
  schedule: renderSchedule, standings: renderStandings, postseason: renderPostseason,
  players: renderPlayers, stadiums: renderStadiums, teams: renderTeams, news: renderNews,
};
const rendered = {};
function activate(tab) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  document.querySelectorAll(".panel").forEach(pn => pn.classList.toggle("active", pn.id === `panel-${tab}`));
  if (!rendered[tab]) {
    try {
      RENDERERS[tab]();
      rendered[tab] = true;
    } catch (e) {
      // 한 탭에서 오류가 나도 다른 탭·버튼은 계속 동작하도록
      console.error(`[${tab}] 표시 오류`, e);
      const pn = document.getElementById(`panel-${tab}`);
      if (pn) pn.innerHTML = emptyBox("이 화면을 표시하는 중 문제가 생겼습니다. 새로고침해 보세요.");
    }
  }
  if (tab === "stadiums") setTimeout(() => window.dispatchEvent(new Event("resize")), 250);
}

/* ---------- 시작 ---------- */
/* 실시간 점수 주기적 갱신: 화면이 보일 때만, 오늘 경기가 다 끝나면 10분 간격으로 느리게 */
function liveFinishedToday() {
  const g = liveGamesToday();
  return !g || !g.length || g.every(x => x.state === "final" || x.state === "cancel");
}
async function pollLive() {
  if (!document.hidden) {
    const L = await fetchLive();
    if (L && (!DATA.live || L.updated_at !== DATA.live.updated_at)) {
      DATA.live = L;
      rendered.schedule = false; rendered.postseason = false;
      const active = document.querySelector(".tab.active");
      rendered.myteam = false;
      if (active && ["schedule", "postseason", "myteam"].includes(active.dataset.tab)) activate(active.dataset.tab);
    }
  }
  setTimeout(pollLive, liveFinishedToday() ? 10 * 60 * 1000 : LIVE_POLL_MS);
}

(async function init() {
  const [, live] = await Promise.all([loadAll(), fetchLive()]);
  DATA.live = live;
  buildTeamColorMap();
  loadMyTeam();
  if (MY_TEAM && !allTeams().some(t => t.name === MY_TEAM)) saveMyTeam(null);
  applyMyTeamTheme();
  setTimeout(pollLive, liveFinishedToday() ? 10 * 60 * 1000 : LIVE_POLL_MS);

  const meta = DATA.meta;
  document.getElementById("updated-at").textContent =
    meta && meta.updated_at_kst ? `갱신: ${meta.updated_at_kst} (KST)` : "갱신: —";

  document.querySelectorAll(".tab").forEach(t =>
    t.addEventListener("click", () => activate(t.dataset.tab)));

  document.getElementById("myteam-chip").addEventListener("click", () => activate("myteam"));
  activate(MY_TEAM ? "myteam" : "schedule");
  document.getElementById("loader").classList.add("hide");
})();
