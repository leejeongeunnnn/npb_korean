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
  const g = await loadGame(gid);
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
