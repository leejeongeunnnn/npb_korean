/* NPB 정적 대시보드 - data/*.json 을 읽어 7개 탭을 렌더링 */

const DATA = {};
const FILES = ["meta", "standings", "schedule", "postseason", "batters", "news", "teams"];

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
function renderSchedule() {
  const p = document.getElementById("panel-schedule");
  const data = DATA.schedule;
  let html = `<h2 class="section-title">🔥 최근 30일 경기 일정 &amp; 결과</h2>`;
  html += `<p class="hint">야후 재팬 스포츠 기준으로 수집된 최근 약 30일간의 경기 결과와 예정 경기입니다. 최신순으로 정렬됩니다.</p>`;

  const days = (data && data.days) ? data.days.filter(d => d.games && d.games.length) : [];
  if (!days.length) { p.innerHTML = html + emptyBox(SEED_MSG); return; }

  days.sort((a, b) => b.date.localeCompare(a.date));
  days.forEach(day => {
    html += `<div class="day-group"><div class="day-head">${esc(day.display)} ${day.is_today ? '<span class="today-badge">오늘</span>' : ""}</div><div class="game-grid">`;
    day.games.forEach(g => {
      const live = g.status && g.status.includes("진행 중");
      const done = g.score_home !== "" && g.score_away !== "";
      let hw = "", aw = "";
      if (done) {
        const sh = parseInt(g.score_home), sa = parseInt(g.score_away);
        if (sh > sa) hw = "winner"; else if (sa > sh) aw = "winner";
      }
      html += `<div class="game">
        ${g.series ? `<div class="series">${esc(g.series)}</div>` : ""}
        <div class="game-row">
          <span class="game-team"><span class="dot" style="background:${colorOf(g.away)}"></span>${esc(g.away)}</span>
          <span class="game-score ${aw}">${esc(g.score_away || "-")}</span>
        </div>
        <div class="game-row">
          <span class="game-team"><span class="dot" style="background:${colorOf(g.home)}"></span>${esc(g.home)}</span>
          <span class="game-score ${hw}">${esc(g.score_home || "-")}</span>
        </div>
        <div class="game-meta">
          <span>${esc(g.venue || "")}</span>
          <span class="${live ? "status-live" : ""}">${esc(g.status || "")}</span>
        </div>
      </div>`;
    });
    html += `</div></div>`;
  });
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
      t += `<tr>
        <td>${esc(r.rank)}</td>
        <td class="team"><span class="dot" style="display:inline-block;background:${esc(r.color)};margin-right:6px"></span>${esc(r.team)}</td>
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

  const live = (ps && ps.live) ? ps.live : [];
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

/* ---------- 4. 선수 성적 ---------- */
let playerSort = { key: "avg", dir: -1 };
function renderPlayers() {
  const p = document.getElementById("panel-players");
  const batters = DATA.batters || [];
  let html = `<h2 class="section-title">🏃 규정타석 타자 성적</h2>`;
  html += `<p class="hint">NPB 공식(npb.jp) 규정타석 타자 기록입니다. 구단으로 필터링하거나, 표 머리글을 눌러 정렬할 수 있습니다.</p>`;
  if (!batters.length) { p.innerHTML = html + emptyBox(SEED_MSG); return; }

  const teams = [...new Set(batters.map(b => b.team))].sort();
  html += `<div class="controls">
    <select id="pteam"><option value="">전체 구단</option>${teams.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select>
  </div><div class="table-scroll"><div id="ptable"></div></div>`;
  p.innerHTML = html;

  const cols = [
    { k: "name", label: "선수", cls: "pname" }, { k: "team", label: "구단", cls: "pteam" },
    { k: "avg", label: "타율", num: 1 }, { k: "hr", label: "홈런", num: 1 },
    { k: "obp", label: "출루율", num: 1 }, { k: "slg", label: "장타율", num: 1 }, { k: "sb", label: "도루", num: 1 },
  ];

  const draw = () => {
    const filter = p.querySelector("#pteam").value;
    let rows = batters.filter(b => !filter || b.team === filter);
    rows.sort((a, b) => {
      const va = a[playerSort.key], vb = b[playerSort.key];
      if (typeof va === "string") return playerSort.dir * va.localeCompare(vb);
      return playerSort.dir * (va - vb);
    });
    const fmt = (k, v) => (["avg", "obp", "slg"].includes(k)) ? Number(v).toFixed(3).replace(/^0/, "") : v;
    let t = `<table class="stats"><thead><tr>`;
    cols.forEach(c => {
      const arrow = playerSort.key === c.k ? (playerSort.dir < 0 ? " ▼" : " ▲") : "";
      t += `<th data-k="${c.k}">${esc(c.label)}${arrow}</th>`;
    });
    t += `</tr></thead><tbody>`;
    rows.forEach(b => {
      t += `<tr>
        <td class="pname">${esc(b.name)}</td>
        <td class="pteam"><span class="dot" style="display:inline-block;background:${esc(b.color)};margin-right:5px"></span>${esc(b.team)}</td>
        <td class="num">${fmt("avg", b.avg)}</td><td class="num">${esc(b.hr)}</td>
        <td class="num">${fmt("obp", b.obp)}</td><td class="num">${fmt("slg", b.slg)}</td><td class="num">${esc(b.sb)}</td>
      </tr>`;
    });
    t += `</tbody></table>`;
    p.querySelector("#ptable").innerHTML = t;
    p.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
      const k = th.dataset.k;
      if (playerSort.key === k) playerSort.dir *= -1;
      else { playerSort.key = k; playerSort.dir = (k === "name" || k === "team") ? 1 : -1; }
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
  html += `<div class="controls"><select id="ncat"><option value="">전체 분야</option>${cats.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")}</select></div><div id="nlist"></div>`;
  p.innerHTML = html;

  const draw = () => {
    const f = p.querySelector("#ncat").value;
    const list = news.filter(n => !f || n.category === f);
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
const RENDERERS = {
  schedule: renderSchedule, standings: renderStandings, postseason: renderPostseason,
  players: renderPlayers, stadiums: renderStadiums, teams: renderTeams, news: renderNews,
};
const rendered = {};
function activate(tab) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  document.querySelectorAll(".panel").forEach(pn => pn.classList.toggle("active", pn.id === `panel-${tab}`));
  if (!rendered[tab]) { RENDERERS[tab](); rendered[tab] = true; }
  if (tab === "stadiums") setTimeout(() => window.dispatchEvent(new Event("resize")), 250);
}

/* ---------- 시작 ---------- */
(async function init() {
  await loadAll();
  buildTeamColorMap();

  const meta = DATA.meta;
  document.getElementById("updated-at").textContent =
    meta && meta.updated_at_kst ? `갱신: ${meta.updated_at_kst} (KST)` : "갱신: —";

  document.querySelectorAll(".tab").forEach(t =>
    t.addEventListener("click", () => activate(t.dataset.tab)));

  activate("schedule");
  document.getElementById("loader").classList.add("hide");
})();
