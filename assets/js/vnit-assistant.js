// VNIT Assistant: the chatbot as a floating chat window on every page of the site.
// The logic is copied from vnit-chatbot/frontend/index.html (the chatbot's own
// chat page) so both behave the same: follow-ups, clarifying buttons, the student
// profile, sources, "How I found this", the verification badge and feedback.
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

  var KIND = { understand: "understood", route: "decided", search: "searched",
    tool: "acted", answer: "answered", verify: "checked", revise: "revised",
    fallback: "fallback", grade: "graded", clarify: "asked back", handoff: "handed off" };

  var asked = [];   // questions so far, so a follow-up can be understood
  var profile = {}; // details picked from clarifying questions (programme, gender...)
  var busy = false;
  var els = {};

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

  // Minimal Markdown -> HTML for what the model actually writes: bold, italics,
  // inline code, bullet and numbered lists, and "Note:" lines. Everything is
  // escaped first, so nothing in an answer can inject HTML into the page.
  function renderAnswer(text) {
    var lines = escapeHtml(String(text || "").replace(/\r/g, "")).split("\n");
    var html = "", list = null;

    function inline(s) {
      return s
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[\s(])\*(?!\s)([^*]+?)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>")
        .replace(/`([^`]+?)`/g, "<code>$1</code>")
        .replace(/\[(\d+)\]/g, "<sup>$1</sup>");
    }
    function closeList() { if (list) { html += "</" + list + ">"; list = null; } }

    lines.forEach(function (raw) {
      var line = raw.trim();
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

  function addThinking() {
    var turn = addTurn("va-bot");
    turn.innerHTML = '<div class="va-bubble"><span class="va-typing" aria-hidden="true"><i></i><i></i><i></i></span>' +
      '<span class="va-typing-label">Searching VNIT’s documents…</span></div>';
    // A question that needs extra lookups can wait for the free plan's
    // per-minute allowance, so say so rather than look frozen.
    var label = turn.querySelector(".va-typing-label");
    var later = setTimeout(function () {
      label.textContent = "Looking further — extra lookups can take up to a minute on the free plan…";
    }, 12000);
    turn.stopTimer = function () { clearTimeout(later); };
    return turn;
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
        send(data.question, c.label, turn.historyAtAsk);
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

  function addMeta(turn, data) {
    var meta = el("div", "va-meta");
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
    if (mode.indexOf("direct") !== 0 && mode !== "clarify" && mode !== "error") {
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

  function fillAnswer(turn, data) {
    if (turn.stopTimer) turn.stopTimer();
    turn.innerHTML = "";
    addUnderstood(turn, data);
    var bubble = el("div", "va-bubble");
    bubble.innerHTML = renderAnswer(data.answer);
    addSources(bubble, data);
    turn.appendChild(bubble);
    addChoices(bubble, turn, data);
    addSteps(turn, data);
    addMeta(turn, data);
    els.chat.scrollTop = els.chat.scrollHeight;
  }

  function ask() {
    var question = els.input.value.trim();
    if (!question || busy) return;
    els.input.value = "";
    els.input.style.height = "auto";
    send(question, question, asked.slice(-3));
  }

  // `shown` is what appears as the visitor's message: the question itself, or
  // the choice they clicked ("B.Tech") when a clarified question is re-asked.
  function send(question, shown, history) {
    if (busy) return;
    busy = true;
    els.send.disabled = true;
    addMine(shown);
    var pending = addThinking();
    pending.historyAtAsk = history;

    fetch(apiUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history, profile: profile })
    }).then(function (resp) {
      if (!resp.ok) {
        return resp.json().catch(function () { return {}; }).then(function (body) {
          fillAnswer(pending, { question: question, answer: body.detail || "HTTP " + resp.status, sources: [], mode: "error" });
        });
      }
      return resp.json().then(function (data) {
        fillAnswer(pending, data);
        asked.push(data.understood_as || question);
      });
    }).catch(function () {
      fillAnswer(pending, { question: question, answer: NOT_RUNNING, sources: [], mode: "error" });
    }).then(function () {
      busy = false;
      els.send.disabled = false;
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
    els.form.addEventListener("submit", function (e) { e.preventDefault(); ask(); });
    els.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); }
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
