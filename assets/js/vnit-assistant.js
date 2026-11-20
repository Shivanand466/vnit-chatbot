// VNIT Assistant: the chatbot as a floating chat window on every page of the site.
// The logic follows vnit-chatbot/frontend/index.html (the chatbot's own chat
// page) so both behave the same: follow-ups, clarifying buttons, the student
// profile, sources, "How I found this", the verification badge and feedback, and
// since agent v2 the answer streamed with its steps shown live, Stop, Copy,
// Regenerate, suggested follow-ups and tables. It prefers /ask/stream and falls
// back to /ask, so it still works with an older chatbot server.
// Conversation state lives in memory only (no localStorage, no cookies), exactly
// like the chat page, so it is forgotten when the visitor changes page.
(function () {
  "use strict";

  var GREETING = "Ask about admissions, fees, hostels, the academic calendar, placements, " +
    "departments or notices. Answers come only from VNIT's own pages and documents, with sources.";
  var NOT_RUNNING = "The VNIT Assistant isn't running. Start it with start_website.bat.";

  // Suggested questions per section of the site, from the demo table in
  // vnit-chatbot/HOW-TO-RUN.md section 3 (questions known to be answered correctly).
  var SUGGESTIONS = {
    hostel: [
      "What is the hostel fee?",
      "What is the hostel fee for first year B.Tech boys for the Winter 2026 session?",
      "What is the hostel wifi password?"
    ],
    academics: [
      "When are the end semester exams for first year B.Tech in Winter 2026?",
      "When do classes start for first year B.Tech students in Winter 2026?",
      "What is the email of the Dean (Academic)?"
    ],
    admissions: [
      "What is the yearly tuition fee for B.Tech students in the OPEN category?",
      "What tuition fee do SC/ST B.Tech students pay?",
      "What is the total tuition fee for all four years of B.Tech for an OPEN category student?"
    ],
    departments: [
      "How many undergraduate students does Civil Engineering enroll annually?",
      "What specializations does the Electrical Engineering M.Tech offer?",
      "When was the Mechanical Engineering department established?"
    ],
    research: [
      "Tell me about the 5G lab and when was it announced",
      "Who is the current Director of VNIT?",
      "What is the email of the Dean (Academic)?"
    ],
    people: [
      "Who is the current Director of VNIT?",
      "What is the email of the Dean (Academic)?",
      "When was the Mechanical Engineering department established?"
    ],
    scholarships: [
      "How much money does the Kotak Kanya Scholarship give per year?",
      "What is the last date to apply for the IDFC FIRST Bank Engineering Scholarship?",
      "What tuition fee do SC/ST B.Tech students pay?"
    ],
    general: [
      "What is the hostel fee for first year B.Tech boys for the Winter 2026 session?",
      "When do classes start for first year B.Tech students in Winter 2026?",
      "Who is the current Director of VNIT?"
    ]
  };

  var SECTION_SUGGESTIONS = {
    academics: "academics", admissions: "admissions", departments: "departments",
    research: "research", about: "people", administration: "people", notices: "scholarships",
    placements: "general", news: "general", recruitment: "people", more: "people", home: "general"
  };

  // Which suggestions fit which part of the site, by the page's address (as on vnit.ac.in).
  var PATH_SUGGESTIONS = [
    [/hostel|non-saarc|facilities-hostel/, "hostel"],
    [/section\/academics\/(fees|admission)|academic-programs/, "admissions"],
    [/section\/academics|academic-event-calendar/, "academics"],
    [/engineering\/|basic_science\/|\/arch\//, "departments"],
    [/section\/rnc|5g-lab|centre-for-innovation|s-tic|coe/, "research"],
    [/director|deans|registrar|head-of-departments|bog-|chairman|officers/, "people"],
    [/notices/, "scholarships"]
  ];

  var KIND = { understand: "understood", route: "decided", search: "searched", plan: "planned",
    tool: "acted", reflect: "noticed", compact: "tidied", stop: "stopped", answer: "answered",
    verify: "checked", revise: "revised", fallback: "fallback", grade: "graded",
    clarify: "asked back", handoff: "handed off" };

  var turns = [];   // earlier questions and the answers given, {q, a}, so follow-ups work
  var profile = {}; // details picked from clarifying questions (programme, gender...)
  var busy = null;  // the AbortController of the answer being written, while one is
  var els = {};
  var MAX_TURNS = 6;

  function apiUrl() {
    if (window.VNIT_ASSISTANT_API) return window.VNIT_ASSISTANT_API;
    var loc = window.location;
    if (/^https?:$/.test(loc.protocol) && loc.pathname.indexOf("/site/") === 0) return loc.origin + "/ask";
    return "http://127.0.0.1:8000/ask";
  }

  function suggestionsForPage() {
    var path = window.location.pathname;
    var section = document.body.getAttribute("data-section") || "general";
    for (var i = 0; i < PATH_SUGGESTIONS.length; i++) {
      if (PATH_SUGGESTIONS[i][0].test(path)) return SUGGESTIONS[PATH_SUGGESTIONS[i][1]];
    }
    return SUGGESTIONS[SECTION_SUGGESTIONS[section] || "general"];
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Markdown -> HTML for what the model writes: bold, italics, inline code,
  // links, bullet and numbered lists, tables (compare answers) and "Note:"
  // lines. Everything is escaped first, so nothing in an answer can inject
  // HTML into the page; links are kept only as plain http(s) addresses.
  function inline(s) {
    return s
      .replace(/\[([^\]]{1,120})\]\((https?:\/\/[^\s)]+)\)/g, function (m, text, url) {
        return '<a href="' + url + '" target="_blank" rel="noopener">' + text + "</a>";
      })
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[\s(])\*(?!\s)([^*]+?)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>")
      .replace(/`([^`]+?)`/g, "<code>$1</code>")
      .replace(/\[(\d+)\]/g, "<sup>$1</sup>");
  }

  function tableHtml(rows) {
    var rule = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/;
    var html = '<div class="va-tablewrap"><table>';
    rows.forEach(function (r, i) {
      if (rule.test(r)) return;
      var tag = i === 0 && rows[1] && rule.test(rows[1]) ? "th" : "td";
      var cells = r.replace(/^\|/, "").replace(/\|$/, "").split("|");
      html += "<tr>" + cells.map(function (c) {
        return "<" + tag + ">" + inline(c.trim()) + "</" + tag + ">";
      }).join("") + "</tr>";
    });
    return html + "</table></div>";
  }

  function renderAnswer(text) {
    var lines = escapeHtml(String(text || "").replace(/\r/g, "")).split("\n");
    var html = "", list = null, table = [];

    function closeList() { if (list) { html += "</" + list + ">"; list = null; } }
    function closeTable() { if (table.length) { html += tableHtml(table); table = []; } }

    lines.forEach(function (raw) {
      var line = raw.trim();
      if (line.charAt(0) === "|") { closeList(); table.push(line); return; }
      closeTable();
      if (!line) { closeList(); return; }
      var bullet = line.match(/^[-*•]\s+(.*)$/);
      var numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
      var note = line.match(/^(?:\*\*)?(note|caution|important)\s*:?(?:\*\*)?\s*:?\s*(.*)$/i);
      if (bullet) {
        if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
        html += "<li>" + inline(bullet[1]) + "</li>";
      } else if (numbered) {
        if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
        html += "<li>" + inline(numbered[2]) + "</li>";
      } else if (note && note[2]) {
        closeList();
        html += '<div class="va-note"><strong>' + note[1][0].toUpperCase() + note[1].slice(1) +
          ":</strong> " + inline(note[2]) + "</div>";
      } else {
        closeList();
        html += "<p>" + inline(line.replace(/^#+\s*/, "")) + "</p>";
      }
    });
    closeTable();
    closeList();
    return html;
  }

  // ------------------------------------------------------------ building the widget

  function build() {
    els.launcher = el("button", "va-launcher");
    els.launcher.type = "button";
    els.launcher.setAttribute("aria-haspopup", "dialog");
    els.launcher.setAttribute("aria-expanded", "false");
    els.launcher.innerHTML = '<span class="va-launcher-icon" aria-hidden="true"></span><span class="va-launcher-label">Ask VNIT Assistant</span>';

    els.panel = el("section", "va-panel");
    els.panel.id = "vnit-assistant";
    els.panel.hidden = true;
    els.panel.setAttribute("role", "dialog");
    els.panel.setAttribute("aria-labelledby", "va-title");
    els.launcher.setAttribute("aria-controls", "vnit-assistant");

    var head = el("div", "va-head");
    var title = el("h2", "va-title", "VNIT Assistant");
    title.id = "va-title";
    els.close = el("button", "va-close");
    els.close.type = "button";
    els.close.setAttribute("aria-label", "Close the VNIT Assistant");
    els.close.innerHTML = '<span aria-hidden="true">&times;</span>';
    head.append(title, els.close);

    els.chat = el("div", "va-chat");
    els.chat.setAttribute("aria-live", "polite");
    var intro = el("div", "va-intro");
    intro.appendChild(el("p", "va-greeting", GREETING));
    var chips = el("div", "va-starters");
    suggestionsForPage().forEach(function (q) {
      var b = el("button", "", q);
      b.type = "button";
      b.addEventListener("click", function () { els.input.value = q; ask(); });
      chips.appendChild(b);
    });
    intro.appendChild(chips);
    els.chat.appendChild(intro);

    els.form = el("form", "va-form");
    var label = el("label", "va-sr", "Your question");
    label.setAttribute("for", "va-question");
    els.input = el("textarea", "va-input");
    els.input.id = "va-question";
    els.input.rows = 1;
    els.input.placeholder = "Ask about fees, hostels, admissions, exams…";
    els.input.setAttribute("autocomplete", "off");
    els.send = el("button", "va-send", "Ask");
    els.send.type = "submit";
    els.form.append(label, els.input, els.send);

    var hint = el("p", "va-hint", "Enter to send · follow-ups like “and for girls?” work ");
    els.clear = el("button", "va-clear", "· Clear my details");
    els.clear.type = "button";
    els.clear.hidden = true;
    hint.appendChild(els.clear);

    els.panel.append(head, els.chat, els.form, hint);
    document.body.append(els.launcher, els.panel);
  }

  function showProfile() { els.clear.hidden = Object.keys(profile).length === 0; }

  function open() {
    els.panel.hidden = false;
    els.launcher.setAttribute("aria-expanded", "true");
    document.documentElement.classList.add("va-open");
    els.input.focus();
  }

  function close() {
    els.panel.hidden = true;
    els.launcher.setAttribute("aria-expanded", "false");
    document.documentElement.classList.remove("va-open");
    els.launcher.focus();
  }

  // ------------------------------------------------------------ conversation

  function addTurn(cls) {
    var turn = el("div", "va-turn " + cls);
    els.chat.appendChild(turn);
    els.chat.scrollTop = els.chat.scrollHeight;
    return turn;
  }

  function addMine(text) {
    var turn = addTurn("va-me");
    turn.appendChild(el("div", "va-bubble", text));
  }

  // While the answer is being worked out: the steps as small lines (the newest
  // with a spinner), then the answer itself as it is written.
  function addThinking() {
    var turn = addTurn("va-bot");
    var bubble = el("div", "va-bubble");
    turn.live = el("div", "va-live");
    turn.body = el("div", "va-body va-cursor");
    bubble.append(turn.live, turn.body);
    turn.appendChild(bubble);
    liveStep(turn, "Searching VNIT’s documents…");
    return turn;
  }

  function liveStep(turn, text) {
    if (!turn.live) return;
    turn.live.querySelectorAll(".va-now").forEach(function (d) { d.classList.remove("va-now"); });
    var line = el("div", "va-now", text.length > 160 ? text.slice(0, 160) + "…" : text);
    turn.live.appendChild(line);
    els.chat.scrollTop = els.chat.scrollHeight;
  }

  function stepText(t) {
    if (t.step === "tool" && t.tool === "read_document") return "Opening: " + t.text.replace(/^Looked inside /, "");
    return t.text;
  }

  function rate(data, rating, row, status) {
    row.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
    fetch(apiUrl().replace(/\/ask$/, "/feedback"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: data.understood_as || data.question,
        answer: data.answer, mode: data.mode, rating: rating
      })
    }).then(function (resp) {
      status.textContent = resp.ok ? "Thanks!" : "Could not save that.";
    }).catch(function () {
      status.textContent = "Could not save that.";
    });
  }

  function addUnderstood(turn, data) {
    if (!data.understood_as) return;
    var note = el("div", "va-understood");
    note.append(el("span", "", "Understood as"), el("span", "", data.understood_as));
    turn.appendChild(note);
  }

  function addSources(bubble, data) {
    if (!data.sources || !data.sources.length) return;
    var src = el("div", "va-sources");
    // Numbered like the [1], [2] citations in the answer, when it has any.
    var numbered = /\[\d+\]/.test(data.answer || "");
    data.sources.forEach(function (s, i) {
      var url = String(s.url || "");
      var safe = /^https?:\/\//.test(url);
      var a = el(safe ? "a" : "span");
      if (safe) { a.href = url; a.target = "_blank"; a.rel = "noopener"; a.title = url; }
      if (numbered) a.appendChild(el("b", "", String(i + 1)));
      a.appendChild(document.createTextNode(s.date ? s.title + " (" + s.date + ")" : String(s.title || url)));
      src.appendChild(a);
    });
    bubble.appendChild(src);
  }

  // A clarifying question: one button per choice. Picking one remembers it and
  // asks the original question again with it filled in.
  function addChoices(bubble, turn, data) {
    if (!data.clarify || !data.clarify.choices) return;
    var row = el("div", "va-choices");
    data.clarify.choices.forEach(function (c) {
      var b = el("button", "", c.label);
      b.type = "button";
      b.addEventListener("click", function () {
        row.querySelectorAll("button").forEach(function (x) { x.disabled = true; });
        profile[data.clarify.slot] = c.value;
        showProfile();
        send(data.question, c.label);
      });
      row.appendChild(b);
    });
    bubble.appendChild(row);
  }

  // The agent's steps: what it searched, which documents it opened, what it
  // calculated, and what the verifier found, so it can be checked, not trusted.
  function addSteps(turn, data) {
    if (!data.trace || !data.trace.length) return;
    var details = el("details", "va-steps");
    var tools = data.trace.filter(function (t) { return t.step === "tool"; }).length;
    details.appendChild(el("summary", "", "How I found this (" + data.trace.length + " steps" +
      (tools ? ", " + tools + " extra lookup" + (tools > 1 ? "s" : "") : "") + ")"));
    var list = el("ol");
    data.trace.forEach(function (t) {
      var li = el("li");
      li.append(el("span", "va-kind", KIND[t.step] || t.step), document.createTextNode(t.text));
      list.appendChild(li);
    });
    details.appendChild(list);
    turn.appendChild(details);
  }

  function tool(label, title, onClick) {
    var b = el("button", "va-tool", label);
    b.type = "button";
    b.title = title;
    b.addEventListener("click", onClick);
    return b;
  }

  function addMeta(turn, data) {
    var meta = el("div", "va-meta");
    if (data.mode !== "error") {
      meta.appendChild(tool("Copy", "Copy the answer", function (e) {
        var b = e.currentTarget;
        var done = function (text) { b.textContent = text; setTimeout(function () { b.textContent = "Copy"; }, 1500); };
        if (navigator.clipboard) navigator.clipboard.writeText(data.answer).then(function () { done("Copied"); },
                                                                                   function () { done("Copy failed"); });
        else done("Copy failed");
      }));
    }
    meta.appendChild(tool("Regenerate", "Ask the same question again", function () {
      if (!busy && data.question) send(data.question, data.question);
    }));
    meta.appendChild(el("span", "va-mode", data.mode));
    var v = data.verification;
    if (v && (v.verdict === "verified" || v.verdict === "unsupported")) {
      var ok = v.verdict === "verified";
      meta.appendChild(el("span", "va-check " + (ok ? "va-ok" : "va-warn"),
        ok ? "✓ " + v.checked + " figure" + (v.checked === 1 ? "" : "s") + " checked against sources"
           : "⚠ not confirmed: " + (v.unsupported || []).join(", ")));
    }
    // Rating only makes sense for a real answer, not a greeting, a question back or an error.
    var mode = String(data.mode);
    if (mode.indexOf("direct") !== 0 && mode !== "clarify" && mode !== "error" && mode !== "stopped") {
      var row = el("span", "va-rate");
      var status = el("span", "va-rate-status");
      [["\u{1F44D}", "up", "Helpful"], ["\u{1F44E}", "down", "Not helpful"]].forEach(function (r) {
        var b = el("button", "", r[0]);
        b.type = "button";
        b.title = r[2];
        b.setAttribute("aria-label", r[2]);
        b.addEventListener("click", function () { rate(data, r[1], row, status); });
        row.appendChild(b);
      });
      row.appendChild(status);
      meta.appendChild(row);
    }
    turn.appendChild(meta);
  }

  // Follow-up questions the server suggests, as chips under the newest answer only.
  function addSuggestions(turn, data) {
    els.chat.querySelectorAll(".va-suggest").forEach(function (s) { s.remove(); });
    if (!data.suggestions || !data.suggestions.length) return;
    var row = el("div", "va-suggest");
    data.suggestions.forEach(function (q) {
      var b = el("button", "", q);
      b.type = "button";
      b.addEventListener("click", function () { if (!busy) send(q, q); });
      row.appendChild(b);
    });
    turn.appendChild(row);
  }

  function fillAnswer(turn, data, corrected) {
    turn.innerHTML = "";
    turn.live = turn.body = null;
    addUnderstood(turn, data);
    var bubble = el("div", "va-bubble");
    bubble.innerHTML = renderAnswer(data.answer);
    addSources(bubble, data);
    turn.appendChild(bubble);
    if (corrected) turn.appendChild(el("div", "va-corrected", "Corrected after checking against the documents."));
    addChoices(bubble, turn, data);
    addSteps(turn, data);
    addMeta(turn, data);
    addSuggestions(turn, data);
    els.chat.scrollTop = els.chat.scrollHeight;
  }

  function ask() {
    var question = els.input.value.trim();
    if (!question || busy) return;
    els.input.value = "";
    els.input.style.height = "auto";
    send(question, question);
  }

  function setBusy(controller) {
    busy = controller;
    els.send.textContent = controller ? "Stop" : "Ask";
    els.send.classList.toggle("va-stop", !!controller);
  }

  function requestBody(question) {
    return JSON.stringify({ question: question, turns: turns.slice(-MAX_TURNS),
                            history: turns.slice(-3).map(function (t) { return t.q; }), profile: profile });
  }

  function errorAnswer(question, resp) {
    return resp.json().catch(function () { return {}; }).then(function (body) {
      return { question: question, answer: body.detail || "HTTP " + resp.status, sources: [], mode: "error" };
    });
  }

  // Server-Sent Events from /ask/stream: "step" lines, "token" pieces of the
  // answer, "replace" when the checker made it revise, then "done" (what /ask
  // returns). Resolves to null when the server has no /ask/stream (an older one).
  function streamAnswer(question, turn, signal) {
    return fetch(apiUrl().replace(/\/ask$/, "/ask/stream"), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: requestBody(question), signal: signal
    }).then(function (resp) {
      if (resp.status === 404 || resp.status === 405 || !resp.body) return null;
      if (!resp.ok) return errorAnswer(question, resp);
      var reader = resp.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "", text = "", corrected = false;
      function paint() { if (turn.body) { turn.body.innerHTML = renderAnswer(text); els.chat.scrollTop = els.chat.scrollHeight; } }
      function pump() {
        return reader.read().then(function (r) {
          if (r.done) return text ? { question: question, answer: text, sources: [], mode: "stopped" } : null;
          buffer += decoder.decode(r.value, { stream: true });
          var cut;
          while ((cut = buffer.indexOf("\n\n")) >= 0) {
            var block = buffer.slice(0, cut);
            buffer = buffer.slice(cut + 2);
            if (block.charAt(0) === ":") continue;            // keep-alive ping
            var event = (block.match(/^event: (.*)$/m) || [])[1];
            var raw = (block.match(/^data: (.*)$/m) || [])[1];
            if (!event || raw === undefined) continue;
            var data = JSON.parse(raw);
            if (event === "step") liveStep(turn, stepText(data));
            else if (event === "token") { if (!text) liveStep(turn, "Writing the answer…"); text += data; paint(); }
            else if (event === "replace") { text = data; corrected = true; paint(); }
            else if (event === "done") { data._corrected = corrected; return data; }
            else if (event === "error") return { question: question, answer: data.message, sources: [], mode: "error" };
          }
          return pump();
        });
      }
      return pump();
    });
  }

  function plainAnswer(question, signal) {
    return fetch(apiUrl(), {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: requestBody(question), signal: signal
    }).then(function (resp) { return resp.ok ? resp.json() : errorAnswer(question, resp); });
  }

  // `shown` is what appears as the visitor's message: the question itself, or
  // the choice they clicked ("B.Tech") when a clarified question is re-asked.
  function send(question, shown) {
    if (busy) return;
    addMine(shown);
    var pending = addThinking();
    var controller = new AbortController();
    setBusy(controller);

    streamAnswer(question, pending, controller.signal).catch(function (err) {
      if (err && err.name === "AbortError") throw err;
      return null;                                     // the stream failed: try /ask
    }).then(function (data) {
      return data || plainAnswer(question, controller.signal);
    }).then(function (data) {
      fillAnswer(pending, data, data._corrected);
      if (data.mode !== "error" && data.mode !== "clarify") {
        turns.push({ q: data.understood_as || question, a: data.answer });
        turns = turns.slice(-50);
      }
    }).catch(function (err) {
      if (err && err.name === "AbortError") {
        var partial = pending.body ? pending.body.innerText.trim() : "";
        fillAnswer(pending, { question: question, answer: (partial ? partial + "\n\n" : "") + "*Stopped.*",
                              sources: [], mode: "stopped" });
      } else {
        fillAnswer(pending, { question: question, answer: NOT_RUNNING, sources: [], mode: "error" });
      }
    }).then(function () {
      setBusy(null);
      els.input.focus();
    });
  }

  // ------------------------------------------------------------ wiring

  function wire() {
    els.launcher.addEventListener("click", function () {
      if (els.panel.hidden) open(); else close();
    });
    els.close.addEventListener("click", close);
    els.clear.addEventListener("click", function () { profile = {}; showProfile(); });
    els.form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (busy) busy.abort();          // the button reads Stop while an answer is written
      else ask();
    });
    els.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy) ask(); }
    });
    els.input.addEventListener("input", function () {
      els.input.style.height = "auto";
      els.input.style.height = Math.min(els.input.scrollHeight, 120) + "px";
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !els.panel.hidden) close();
    });
    document.querySelectorAll("[data-open-assistant]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.preventDefault(); open(); });
    });
  }

  function start() {
    build();
    wire();
    if (new URLSearchParams(window.location.search).get("assistant") === "open") open();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
