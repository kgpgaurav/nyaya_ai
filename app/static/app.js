"use strict";

const UI = {
  en: {
    language: "Language", caseFile: "Case file", newCase: "New case", modeLegend: "What do you want to do?",
    m_auto: "Just talk", m_build_case: "Build my case", m_explain: "My options", m_draft: "Draft a letter",
    m_practice: "Practise", m_notice: "Explain a notice", typeHere: "Describe your problem",
    placeholder: "What happened? Write it the way you'd tell a friend.", speak: "Speak instead of typing", send: "Send",
    whatYouToldMe: "What you've told me", factsEmpty: "Facts appear here as you describe what happened, each with the words you used.",
    stillNeeded: "Still useful to know", timeline: "Timeline", documents: "Drafts",
    limits: "Nyaya gives general information from a small set of checked sources. It is not a lawyer and can be wrong. For police, court or family matters, speak to a lawyer. Free legal aid: 15100.",
    export: "Download my case", deleteData: "Delete my data", confirmDraft: "Facts are right, write the draft", notYet: "Not yet",
    thinking: "Checking your words and my sources…", listening: "Listening. Tap the microphone again to stop.",
    transcribing: "Turning your voice into text…", youSaid: "From your voice", sources: "Sources",
    reviewed: "checked", confirmAgain: "Tap again to clear this case", deleted: "Your case was deleted.",
    micBlocked: "Microphone access was blocked. You can type instead.", noVoice: "Voice input isn't set up on this server. Please type.",
    modelMissing: "The AI model isn't configured on this server yet, so replies are off.",
    yourWords: "your words", edited: "edited by you", confirmed: "confirmed",
    domain_deposit: "Security deposit not returned", domain_refund: "Refund or faulty purchase",
    domain_salary: "Unpaid salary", domain_notice: "A notice you received", domain_unknown: "Not sure yet", domain_other: "Outside what I cover",
    asks: "It asks you to", sentBy: "Sent by", download: "Download", deadline: "Deadline in the notice",
  },
  hi: {
    language: "भाषा", caseFile: "केस फ़ाइल", newCase: "नया केस", modeLegend: "आप क्या करना चाहते हैं?",
    m_auto: "बस बात करें", m_build_case: "केस बनाएं", m_explain: "मेरे विकल्प", m_draft: "पत्र बनाएं",
    m_practice: "अभ्यास", m_notice: "नोटिस समझें", typeHere: "अपनी समस्या बताएं",
    placeholder: "क्या हुआ? वैसे लिखिए जैसे किसी दोस्त को बताते।", speak: "लिखने की जगह बोलें", send: "भेजें",
    whatYouToldMe: "आपने क्या बताया", factsEmpty: "जैसे-जैसे आप बताएंगे, तथ्य यहां आपके शब्दों के साथ दिखेंगे।",
    stillNeeded: "यह जानना भी उपयोगी होगा", timeline: "घटनाक्रम", documents: "ड्राफ्ट",
    limits: "Nyaya कुछ जांचे हुए स्रोतों से सामान्य जानकारी देता है। यह वकील नहीं है और गलत हो सकता है। पुलिस, अदालत या पारिवारिक मामलों में वकील से बात करें। मुफ्त कानूनी सहायता: 15100।",
    export: "मेरा केस डाउनलोड करें", deleteData: "मेरा डेटा मिटाएं", confirmDraft: "तथ्य सही हैं, ड्राफ्ट बनाएं", notYet: "अभी नहीं",
    thinking: "आपके शब्द और मेरे स्रोत जांच रहा हूं…", listening: "सुन रहा हूं। रोकने के लिए माइक फिर दबाएं।",
    transcribing: "आपकी आवाज़ को लिख रहा हूं…", youSaid: "आपकी आवाज़ से", sources: "स्रोत",
    reviewed: "जांचा गया", confirmAgain: "यह केस मिटाने के लिए फिर दबाएं", deleted: "आपका केस मिटा दिया गया।",
    micBlocked: "माइक्रोफ़ोन की अनुमति नहीं मिली। आप लिख सकते हैं।", noVoice: "इस सर्वर पर आवाज़ से इनपुट चालू नहीं है। कृपया लिखें।",
    modelMissing: "इस सर्वर पर AI मॉडल अभी सेट नहीं है, इसलिए जवाब बंद हैं।",
    yourWords: "आपके शब्द", edited: "आपने बदला", confirmed: "पुष्टि हुई",
    domain_deposit: "सिक्योरिटी डिपॉज़िट वापस नहीं मिली", domain_refund: "रिफंड या खराब सामान",
    domain_salary: "बकाया वेतन", domain_notice: "आपको मिला नोटिस", domain_unknown: "अभी तय नहीं", domain_other: "मेरे दायरे से बाहर",
    asks: "यह आपसे कहता है", sentBy: "भेजने वाला", download: "डाउनलोड", deadline: "नोटिस में समय-सीमा",
  },
};

const $ = (sel) => document.querySelector(sel);
const state = { lang: "en", config: null, recorder: null, chunks: [], busy: false, deleteArmed: false };

function ui(key) {
  const table = UI[state.lang === "hi" ? "hi" : "en"];
  return table[key] || UI.en[key] || key;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === "") continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, options = {}) {
  const headers = Object.assign({ "x-nyaya-client": "web" }, options.headers || {});
  if (options.json !== undefined) {
    headers["content-type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const res = await fetch(path, Object.assign({}, options, { headers, credentials: "same-origin" }));
  let data = null;
  try { data = await res.json(); } catch (_) { data = null; }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function applyChrome() {
  document.documentElement.lang = state.lang === "hi" ? "hi" : "en";
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = ui(n.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = ui(n.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-aria]").forEach((n) => { n.setAttribute("aria-label", ui(n.dataset.i18nAria)); });
}

function showError(message) {
  const box = $("#error");
  box.textContent = message || "";
  box.hidden = !message;
}

function showStatus(message) {
  const box = $("#status");
  box.textContent = message || "";
  box.hidden = !message;
}

function refButton(n, scope) {
  return el("button", {
    type: "button", class: "ref", "aria-label": `${ui("sources")} ${n}`, text: String(n),
    onclick: () => {
      const target = scope.querySelector(`[data-n="${n}"]`);
      if (!target) return;
      target.scrollIntoView({ block: "nearest", behavior: "smooth" });
      target.classList.add("flash");
      setTimeout(() => target.classList.remove("flash"), 1200);
    },
  });
}

function withRefs(text, refs, scope) {
  return [text, ...(refs || []).map((r) => refButton(r, scope))];
}

function renderSources(citations) {
  if (!citations || !citations.length) return null;
  return el("ol", { class: "sources", "aria-label": ui("sources") },
    citations.map((c) => el("li", { "data-n": String(c.n) },
      el("span", { class: "ref", "aria-hidden": "true", text: String(c.n) }), " ",
      el("span", { class: "cite", text: c.citation }), el("br"),
      el("span", { text: c.summary }), el("br"),
      el("span", { class: "src-meta" },
        el("a", { href: c.url, target: "_blank", rel: "noopener noreferrer", text: c.locator || c.url }),
        c.reviewed_on ? ` · ${ui("reviewed")} ${c.reviewed_on}` : ""),
      c.caveat ? el("span", { class: "src-meta" }, el("br"), c.caveat) : null)));
}

function renderAssistant(meta, content) {
  const wrap = el("div", { class: "bubble" });
  const blocks = (meta && meta.blocks) || {};
  const citations = (meta && meta.citations) || [];

  if (meta && meta.pending) {
    wrap.append(renderConfirm(meta.pending));
    return wrap;
  }
  if (blocks.points) {
    if (blocks.points.length) {
      wrap.append(el("ul", { class: "points" }, blocks.points.map((p) => el("li", {}, withRefs(p.text, p.refs, wrap)))));
    }
    if (blocks.hedge) wrap.append(el("p", { class: "warn", text: blocks.hedge }));
    (blocks.notes || []).forEach((n) => wrap.append(el("p", { class: "note", text: n })));
    if (blocks.question) wrap.append(el("p", { class: "question", text: blocks.question }));
  } else if (blocks.practice) {
    const p = blocks.practice;
    if (p.intro) wrap.append(el("p", { class: "note", text: p.intro }));
    wrap.append(el("div", { class: "practice-line practice-them" }, el("span", { class: "who", text: p.who }), p.them));
    wrap.append(el("p", { class: "practice-line practice-tip" }, withRefs(p.tip, p.refs, wrap)));
  } else if (blocks.notice) {
    const n = blocks.notice;
    wrap.append(el("p", { class: "notice-kind", text: n.kind }));
    if (n.sender) wrap.append(el("p", { class: "note", text: `${ui("sentBy")}: ${n.sender}` }));
    n.summary.forEach((s) => wrap.append(el("p", { text: s })));
    if (n.asks) wrap.append(el("p", {}, el("strong", { text: `${ui("asks")}: ` }), n.asks));
    wrap.append(el("p", { class: n.deadline ? "warn" : "note", text: n.deadline_line }));
    (n.law || []).forEach((l) => wrap.append(el("p", {}, withRefs(l.text, l.refs, wrap))));
    if (n.lawyer) wrap.append(el("p", { class: "warn" }, withRefs(n.lawyer, n.lawyer_ref ? [n.lawyer_ref] : [], wrap)));
  } else if (blocks.draft) {
    const d = blocks.draft;
    wrap.append(el("p", { text: d.text }));
    wrap.append(el("div", { class: "downloads" },
      el("a", { href: `/api/case/documents/${d.id}.docx`, download: true, text: `${ui("download")} Word` }),
      el("a", { href: `/api/case/documents/${d.id}.txt`, download: true, text: `${ui("download")} text` })));
    wrap.append(el("div", { class: "preview", text: d.preview }));
  } else if (blocks.canned) {
    const warn = ["danger", "needs_lawyer", "fabrication"].includes(blocks.canned);
    wrap.append(el("p", { class: warn ? "warn" : "", text: blocks.text }));
  } else {
    wrap.append(el("p", { text: content }));
  }
  const src = renderSources(citations);
  if (src) wrap.append(src);
  return wrap;
}

function renderConfirm(pending) {
  const form = $("#tpl-confirm").content.firstElementChild.cloneNode(true);
  form.querySelector(".confirm-prompt").textContent = pending.prompt;
  const rows = form.querySelector(".confirm-rows");
  pending.facts.forEach((f, i) => {
    const id = `confirm-${f.field}-${i}`;
    rows.append(el("div", { class: "confirm-row" },
      el("label", { for: id, text: f.label }),
      el("input", { id, name: f.field, value: f.value, maxlength: "400", "data-original": f.value })));
  });
  form.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = ui(n.dataset.i18n); });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const edits = {};
    form.querySelectorAll("input[name]").forEach((inp) => {
      if (inp.value.trim() && inp.value.trim() !== inp.dataset.original) edits[inp.name] = inp.value.trim();
    });
    sendConfirm(true, edits);
  });
  form.querySelector(".cancel").addEventListener("click", () => sendConfirm(false, {}));
  return form;
}

function renderMessages(c) {
  const list = $("#messages");
  list.replaceChildren();
  if (!c.messages.length) {
    list.append(el("li", { class: "msg assistant" }, el("div", { class: "bubble" }, el("p", { text: c.welcome }))));
  }
  const lastPending = c.pending ? c.messages.map((m) => !!(m.meta && m.meta.pending)).lastIndexOf(true) : -1;
  c.messages.forEach((m, i) => {
    if (m.role === "user") {
      list.append(el("li", { class: "msg user" }, el("div", { class: "bubble", text: m.content }),
        m.meta && m.meta.via === "voice" ? el("span", { class: "via", text: ui("youSaid") }) : null));
    } else if (m.meta && m.meta.pending && i !== lastPending) {
      return;
    } else {
      list.append(el("li", { class: "msg assistant" }, renderAssistant(m.meta, m.content)));
    }
  });
  list.scrollTop = list.scrollHeight;
}

function renderFile(c) {
  $("#domain").textContent = ui(`domain_${c.domain}`);
  const facts = $("#facts");
  facts.replaceChildren(...c.facts.map((f) => el("div", { class: "fact" },
    el("dt", { text: f.label }),
    el("dd", {}, f.value,
      f.confirmed ? el("span", { class: "tick", text: `✓ ${ui("confirmed")}` }) : null,
      el("span", { class: "quote", text: f.edited ? ui("edited") : `${ui("yourWords")}: “${f.quote}”` })))));
  if (c.notice) {
    const rows = [[ui("sentBy"), c.notice.sender], [ui("deadline"), c.notice.deadline], [ui("asks"), c.notice.asks]];
    rows.filter(([, v]) => v).forEach(([k, v]) => facts.append(el("div", { class: "fact" }, el("dt", { text: k }), el("dd", { text: v }))));
  }
  $("#facts-empty").hidden = facts.children.length > 0;
  const missing = $("#missing");
  missing.replaceChildren(...c.missing.map((m) => el("li", { text: m })));
  $("#missing-block").hidden = !c.missing.length || !c.facts.length;
  const timeline = $("#timeline");
  timeline.replaceChildren(...c.events.map((e) => el("li", {}, e.when ? el("span", { class: "when", text: e.when }) : null, e.what)));
  $("#timeline-block").hidden = !c.events.length;
  const docs = $("#documents");
  docs.replaceChildren(...c.documents.map((d) => el("li", {},
    el("a", { href: `/api/case/documents/${d.id}.docx`, download: true, text: `${d.kind.replace("_", " ")} #${d.id} (Word)` }),
    el("a", { href: `/api/case/documents/${d.id}.txt`, download: true, text: "text" }))));
  $("#docs-block").hidden = !c.documents.length;
}

function render(c) {
  renderMessages(c);
  renderFile(c);
}

function setBusy(on, label) {
  state.busy = on;
  $("#send").disabled = on;
  $("#mic").disabled = on && !state.recorder;
  const list = $("#messages");
  const old = list.querySelector(".thinking-row");
  if (old) old.remove();
  if (on) {
    list.append(el("li", { class: "msg assistant thinking-row" }, el("p", { class: "thinking", text: label || ui("thinking") })));
    list.scrollTop = list.scrollHeight;
  }
}

function currentMode() {
  return document.querySelector('input[name="mode"]:checked').value;
}

async function sendText(text) {
  showError("");
  setBusy(true);
  try {
    const data = await api("/api/case/messages", { method: "POST", json: { text, mode: currentMode(), language: $("#language").value } });
    $("#text").value = "";
    render(data.case);
  } catch (err) {
    if (err.status === 401) { await startCase(); showError(err.message); }
    else showError(err.message);
  } finally {
    setBusy(false);
  }
}

async function sendConfirm(confirmed, edits) {
  showError("");
  setBusy(true);
  try {
    const data = await api("/api/case/confirm", { method: "POST", json: { confirmed, edits } });
    render(data.case);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
}

async function sendVoice(blob) {
  showError("");
  setBusy(true, ui("transcribing"));
  const form = new FormData();
  form.append("audio", blob, "voice.webm");
  form.append("mode", currentMode());
  form.append("language", $("#language").value);
  try {
    const data = await api("/api/case/voice", { method: "POST", body: form });
    render(data.case);
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
}

async function toggleMic() {
  const mic = $("#mic");
  if (state.recorder) {
    state.recorder.stop();
    return;
  }
  if (state.config && !state.config.voice_ready) { showError(ui("noVoice")); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    state.chunks = [];
    rec.addEventListener("dataavailable", (e) => { if (e.data.size) state.chunks.push(e.data); });
    rec.addEventListener("stop", () => {
      stream.getTracks().forEach((tr) => tr.stop());
      state.recorder = null;
      mic.setAttribute("aria-pressed", "false");
      showStatus("");
      const blob = new Blob(state.chunks, { type: rec.mimeType || "audio/webm" });
      if (blob.size) sendVoice(blob);
    });
    rec.start();
    state.recorder = rec;
    mic.setAttribute("aria-pressed", "true");
    showStatus(ui("listening"));
  } catch (_) {
    showError(ui("micBlocked"));
  }
}

async function startCase() {
  const data = await api("/api/case", { method: "POST" });
  render(data.case);
}

async function loadCase() {
  try {
    const data = await api("/api/case");
    if (data.case.language && $("#language").value === "auto") state.lang = data.case.language;
    render(data.case);
  } catch (err) {
    if (err.status === 401) await startCase();
    else showError(err.message);
  }
}

function bind() {
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("#text").value.trim();
    if (!text || state.busy) return;
    sendText(text);
  });
  $("#text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("#composer").requestSubmit();
  });
  $("#mic").addEventListener("click", toggleMic);
  $("#language").addEventListener("change", () => {
    const v = $("#language").value;
    state.lang = v === "hi" ? "hi" : "en";
    applyChrome();
    loadCase();
  });
  $("#new-case").addEventListener("click", async () => {
    const btn = $("#new-case");
    if (!state.deleteArmed) {
      state.deleteArmed = true;
      btn.textContent = ui("confirmAgain");
      setTimeout(() => { state.deleteArmed = false; btn.textContent = ui("newCase"); }, 4000);
      return;
    }
    state.deleteArmed = false;
    btn.textContent = ui("newCase");
    await startCase();
  });
  $("#delete-case").addEventListener("click", async () => {
    await api("/api/case", { method: "DELETE" });
    showStatus(ui("deleted"));
    await startCase();
  });
  $("#toggle-file").addEventListener("click", () => {
    const file = $("#case-file");
    const open = file.classList.toggle("open");
    $("#toggle-file").setAttribute("aria-expanded", String(open));
  });
}

async function init() {
  bind();
  applyChrome();
  try {
    state.config = await api("/api/config");
    if (!state.config.llm_ready) showStatus(ui("modelMissing"));
  } catch (_) {
    state.config = null;
  }
  await loadCase();
  applyChrome();
}

document.addEventListener("DOMContentLoaded", init);
