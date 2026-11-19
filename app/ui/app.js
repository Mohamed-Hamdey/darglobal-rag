const PREFS_KEY = "dar_wasalt_prefs_v2";

function loadPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY)) || {};
    return {
      source: ["both", "darglobal", "wasalt"].includes(raw.source) ? raw.source : "both",
      lang: ["en", "ar"].includes(raw.lang) ? raw.lang : "en",
      theme: ["dark", "light"].includes(raw.theme) ? raw.theme : "dark",
      history: Array.isArray(raw.history) ? raw.history.slice(-10) : []
    };
  } catch {
    return { source: "both", lang: "en", theme: "dark", history: [] };
  }
}

function savePrefs() {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({
      source: state.source,
      lang: state.lang,
      theme: state.theme,
      history: state.history.slice(-10)
    }));
  } catch { /* ignore storage quota errors */ }
}

const saved = loadPrefs();
const state = {
  source: saved.source,
  lang: saved.lang,
  theme: saved.theme,
  history: saved.history,
  streaming: false,
  ctrl: null,
  citationsMap: new Map()
};

// Apply saved theme immediately on script evaluation to prevent flash
document.documentElement.dataset.theme = state.theme;

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(state.theme);
  syncControlsFromState();
  applyI18n(state.lang);
  fetchMeta();
  wire();
  updateConnectivity();
  restoreHistory();
});

function restoreHistory() {
  if (!state.history.length) return;
  document.getElementById("hero").classList.add("hidden");
  document.getElementById("newChatBtn").classList.remove("hidden");
  const tr = document.getElementById("transcript");
  tr.classList.remove("hidden");

  let lastAsstHost = null;
  state.history.forEach(msg => {
    if (msg.role === "user") {
      addMsg(msg.content, "user");
    } else {
      const host = addMsg("", "assistant", msg.originalQuery || "");
      const textEl = host.querySelector(".as-text");
      textEl.innerHTML = renderMarkdown(msg.content);

      const actionsEl = host.querySelector(".as-actions");
      if (actionsEl && msg.content) {
        actionsEl.classList.remove("hidden");
        actionsEl.querySelector(".copy-btn").dataset.raw = msg.content;
      }
      if (Array.isArray(msg.citations) && msg.citations.length > 0) {
        renderCits(host, msg.citations);
      }
      lastAsstHost = host;
    }
  });

  if (lastAsstHost) renderFollowups(lastAsstHost);
  autoScroll(true);
}

function applyTheme(theme) {
  state.theme = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = state.theme;
  syncThemeButton();
}

function syncThemeButton() {
  const btn = document.getElementById("themeBtn");
  if (!btn) return;
  const t = I18N[state.lang] || I18N.en;
  const label = state.theme === "dark" ? t.theme_to_light : t.theme_to_dark;
  btn.title = label;
  btn.setAttribute("aria-label", label);
  btn.setAttribute("aria-pressed", String(state.theme === "light"));
}

function syncControlsFromState() {
  document.querySelectorAll(".seg-btn").forEach(b => {
    const active = b.dataset.src === state.source;
    b.classList.toggle("active", active);
    b.setAttribute("aria-checked", String(active));
  });
  document.querySelectorAll(".lang-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.lang === state.lang);
  });
}

async function fetchMeta() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch("/api/meta", { signal: controller.signal });
    if (!res.ok) throw new Error("Meta HTTP " + res.status);
    const m = await res.json();
    document.getElementById("st-pages").textContent = m.pages_indexed ?? "47";
    document.getElementById("st-wa").textContent = m.wasalt_listings ?? "319";
    document.getElementById("st-date").textContent = m.data_date ?? "2026-11-19";
    document.getElementById("footMeta").textContent = `Model: ${m.model || "Active"} · Data: ${m.data_date || "Snapshot"}`;
  } catch (e) {
    console.warn("meta fallback", e);
    document.getElementById("st-pages").textContent = "47";
    document.getElementById("st-wa").textContent = "319";
    document.getElementById("st-date").textContent = "2026-11-19";
    document.getElementById("footMeta").textContent = "Dataset Snapshot: 2026-11-19";
  } finally {
    clearTimeout(timeout);
  }
}

function wire() {
  document.getElementById("themeBtn").addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
    savePrefs();
  });

  document.querySelectorAll(".seg-btn").forEach(b => b.addEventListener("click", () => {
    state.source = b.dataset.src;
    syncControlsFromState();
    savePrefs();
  }));

  document.querySelectorAll(".lang-btn").forEach(b => b.addEventListener("click", () => {
    state.lang = b.dataset.lang;
    syncControlsFromState();
    savePrefs();
    applyI18n(state.lang);
  }));

  document.getElementById("resetBtn").addEventListener("click", resetSession);
  document.getElementById("newChatBtn").addEventListener("click", resetSession);

  document.getElementById("starters").addEventListener("click", e => {
    const card = e.target.closest(".starter");
    if (!card) return;
    document.getElementById("input").value = card.dataset.q;
    send();
  });

  document.getElementById("transcript").addEventListener("click", async e => {
    const citeBtn = e.target.closest(".cite-inline");
    if (citeBtn) {
      const cit = state.citationsMap.get(String(citeBtn.dataset.cite));
      if (cit) openDrawer(cit);
      return;
    }

    const copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
      const raw = copyBtn.dataset.raw || "";
      try {
        await navigator.clipboard.writeText(raw);
        copyBtn.textContent = I18N[state.lang].copied;
        setTimeout(() => { copyBtn.textContent = I18N[state.lang].copy; }, 1800);
      } catch { /* clipboard unavailable */ }
      return;
    }

    const regenBtn = e.target.closest(".regen-btn");
    if (regenBtn && !state.streaming) {
      const q = regenBtn.dataset.q;
      if (q) {
        document.getElementById("input").value = q;
        send();
      }
      return;
    }

    const followBtn = e.target.closest(".followup-btn");
    if (followBtn && !state.streaming) {
      document.getElementById("input").value = followBtn.dataset.q;
      send();
    }
  });

  const inp = document.getElementById("input");
  const sendBtn = document.getElementById("sendBtn");

  const syncSendState = () => {
    if (state.streaming) return;
    sendBtn.disabled = !inp.value.trim() || !navigator.onLine;
  };

  inp.addEventListener("input", () => {
    inp.style.height = "auto";
    inp.style.height = Math.min(inp.scrollHeight, 140) + "px";
    syncSendState();
  });

  inp.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) send();
    }
  });

  document.getElementById("composer").addEventListener("submit", e => {
    e.preventDefault();
    if (!sendBtn.disabled) send();
  });

  const main = document.getElementById("main");
  const scrollBtn = document.getElementById("scrollBottomBtn");
  main.addEventListener("scroll", () => {
    const trVisible = !document.getElementById("transcript").classList.contains("hidden");
    const distFromBottom = main.scrollHeight - main.scrollTop - main.clientHeight;
    scrollBtn.classList.toggle("hidden", !trVisible || distFromBottom < 180);
  });
  scrollBtn.addEventListener("click", () => autoScroll(true));

  document.getElementById("drawerClose").addEventListener("click", closeDrawer);
  document.getElementById("drawerBackdrop").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeDrawer();
  });

  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
}

function updateConnectivity() {
  const online = navigator.onLine;
  document.getElementById("offlineBanner").classList.toggle("hidden", online);
  const inp = document.getElementById("input");
  const sendBtn = document.getElementById("sendBtn");
  if (!state.streaming) {
    sendBtn.disabled = !online || !inp.value.trim();
  }
}

function resetSession() {
  if (state.streaming) stop();
  state.history = [];
  state.citationsMap.clear();
  savePrefs(); // Persist cleared history so reload stays clean
  const tr = document.getElementById("transcript");
  tr.innerHTML = "";
  tr.classList.add("hidden");
  document.getElementById("hero").classList.remove("hidden");
  document.getElementById("newChatBtn").classList.add("hidden");
  document.getElementById("scrollBottomBtn").classList.add("hidden");
  document.getElementById("input").focus();
}

function esc(s) {
  return (s || "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function safeUrl(u) {
  if (!u || typeof u !== "string") return "";
  return /^https?:\/\//i.test(u.trim()) ? u.trim() : "";
}

function renderMarkdown(raw) {
  if (!raw) return "";
  const lines = raw.split(/\r?\n/);
  const out = [];
  let i = 0;

  const inline = txt => esc(txt)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(\d+)\]/g, '<sup><button type="button" class="cite-inline" data-cite="$1">[$1]</button></sup>')
    .replace(/((?:SAR|AED|USD|GBP|OMR|QAR)\s?[\d,.]+(?:\s?[MKmk])?)/g, '<span class="num">$1</span>');

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim().startsWith("|") && i + 1 < lines.length && /^\s*\|?[\s:-]+\|/.test(lines[i + 1])) {
      const headers = line.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(lines[i].trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
        i++;
      }
      const ths = headers.map(h => `<th>${inline(h)}</th>`).join("");
      const trs = rows.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("");
      out.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table></div>`);
      continue;
    }

    const hMatch = line.match(/^#{2,4}\s+(.+)$/);
    if (hMatch) {
      out.push(`<h3>${inline(hMatch[1])}</h3>`);
      i++;
      continue;
    }

    if (/^\s*[-*•]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(`<li>${inline(lines[i].replace(/^\s*[-*•]\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(`<li>${inline(lines[i].replace(/^\s*\d+\.\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ol>${items.join("")}</ol>`);
      continue;
    }

    if (!line.trim()) {
      i++;
      continue;
    }

    out.push(`<p>${inline(line)}</p>`);
    i++;
  }

  return out.join("");
}

function addMsg(text, role, originalQuery = "") {
  document.getElementById("hero").classList.add("hidden");
  document.getElementById("newChatBtn").classList.remove("hidden");
  const tr = document.getElementById("transcript");
  tr.classList.remove("hidden");

  const d = document.createElement("div");
  if (role === "user") {
    d.className = "msg msg-user";
    d.dir = "auto";
    d.textContent = text;
  } else {
    const t = I18N[state.lang];
    d.className = "msg msg-asst";
    d.dir = "auto";
    d.innerHTML = `
      <div class="as-hdr">
        <span class="as-label">${t.assistant}</span>
        <div class="as-actions hidden">
          <button type="button" class="act-btn copy-btn">${t.copy}</button>
          <button type="button" class="act-btn regen-btn" data-q="${esc(originalQuery)}">${t.regen}</button>
        </div>
      </div>
      <div class="as-text"><span class="dots"><i></i><i></i><i></i></span></div>`;
  }
  tr.appendChild(d);
  autoScroll(true);
  return d;
}

async function send() {
  const inp = document.getElementById("input");
  const msg = inp.value.trim();
  if (!msg || state.streaming || !navigator.onLine) return;

  inp.value = "";
  inp.style.height = "auto";
  addMsg(msg, "user");

  state.history.push({ role: "user", content: msg });
  state.history = state.history.slice(-10);
  savePrefs();

  await runChat(msg);
}

async function runChat(msg) {
  state.streaming = true;
  const sendBtn = document.getElementById("sendBtn");
  sendBtn.disabled = false;
  sendBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16"><rect x="4" y="4" width="8" height="8" fill="currentColor"/></svg>';
  sendBtn.onclick = stop;
  document.getElementById("loadbar").hidden = false;

  const host = addMsg("", "assistant", msg);
  const textEl = host.querySelector(".as-text");
  const actionsEl = host.querySelector(".as-actions");

  let full = "", cits = [], warned = null, gotFirst = false, wakeTimer = null;
  state.ctrl = new AbortController();
// Inside runChat(), replace the wakeTimer block with:
let responseStarted = false;
const wakingTimer = setTimeout(() => {
  if (!responseStarted) showWaking(textEl);          // no headers yet → cold start
}, 3000);
const thinkingTimer = setTimeout(() => {
  if (responseStarted && !gotFirst) showThinking(textEl); // headers OK, model queued
}, 2500);

// Right after: const res = await fetch(...) and before reading body:
responseStarted = true;
clearTimeout(wakingTimer);

// On first meta/token event:
gotFirst = true;
clearTimeout(wakingTimer); clearTimeout(thinkingTimer);
hideWaking(textEl);

// Add this helper next to showWaking():
function showThinking(el) {
  if (el.querySelector(".notice")) return;
  el.innerHTML = `<div class="rag-status"><span class="rag-dot"></span><span>${I18N[state.lang].thinking}</span></div>`;
}
  // Dynamic RAG Status Indicator
  const statusEl = document.createElement("div");
  statusEl.className = "rag-status";
  const docCount = document.getElementById("st-wa")?.textContent || "300+";
  const searchLabel = state.lang === "ar"
    ? `جارٍ البحث في ${docCount} سجل عقاري…`
    : `Searching ${docCount} indexed records…`;
  statusEl.innerHTML = `<span class="rag-dot"></span><span class="rag-text">${esc(searchLabel)}</span>`;
  textEl.innerHTML = "";
  textEl.appendChild(statusEl);

  const statusTimer = setTimeout(() => {
    const ragTxt = statusEl.querySelector(".rag-text");
    if (ragTxt) {
      ragTxt.textContent = state.lang === "ar"
        ? "قراءة المصادر وصياغة الإجابة…"
        : "Reading sources & synthesizing brief…";
    }
  }, 1500);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: msg,
        source: state.source,
        lang: state.lang,
        history: state.history.slice(0, -1).map(h => ({ role: h.role, content: h.content }))
      }),
      signal: state.ctrl.signal
    });
    if (!res.ok) throw new Error("HTTP " + res.status);

    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop();

      for (const ev of events) {
        if (!ev.startsWith("data: ")) continue;
        let d;
        try { d = JSON.parse(ev.slice(6)); } catch { continue; }

        if (d.type === "meta") {
          gotFirst = true;
          clearTimeout(wakeTimer);
          clearTimeout(statusTimer);
          hideWaking(textEl);
          statusEl.remove();
          if (d.cached) addBadge(host, "cached");
        } else if (d.type === "token") {
          gotFirst = true;
          clearTimeout(wakeTimer);
          clearTimeout(statusTimer);
          hideWaking(textEl);
          if (statusEl.parentNode) statusEl.remove();

          full += d.content;
          textEl.innerHTML = renderMarkdown(full) + '<span class="caret"></span>';
          autoScroll();
        } else if (d.type === "citations") {
          cits = d.data || [];
          renderCits(host, cits);
        } else if (d.type === "warning") {
          warned = d.content;
          addBadge(host, "warn", d.content);
        } else if (d.type === "error") {
          throw new Error(d.content || "stream error");
        }
      }
    }

    if (!full && !cits.length) {
      textEl.innerHTML = `<div class="notice"><div class="n-title">${I18N[state.lang].err_title}</div>${esc(warned || I18N[state.lang].err_txt)}<div><button type="button" class="retry" data-retry="${esc(msg)}">${I18N[state.lang].retry}</button></div></div>`;
    } else {
      textEl.innerHTML = renderMarkdown(full);
      actionsEl.classList.remove("hidden");
      actionsEl.querySelector(".copy-btn").dataset.raw = full;
      renderFollowups(host);
    }

    state.history.push({
      role: "assistant",
      content: full,
      originalQuery: msg,
      citations: cits
    });
    state.history = state.history.slice(-10);
    savePrefs();

    document.getElementById("announce").textContent = `Answer ready, ${cits.length} sources`;
  } catch (err) {
    clearTimeout(statusTimer);
    if (statusEl.parentNode) statusEl.remove();

    if (err.name === "AbortError") {
      textEl.innerHTML = renderMarkdown(full) || `<em>${I18N[state.lang].stopped}</em>`;
      if (full) {
        actionsEl.classList.remove("hidden");
        actionsEl.querySelector(".copy-btn").dataset.raw = full;
        state.history.push({ role: "assistant", content: full, originalQuery: msg, citations: cits });
        savePrefs();
      }
    } else {
      textEl.innerHTML = `<div class="notice error"><div class="n-title">${I18N[state.lang].err_title}</div>${esc(I18N[state.lang].err_txt)}<div><button type="button" class="retry" data-retry="${esc(msg)}">${I18N[state.lang].retry}</button></div></div>`;
    }
  } finally {
    clearTimeout(wakeTimer);
    state.streaming = false;
    state.ctrl = null;
    sendBtn.innerHTML = '<svg class="send-icon" width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8h10.5M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';
    sendBtn.onclick = null;
    sendBtn.disabled = !document.getElementById("input").value.trim() || !navigator.onLine;
    document.getElementById("loadbar").hidden = true;

    host.querySelector(".retry")?.addEventListener("click", e => {
      document.getElementById("input").value = e.target.dataset.retry;
      send();
    });
    autoScroll();
  }
}

function renderFollowups(host) {
  document.querySelectorAll(".followups").forEach(el => el.remove());
  const list = I18N[state.lang].followups?.[state.source] || [];
  if (!list.length) return;

  const wrap = document.createElement("div");
  wrap.className = "followups";
  list.forEach(q => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "followup-btn";
    btn.dataset.q = q;
    btn.textContent = q;
    wrap.appendChild(btn);
  });
  host.appendChild(wrap);
}

function stop() { state.ctrl?.abort(); }

function autoScroll(force = false) {
  const main = document.getElementById("main");
  const nearBottom = main.scrollHeight - main.scrollTop - main.clientHeight < 160;
  if (force || nearBottom) main.scrollTop = main.scrollHeight;
}

function showWaking(el) {
  el.innerHTML = `<div class="notice"><div class="n-title">${I18N[state.lang].waking}</div>${I18N[state.lang].waking_txt}</div>`;
}

function hideWaking(el) {
  if (el.querySelector(".notice")) el.innerHTML = '<span class="dots"><i></i><i></i><i></i></span>';
}

function addBadge(host, kind, text) {
  const row = host.querySelector(".cit-row") || makeCitRow(host);
  const b = document.createElement("span");
  b.className = "badge" + (kind === "warn" ? " warn" : kind === "cached" ? " cached" : "");
  b.textContent = text || I18N[state.lang][kind === "warn" ? "sources_only" : kind];
  row.appendChild(b);
}

function makeCitRow(host) {
  const r = document.createElement("div");
  r.className = "cit-row";
  r.innerHTML = `<span class="label">${I18N[state.lang].sources}</span>`;
  host.appendChild(r);
  return r;
}

function renderCits(host, cits) {
  const row = host.querySelector(".cit-row") || makeCitRow(host);
  row.querySelectorAll(".chip").forEach(c => c.remove());

  cits.forEach(c => {
    state.citationsMap.set(String(c.n), c);
    const url = safeUrl(c.url);
    const dot = c.company === "Wasalt" ? "dot-wa" : c.company === "computed" ? "dot-silver" : "dot-dar";
    const el = document.createElement("button");
    el.type = "button";
    el.className = "chip";
    el.setAttribute("aria-label", `Source ${c.n}: ${c.title}, ${c.company}`);
    el.innerHTML = `
      <span class="n">[${c.n}]</span>
      <i class="dot ${dot}"></i>
      <span class="t">${esc((c.title || "").slice(0, 32))}</span>
      ${url ? `<span class="ext" title="${I18N[state.lang].open}">
        <svg width="11" height="11" viewBox="0 0 14 14">
          <path d="M5 2H2v10h10V9M9 1h4v4M13 1L6 8" fill="none" stroke="currentColor" stroke-width="1.3"/>
        </svg>
      </span>` : ""}`;

    el.addEventListener("click", e => {
      if (e.target.closest(".ext") && url) {
        window.open(url, "_blank", "noopener,noreferrer");
        return;
      }
      openDrawer(c);
    });
    row.appendChild(el);
  });
}

function openDrawer(c) {
  const t = I18N[state.lang];
  const url = safeUrl(c.url);
  const dot = c.company === "Wasalt" ? "dot-wa" : c.company === "computed" ? "dot-silver" : "dot-dar";
  const body = document.getElementById("drawerBody");

  body.innerHTML = `
    <div class="drawer-meta">
      <i class="dot ${dot}"></i>
      <span>[${c.n}] · ${esc(c.company || "Source")}</span>
    </div>
    <h2 class="drawer-title">${esc(c.title || "Untitled Record")}</h2>
    ${url ? `<div class="drawer-url">${esc(url)}</div>` : ""}
    <p class="drawer-snippet">${esc(c.snippet || c.excerpt || c.chunk || t.no_excerpt)}</p>
    ${url ? `<a class="drawer-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${t.open} ↗</a>` : ""}
  `;

  document.getElementById("drawerBackdrop").classList.remove("hidden");
  const drawer = document.getElementById("sourceDrawer");
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  document.getElementById("drawerBackdrop").classList.add("hidden");
  const drawer = document.getElementById("sourceDrawer");
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}