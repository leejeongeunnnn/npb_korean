/* 지난 경기 상세: 경기 카드 / 마이팀 최근 경기를 누르면 열리는 창
   data/games/<경기ID>.json 을 읽어 이닝별 점수 · 승패투수 · 홈런 · 득점 장면 · 라인업 · 투수 기록을 보여준다. */

const GAME_CACHE = {};
async function loadGame(gid) {
  if (gid in GAME_CACHE) return GAME_CACHE[gid];
  try {
    const r = await fetch(`data/games/${gid}.json?t=${Math.floor(Date.now() / 600000)}`, { cache: "no-store" });
    GAME_CACHE[gid] = r.ok ? await r.json() : null;
  } catch (e) { GAME_CACHE[gid] = null; }
  return GAME_CACHE[gid];
}

const shortTeam = (t) => (t || "").split(" ")[0];
const dot = (team) => `<span class="dot" style="display:inline-block;background:${readable(colorOf(team))}"></span>`;
const GD = { side: "away" };

function ensureModal() {
  let m = document.getElementById("game-modal");
  if (m) return m;
  m = document.createElement("div");
  m.id = "game-modal";
  m.innerHTML = `<div class="gm-backdrop" data-close="1"></div>
    <div class="gm-panel" role="dialog" aria-modal="true" aria-label="경기 상세">
      <button class="gm-close" data-close="1" aria-label="닫기">✕</button>
      <div class="gm-body"></div>
    </div>`;
  document.body.appendChild(m);
  m.addEventListener("click", (e) => { if (e.target.dataset.close) closeGame(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && m.classList.contains("open")) closeGame(); });
  window.addEventListener("popstate", () => { if (m.classList.contains("open")) closeGame(true); });
  return m;
}

function closeGame(fromHistory = false) {
  const m = document.getElementById("game-modal");
  if (!m) return;
  m.classList.remove("open");
  document.body.classList.remove("gm-lock");
  if (!fromHistory && history.state && history.state.game) history.back();   // 휴대폰 뒤로가기와 맞춤
}

async function openGame(gid, hint = {}) {
  const m = ensureModal();
  const body = m.querySelector(".gm-body");
  m.classList.add("open");
  document.body.classList.add("gm-lock");
  if (!(history.state && history.state.game)) history.pushState({ game: gid }, "");
  body.innerHTML = `<div class="empty"><div class="spinner" style="margin:0 auto 10px"></div>경기 기록을 불러오는 중...</div>`;
  GD.open = gid; GD.mode = "";
  // 경기 전·진행 중: 예고 선발 · 라인업 · 문자중계
  if (hint.state && hint.state !== "final") {
    GD.mode = "today"; GD.hint = hint;
    GD.tab = hint.state === "live" ? "text" : "pitch";
    renderToday(body, gid, hint);
    return;
  }
  const g = await loadGame(gid);
  if (!g && todayDetail(gid)) {      // 방금 끝나서 상세 기록이 아직 없으면 문자중계라도
    GD.mode = "today"; GD.hint = hint; GD.tab = "text";
    renderToday(body, gid, hint);
    return;
  }
  if (!g) {
    body.innerHTML = `<div class="gm-head"><div class="gm-meta">${esc(hint.date || "")} · ${esc(hint.venue || "")}</div>
        <div class="gm-score"><div class="gm-t">${dot(hint.away)}${esc(hint.away || "원정")}</div><b>${esc(hint.sa ?? "-")} : ${esc(hint.sh ?? "-")}</b><div class="gm-t">${dot(hint.home)}${esc(hint.home || "홈")}</div></div></div>
      ${emptyBox("이 경기의 상세 기록은 아직 수집되지 않았어요. 보통 경기가 끝나고 1시간 안에 채워집니다.")}
      <p class="hint" style="text-align:center"><a href="https://baseball.yahoo.co.jp/npb/game/${esc(gid)}/top" target="_blank" rel="noopener" style="color:var(--accent-2)">Yahoo! 재팬 원문 보기 →</a></p>`;
    return;
  }
  GD.side = (MY_TEAM && g.home === MY_TEAM) ? "home" : "away";
  renderGame(body, g);
}

function renderGame(body, g) {
  const away = g.linescore[0] || {}, home = g.linescore[1] || {};
  const ra = parseInt(away.r), rh = parseInt(home.r);
  const KIND = { cs: "클라이맥스 시리즈", japan_series: "일본시리즈" };
  const inns = g.innings && g.innings.length ? g.innings : (away.innings || []).map((_, i) => String(i + 1));

  // 득점 장면을 이닝별로 묶기
  const byInning = [];
  g.plays.forEach(p => {
    const key = `${p.inning}${p.half}`;
    let grp = byInning.find(x => x.key === key);
    if (!grp) byInning.push(grp = { key, label: `${p.inning}회${p.half}`, team: p.team, plays: [] });
    grp.plays.push(p);
  });

  const sideTeam = GD.side === "home" ? g.home : g.away;
  const lineup = (g.lineups || {})[sideTeam] || [];
  const pitch = (g.pitching || {})[sideTeam] || [];

  body.innerHTML = `
    <div class="gm-head">
      <div class="gm-meta">${esc(g.date)} · ${esc(g.venue || "")}${KIND[g.kind] ? ` · <b style="color:var(--accent)">${KIND[g.kind]}</b>` : ""}</div>
      <div class="gm-score">
        <div class="gm-t ${ra > rh ? "win" : ""}">${dot(g.away)}${esc(g.away)}<small>원정</small></div>
        <b>${esc(away.r)} <i>:</i> ${esc(home.r)}</b>
        <div class="gm-t ${rh > ra ? "win" : ""}">${dot(g.home)}${esc(g.home)}<small>홈</small></div>
      </div>
    </div>

    <div class="table-scroll"><table class="gm-line"><thead><tr><th></th>${inns.map(i => `<th>${esc(i)}</th>`).join("")}<th class="tot">계</th><th>안타</th><th>실책</th></tr></thead>
      <tbody>${[away, home].map(l => `<tr><td class="team">${dot(l.team)}${esc(shortTeam(l.team))}</td>${inns.map((_, i) => {
        const v = (l.innings || [])[i] ?? ""; return `<td class="${v !== "" && v !== "0" && v !== "X" && v !== "x" ? "scored" : ""}">${esc(v)}</td>`; }).join("")}
        <td class="tot">${esc(l.r)}</td><td>${esc(l.h)}</td><td>${esc(l.e)}</td></tr>`).join("")}</tbody></table></div>

    <div class="gm-two">
      <div class="card"><div class="mt-ph">🏅 승패 투수</div>
        ${g.decisions.length ? g.decisions.map(d => `<div class="mt-pl"><span><span class="gm-dec ${d.kind === "승리" ? "w" : d.kind === "패전" ? "l" : "s"}">${esc(d.kind)}</span>${esc(d.name)} <em class="pf-jp">${esc(shortTeam(d.team))}</em></span><span class="num">${esc(d.record)}</span></div>`).join("") : '<div class="hint" style="margin:0">기록 없음</div>'}
      </div>
      <div class="card"><div class="mt-ph">💥 홈런</div>
        ${g.homeruns.length ? g.homeruns.map(h => `<div class="mt-pl"><span>${dot(h.team)}${esc(h.name)}</span><span class="num">${h.inning ? `${esc(h.inning)}회 ` : ""}${esc(h.kind)} ${h.no ? `· 시즌 ${esc(h.no)}호` : ""}</span></div>`).join("") : '<div class="hint" style="margin:0">홈런 없음</div>'}
      </div>
    </div>

    <h3 class="sched-sub">⚾ 득점 장면</h3>
    ${byInning.length ? `<div class="gm-plays">${byInning.map(grp => `
      <div class="gm-inn"><div class="gm-inn-l">${esc(grp.label)}</div><div class="gm-inn-r">
        ${grp.plays.map(p => `<div class="gm-play" style="border-left-color:${readable(colorOf(p.team))}">
          <div class="gm-play-top"><b>${esc(p.batter)}</b> <span class="pf-jp">${esc(shortTeam(p.team))} ${esc(p.order)}${p.situation ? ` · ${esc(p.situation)}` : ""}</span></div>
          <div class="gm-play-desc" title="${esc(p.desc_ja)}">${esc(p.desc || p.desc_ja)}</div>
          ${p.score ? `<div class="gm-play-score">${esc(p.score)}</div>` : ""}
        </div>`).join("")}
      </div></div>`).join("")}</div>` : emptyBox("득점 장면이 없습니다.")}

    <h3 class="sched-sub">📋 라인업 · 기록</h3>
    <div class="stage-tabs">
      <button class="stage-chip ${GD.side === "away" ? "active" : ""}" data-side="away">${esc(shortTeam(g.away))} (원정)</button>
      <button class="stage-chip ${GD.side === "home" ? "active" : ""}" data-side="home">${esc(shortTeam(g.home))} (홈)</button>
    </div>
    <div class="card gm-card"><div class="mt-ph">🏏 타자 <span class="mt-sub">타순 · 포지션 · 타석 결과</span></div>
      <table class="gm-tbl gm-bat"><thead><tr><th>#</th><th class="l">선수</th><th>타수</th><th>안타</th><th>타점</th><th>득점</th><th>홈런</th></tr></thead><tbody>
      ${lineup.map(p => `<tr class="${p.starter ? "" : "sub"}"><td class="num">${p.starter ? p.order : ""}</td>
        <td class="l"><div class="gm-pn">${p.starter ? "" : "↳ "}${esc(p.name)}</div><div class="gm-pos">${esc(p.pos)} · 타율 ${esc(p.avg)}</div></td>
        <td class="num">${esc(p.ab)}</td><td class="num ${parseInt(p.h) ? "hl" : ""}">${esc(p.h)}</td>
        <td class="num ${parseInt(p.rbi) ? "hl" : ""}">${esc(p.rbi)}</td><td class="num">${esc(p.r)}</td><td class="num ${parseInt(p.hr) ? "hl" : ""}">${esc(p.hr)}</td></tr>
        ${p.atbats && p.atbats.length ? `<tr class="ab-row"><td></td><td colspan="6">${p.atbats.map(a => `<span class="ab ${/안타|루타|홈런/.test(a.ko) ? "hit" : /볼넷|몸에 맞는|고의/.test(a.ko) ? "walk" : ""}" title="${esc(a.ja)}">${a.inn}회 ${esc(a.ko)}</span>`).join("")}</td></tr>` : ""}`).join("")}
      </tbody></table></div>
    <div class="card gm-card"><div class="mt-ph">⚾ 투수</div>
      <table class="gm-tbl"><thead><tr><th class="l">선수</th><th>이닝</th><th>투구</th><th>피안타</th><th>삼진</th><th>볼넷</th><th>실점</th></tr></thead><tbody>
      ${pitch.map(p => `<tr><td class="l"><div class="gm-pn">${p.state ? `<span class="gm-dec ${p.state === "승" ? "w" : p.state === "패" ? "l" : "s"}">${esc(p.state)}</span>` : ""}${esc(p.name)}</div><div class="gm-pos">자책 ${esc(p.er)} · 시즌 평균자책 ${esc(p.era)}</div></td>
        <td class="num">${esc(ipText(p.ip))}</td><td class="num">${esc(p.np)}</td><td class="num">${esc(p.h)}</td><td class="num">${esc(p.so)}</td>
        <td class="num">${esc(p.bb)}</td><td class="num">${esc(p.r)}</td></tr>`).join("")}
      </tbody></table></div>
    <p class="hint">출처: Yahoo! 재팬 스포츠 · 득점 장면 문장은 야구 용어 사전과 기계 번역으로 옮긴 것이에요(문장에 마우스를 올리면 원문).
      <a href="https://baseball.yahoo.co.jp/npb/game/${esc(g.gid)}/top" target="_blank" rel="noopener" style="color:var(--accent-2)">원문 보기 →</a></p>`;

  body.querySelectorAll("[data-side]").forEach(b => b.addEventListener("click", () => { GD.side = b.dataset.side; renderGame(body, g); }));
}

/* ---------- 오늘 경기: 예고 선발 · 라인업 · 문자중계 ---------- */
function todayDetail(gid) {
  const L = DATA.live;
  const live = L && L.date === todayStr() && L.details && L.details[gid];
  const pre = DATA.today && DATA.today.games && DATA.today.games[gid];
  if (live && pre) return { ...pre, ...live, preview: live.preview || pre.preview,
    starters: Object.keys(live.starters || {}).length ? live.starters : pre.starters,
    lineups: Object.keys(live.lineups || {}).length ? live.lineups : pre.lineups };
  return live || pre || null;
}
function liveGame(gid) {
  const gs = liveGamesToday();
  return gs ? gs.find(x => x.gid === gid) : null;
}

function renderToday(body, gid, hint) {
  const d = todayDetail(gid) || {};
  const lg = liveGame(gid) || {};
  const home = d.home || lg.home || hint.home || "", away = d.away || lg.away || hint.away || "";
  const state = lg.state || d.state || hint.state || "pre";
  const sh = lg.score_home ?? hint.sh ?? "", sa = lg.score_away ?? hint.sa ?? "";
  const status = lg.status || (state === "pre" ? `${d.start || hint.start || ""} 시작` : "");
  const scroll = body.closest(".gm-panel") ? body.closest(".gm-panel").scrollTop : 0;
  const line = d.linescore && d.linescore.length === 2 && d.linescore.some(l => (l.innings || []).some(v => v !== "")) ? d.linescore : null;
  const inns = line ? (line[0].innings || []).map((_, i) => String(i + 1)) : [];
  const tabs = [["text", "📝 문자중계"], ["lineup", "📋 라인업"], ["pitch", "⚾ 선발 투수"]];

  let html = `<div class="gm-head">
      <div class="gm-meta">${esc(d.date || todayStr())} · ${esc(d.venue || hint.venue || "")}</div>
      <div class="gm-score">
        <div class="gm-t">${dot(away)}${esc(away)}<small>원정</small></div>
        <b>${state === "pre" ? '<span class="td-vs">VS</span>' : `${esc(sa === "" ? "-" : sa)} <i>:</i> ${esc(sh === "" ? "-" : sh)}`}</b>
        <div class="gm-t">${dot(home)}${esc(home)}<small>홈</small></div>
      </div>
      <div class="td-status ${state === "live" ? "on" : ""}">${state === "live" ? '<span class="live-dot"></span> ' : ""}${esc(status)}</div>
    </div>`;
  if (line) {
    html += `<div class="table-scroll"><table class="gm-line"><thead><tr><th></th>${inns.map(i => `<th>${i}</th>`).join("")}<th class="tot">계</th><th>안타</th><th>실책</th></tr></thead>
      <tbody>${line.map(l => `<tr><td class="team">${dot(l.team)}${esc(shortTeam(l.team))}</td>${inns.map((_, i) => {
        const v = (l.innings || [])[i] ?? ""; return `<td class="${v !== "" && v !== "0" && !/x/i.test(v) ? "scored" : ""}">${esc(v)}</td>`; }).join("")}
        <td class="tot">${esc(l.r)}</td><td>${esc(l.h)}</td><td>${esc(l.e)}</td></tr>`).join("")}</tbody></table></div>`;
  }
  html += `<div class="stage-tabs td-tabs">${tabs.map(([k, t]) => `<button class="stage-chip ${GD.tab === k ? "active" : ""}" data-ttab="${k}">${t}</button>`).join("")}</div>`;

  if (GD.tab === "text") html += todayText(d, state);
  else if (GD.tab === "lineup") html += todayLineup(d, home, away);
  else html += todayPitch(d, home, away);

  html += `<p class="hint">출처: Yahoo! 재팬 스포츠 · 문자중계는 야구 중계 표현 규칙으로 한국어로 옮겼어요.
    ${state === "live" ? "경기 중에는 1~2분마다 자동으로 새로 고쳐져요. " : ""}
    <a href="https://baseball.yahoo.co.jp/npb/game/${esc(gid)}/text" target="_blank" rel="noopener" style="color:var(--accent-2)">원문 보기 →</a></p>`;
  body.innerHTML = html;
  const panel = body.closest(".gm-panel");
  if (panel && GD.keepScroll) panel.scrollTop = scroll;
  GD.keepScroll = false;
  body.querySelectorAll("[data-ttab]").forEach(b => b.addEventListener("click", () => { GD.tab = b.dataset.ttab; renderToday(body, gid, hint); }));
  body.querySelectorAll("[data-order]").forEach(b => b.addEventListener("click", () => { GD.oldFirst = b.dataset.order === "old"; GD.keepScroll = true; renderToday(body, gid, hint); }));
  body.querySelectorAll("[data-only]").forEach(b => b.addEventListener("click", () => { GD.onlyPoint = !GD.onlyPoint; GD.keepScroll = true; renderToday(body, gid, hint); }));
}

function todayText(d, state) {
  const inns = (d.innings || []).filter(i => i.events && i.events.length);
  if (!inns.length) {
    return emptyBox(state === "pre"
      ? "경기가 시작되면 여기에 한국어 문자중계가 올라와요. 선발 라인업은 보통 경기 시작 약 1시간 전에 발표됩니다."
      : "문자중계를 불러오는 중이에요. 잠시 후 자동으로 채워집니다.");
  }
  const oldFirst = GD.oldFirst ?? (state !== "live");
  const list = oldFirst ? inns : inns.slice().reverse();
  const only = !!GD.onlyPoint;
  let html = `<div class="td-tools">
      <button class="stage-chip ${!oldFirst ? "active" : ""}" data-order="new">최신순</button>
      <button class="stage-chip ${oldFirst ? "active" : ""}" data-order="old">1회부터</button>
      <button class="stage-chip ${only ? "active" : ""}" data-only="1">득점 장면만</button>
    </div>`;
  html += list.map(inn => {
    let evs = inn.events;
    if (only) evs = evs.filter(e => e.lines.some(l => l.k === "point"));
    if (only && !evs.length) return "";
    if (!oldFirst) evs = evs.slice().reverse();
    const sm = inn.summary || {};
    return `<div class="td-inn">
      <div class="td-inn-h" style="border-left-color:${readable(colorOf(inn.team))}">
        <b>${inn.inning}회${inn.half}</b> ${esc(shortTeam(inn.team))} 공격
        ${sm.r !== undefined && sm.r !== "" ? `<span class="td-sum">득점 ${esc(sm.r)} · 안타 ${esc(sm.h)} · 사사구 ${esc(sm.bb)}</span>` : ""}
      </div>
      ${evs.map(e => `<div class="td-ev ${e.lines.some(l => l.k === "point") ? "pt" : ""}">
        ${e.batter ? `<div class="td-bat"><span class="td-no">${esc(e.no)}</span><b>${esc(e.batter)}</b> <span class="pf-jp">${esc(e.order)}${e.situation ? ` · ${esc(e.situation)}` : ""}</span></div>` : ""}
        ${e.lines.map(l => `<div class="td-line ${l.k}">${l.k === "change" ? "🔄 " : ""}${esc(l.t)}${l.tail ? ` <span class="td-tail">${esc(l.tail)}</span>` : ""}${l.score ? `<div class="gm-play-score">${esc(l.score)}</div>` : ""}</div>`).join("")}
      </div>`).join("")}
    </div>`;
  }).join("");
  return html;
}

function todayLineup(d, home, away) {
  const lu = d.lineups || {};
  if (!lu.away && !lu.home) {
    return emptyBox("선발 라인업은 보통 경기 시작 약 1시간 전에 발표돼요. 발표되면 여기에 자동으로 표시됩니다.");
  }
  const col = (side, team) => {
    const t = lu[side];
    return `<div class="card gm-card"><div class="mt-ph">${dot(team)}${esc(shortTeam(team))} <span class="mt-sub">${side === "away" ? "원정 · 선공" : "홈 · 후공"}</span></div>
      ${t ? `<table class="gm-tbl"><tbody>${t.players.map(p => `<tr><td class="num" style="width:28px">${p.order}</td><td class="l"><div class="gm-pn">${esc(p.name)}</div></td><td class="r"><span class="td-pos">${esc(p.pos)}</span></td></tr>`).join("")}</tbody></table>`
          : '<div class="hint" style="margin:0">아직 발표 전</div>'}
    </div>`;
  };
  return `<div class="gm-two">${col("away", away)}${col("home", home)}</div>
    <p class="hint">경기 중 교체(대타·대주자·투수 교체)는 문자중계 탭에 🔄 표시로 나와요.</p>`;
}

function todayPitch(d, home, away) {
  const st = d.starters || {};
  const card = (side, team) => {
    const p = st[side];
    if (!p) return `<div class="card gm-card"><div class="mt-ph">${dot(team)}${esc(shortTeam(team))}</div><div class="hint" style="margin:0">예고 선발 발표 전 (보통 전날 오후 발표)</div></div>`;
    const S = p.stats || {};
    const rows = ["season", "ps", "il"].filter(k => S[k]).map(k => `<tr><td class="l">${esc(S[k].label)}</td><td class="num">${esc(S[k].era)}</td><td class="num">${esc(S[k].g)}</td><td class="num">${esc(S[k].w)}</td><td class="num">${esc(S[k].l)}</td></tr>`).join("");
    return `<div class="card gm-card">
      <div class="mt-ph">${dot(team)}${esc(shortTeam(team))} <span class="mt-sub">${side === "away" ? "원정" : "홈"}</span></div>
      <div class="td-sp">${p.number ? `<div class="td-sp-no">${esc(p.number)}</div>` : '<div class="td-sp-no">⚾</div>'}<div><div class="td-sp-name">${esc(p.name)}</div><div class="gm-pos">${esc(p.hand)}</div></div></div>
      ${rows ? `<table class="gm-tbl"><thead><tr><th class="l"></th><th>평균자책</th><th>등판</th><th>승</th><th>패</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
      ${p.recent && p.recent.length ? `<div class="mt-ph" style="margin-top:12px;font-size:.78rem">최근 등판</div>
        <table class="gm-tbl"><thead><tr><th class="l">날짜</th><th>결과</th><th>이닝</th><th>투구</th><th>피안타</th><th>삼진</th><th>실점</th></tr></thead><tbody>
        ${p.recent.map(r => `<tr><td class="l">${esc(r.date)} <span class="pf-jp">vs ${esc(r.opp)}</span></td><td class="num ${r.res === "승" ? "hl" : ""}">${esc(r.res)}</td><td class="num">${esc(ipText(r.ip))}</td><td class="num">${esc(r.np)}</td><td class="num">${esc(r.h)}</td><td class="num">${esc(r.so)}</td><td class="num">${esc(r.r)}</td></tr>`).join("")}
        </tbody></table>` : ""}
    </div>`;
  };
  let html = `<div class="gm-two">${card("away", away)}${card("home", home)}</div>`;
  if (d.preview) html += `<div class="card td-preview"><div class="mt-ph">🔍 경기 미리보기 <span class="mt-sub">기계 번역</span></div><p>${esc(d.preview)}</p></div>`;
  return html;
}

window.addEventListener("npb-live", () => {
  const m = document.getElementById("game-modal");
  if (!m || !m.classList.contains("open") || GD.mode !== "today") return;
  GD.keepScroll = true;
  renderToday(m.querySelector(".gm-body"), GD.open, GD.hint || {});
});

function ipText(ip) {   // '1.2' → '1⅔', '0.1' → '⅓'
  const m = /^(\d+)(?:\.(\d))?$/.exec(String(ip || ""));
  if (!m) return ip || "";
  const frac = m[2] === "1" ? "⅓" : m[2] === "2" ? "⅔" : "";
  return (m[1] === "0" && frac ? "" : m[1]) + frac;
}

/* 페이지 어디서든 data-gid 가 있는 요소를 누르면 상세 창 */
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-gid]");
  if (!el || !el.dataset.gid) return;
  e.preventDefault();
  openGame(el.dataset.gid, { ...el.dataset });
});
document.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches("[data-gid]")) { e.preventDefault(); e.target.click(); }
});
