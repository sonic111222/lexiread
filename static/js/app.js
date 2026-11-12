import { api } from "./api.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const viewEl = $("#view");
const overlayRoot = $("#overlay-root");
const drawerRoot = $("#drawer-root");
const toastRoot = $("#toast-root");

const READING_KEY = "lexiread:reading:v1";
const READING_SIZE_KEY = "lexiread:reading-size";

const PAGE_META = {
  studio: { kicker: "READING STUDIO", label: "精读台" },
  wordbook: { kicker: "WORD GARDEN", label: "生词本" },
  settings: { kicker: "PREFERENCES", label: "设置" },
};

const state = {
  boot: null,
  page: getPageFromHash(),
  studioMode: "landing",
  reading: null,
  uploadMode: "image",
  pasteText: "",
  wordbook: { items: [], stats: { total: 0, learning: 0, mastered: 0 } },
  wordbookStatus: "",
  wordbookQuery: "",
  settingsDraft: null,
  drawer: null,
  modalOpen: false,
  busy: false,
  confirmCallback: null,
  review: null,
  lastFocus: null,
  ocrDraft: null,
  voices: [],
  storageWarned: false,
};

let busyStepTimer = null;
let currentAudio = null;
let toastSeq = 0;

/* --------------------------------------------------------------------------
   Small utilities
   -------------------------------------------------------------------------- */
function icon(name, className = "") {
  return `<svg class="icon ${className}" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function normalizeLookup(word) {
  return String(word || "")
    .replaceAll("’", "'")
    .trim()
    .replace(/^[^A-Za-z]+/, "")
    .replace(/[^A-Za-z]+$/, "")
    .replace(/\s+/g, " ");
}

function wordKey(word) {
  return normalizeLookup(word).toLowerCase();
}

function formatIpa(raw) {
  const value = String(raw || "").trim();
  if (!value) return "";
  const wrapped = value.startsWith("/") || value.startsWith("[");
  return wrapped ? value : `/${value}/`;
}

function formatDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  if (sameDay) return "今天";
  return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function getPageFromHash() {
  const page = location.hash.replace(/^#\/?/, "");
  return ["studio", "wordbook", "settings"].includes(page) ? page : "studio";
}

function getReadingSize() {
  const stored = Number(localStorage.getItem(READING_SIZE_KEY));
  return Number.isFinite(stored) ? clamp(stored, 16, 23) : 19;
}

function applyReadingSize(size) {
  const safe = clamp(Number(size) || 19, 16, 23);
  document.documentElement.style.setProperty("--reading-size", `${safe}px`);
  localStorage.setItem(READING_SIZE_KEY, String(safe));
  $$('.paper-tool[data-action="font-minus"]').forEach((button) => {
    button.disabled = safe <= 16;
  });
  $$('.paper-tool[data-action="font-plus"]').forEach((button) => {
    button.disabled = safe >= 23;
  });
}

function shuffle(items) {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function truncate(text, length = 160) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function sentenceAround(text, word) {
  const source = String(text || "").replace(/\s+/g, " ").trim();
  if (!source) return "";
  const target = normalizeLookup(word);
  if (!target) return truncate(source, 260);
  const pattern = new RegExp(escapeRegExp(target), "i");
  const match = pattern.exec(source);
  if (!match) return truncate(source, 260);
  const start = match.index;
  const end = start + match[0].length;
  const left = Math.max(
    source.lastIndexOf(".", start - 1),
    source.lastIndexOf("?", start - 1),
    source.lastIndexOf("!", start - 1),
    source.lastIndexOf(";", start - 1),
  );
  const candidates = [".", "?", "!", ";"]
    .map((mark) => source.indexOf(mark, end))
    .filter((index) => index >= 0);
  const right = candidates.length ? Math.min(...candidates) : Math.min(source.length, end + 130);
  return truncate(source.slice(left + 1, right + 1).trim(), 320);
}

function highlightWord(text, word) {
  const safe = esc(text);
  const query = normalizeLookup(word);
  if (!query) return safe;
  const pattern = new RegExp(`(${escapeRegExp(query)})`, "ig");
  return safe.replace(pattern, "<strong>$1</strong>");
}

function wordMeaning(entry, max = 2) {
  const definitions = entry?.definitions || [];
  const values = definitions.slice(0, max).map((item) => {
    const meaning = String(item?.meaning || "").trim();
    const pos = String(item?.pos || "").trim();
    return pos && meaning ? `${pos} ${meaning}` : meaning;
  }).filter(Boolean);
  if (values.length) return values.join("；");
  const english = entry?.english_definitions?.[0]?.definition;
  return english || "";
}

function wordPhonetic(entry) {
  const us = entry?.phonetic?.us || "";
  const uk = entry?.phonetic?.uk || "";
  return formatIpa(us || uk);
}

function aiAnswerMap(reading = state.reading) {
  const map = new Map();
  for (const answer of reading?.ai?.answers || []) {
    const number = Number(answer?.number);
    if (Number.isFinite(number)) map.set(number, answer);
  }
  return map;
}

function aiVocabMatch(word) {
  const key = wordKey(word);
  if (!key || !state.reading?.ai) return null;
  const vocab = state.reading.ai.vocabulary || [];
  const phrases = state.reading.ai.phrases || [];
  return (
    vocab.find((item) => wordKey(item.word) === key) ||
    phrases.find((item) => wordKey(item.phrase) === key) ||
    null
  );
}

function savedMap() {
  const map = new Map();
  for (const item of state.wordbook.items || []) {
    map.set(wordKey(item.word), item);
  }
  return map;
}

function savedWordSet() {
  return new Set((state.wordbook.items || []).map((item) => wordKey(item.word)));
}

function focusWordSet(reading = state.reading) {
  const set = new Set();
  for (const item of reading?.analysis?.vocabulary || []) {
    set.add(wordKey(item.lookup || item.word));
  }
  for (const item of reading?.ai?.vocabulary || []) {
    set.add(wordKey(item.word));
  }
  for (const item of reading?.ai?.phrases || []) {
    set.add(wordKey(item.phrase));
  }
  return set;
}

function mergedVocabulary() {
  const reading = state.reading;
  if (!reading) return [];
  const local = reading.analysis?.vocabulary || [];
  const ai = reading.ai?.vocabulary || [];
  const localByKey = new Map(local.map((item) => [wordKey(item.lookup || item.word), item]));
  const seen = new Set();
  const result = [];
  for (const item of ai) {
    const key = wordKey(item.word);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const localItem = localByKey.get(key);
    result.push({
      word: item.word,
      lookup: normalizeLookup(item.word),
      count: localItem?.count || 0,
      context: localItem?.context || item.example || "",
      meaning_zh: item.meaning_zh || "",
      pos: item.pos || "",
      usage_zh: item.usage_zh || "",
      source: "ai",
    });
  }
  for (const item of local) {
    const key = wordKey(item.lookup || item.word);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push({ ...item, source: "local" });
    if (result.length >= 18) break;
  }
  return result;
}

function mergedPhrases() {
  const reading = state.reading;
  if (!reading) return [];
  const local = reading.analysis?.phrases || [];
  const ai = reading.ai?.phrases || [];
  const localByKey = new Map(local.map((item) => [wordKey(item.normalized || item.phrase), item]));
  const seen = new Set();
  const result = [];
  for (const item of ai) {
    const key = wordKey(item.phrase);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const localItem = localByKey.get(key);
    result.push({
      phrase: item.phrase,
      normalized: item.phrase,
      kind: "AI 短语",
      count: localItem?.count || 0,
      context: localItem?.context || item.example || "",
      meaning_zh: item.meaning_zh || "",
      usage_zh: item.usage_zh || "",
      source: "ai",
    });
  }
  for (const item of local) {
    const key = wordKey(item.normalized || item.phrase);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push({ ...item, source: "local" });
    if (result.length >= 14) break;
  }
  return result;
}

function effectiveKeySentences() {
  const reading = state.reading;
  if (!reading) return [];
  const ai = reading.ai?.key_sentences || [];
  if (ai.length) {
    return ai.map((item) => ({
      sentence: item.sentence,
      translation_zh: item.translation_zh || "",
      analysis_zh: item.analysis_zh || "",
      label: item.label || "重点句",
      source: "ai",
    }));
  }
  return (reading.analysis?.key_sentences || []).map((item) => ({
    sentence: item.sentence,
    translation_zh: "",
    analysis_zh: item.reason_zh || "",
    label: item.label || "关键句",
    paragraph: item.paragraph,
    source: "local",
  }));
}

function answeredCount(reading = state.reading) {
  if (!reading) return 0;
  return (reading.analysis.questions || []).filter((question) => reading.userAnswers?.[question.number]).length;
}

/* --------------------------------------------------------------------------
   Speech & audio
   -------------------------------------------------------------------------- */
function loadVoices() {
  if (!("speechSynthesis" in window)) return;
  state.voices = window.speechSynthesis.getVoices() || [];
}

function preferredVoice(lang) {
  const voices = state.voices.length ? state.voices : (window.speechSynthesis?.getVoices?.() || []);
  return voices.find((voice) => voice.lang === lang) || voices.find((voice) => voice.lang?.startsWith(lang.slice(0, 2)));
}

function speechRate() {
  const rate = Number(state.boot?.settings?.learning?.voice_rate ?? 1);
  return clamp(Number.isFinite(rate) ? rate : 1, 0.6, 1.4);
}

function speakText(text, button = null, langOverride = "") {
  if (!text || !("speechSynthesis" in window)) {
    toast("当前浏览器不支持语音朗读。", "error");
    return;
  }
  window.speechSynthesis.cancel();
  const accent = langOverride || (state.boot?.settings?.learning?.accent === "uk" ? "en-GB" : "en-US");
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = accent;
  utterance.rate = speechRate();
  utterance.pitch = 1;
  const voice = preferredVoice(accent);
  if (voice) utterance.voice = voice;
  if (button) {
    const clear = () => button.classList.remove("playing", "animate-blink");
    button.classList.add("playing");
    utterance.onend = clear;
    utterance.onerror = clear;
    window.setTimeout(clear, Math.max(2200, text.split(/\s+/).length * 420));
  }
  window.speechSynthesis.speak(utterance);
}

function stopAudio() {
  if (currentAudio) {
    try {
      currentAudio.pause();
    } catch {
      /* no-op */
    }
    currentAudio = null;
  }
  document.querySelectorAll(".playing").forEach((element) => element.classList.remove("playing"));
}

function playAudio(url, fallbackText, button = null) {
  stopAudio();
  if (!url) {
    speakText(fallbackText, button);
    return;
  }
  try {
    const audio = new Audio(url);
    currentAudio = audio;
    if (button) {
      button.classList.add("playing");
      const clear = () => button.classList.remove("playing");
      audio.addEventListener("ended", clear);
      audio.addEventListener("error", () => {
        clear();
        speakText(fallbackText, button);
      });
      window.setTimeout(clear, 7000);
    }
    audio.play().catch(() => {
      if (button) button.classList.remove("playing");
      speakText(fallbackText, button);
    });
  } catch {
    speakText(fallbackText, button);
  }
}

/* --------------------------------------------------------------------------
   Toasts, busy overlay, modal & drawer infrastructure
   -------------------------------------------------------------------------- */
function toast(message, type = "info", duration = 3200) {
  if (!message) return;
  const id = ++toastSeq;
  const element = document.createElement("div");
  element.className = `toast ${type === "error" ? "error" : ""}`;
  element.dataset.toastId = String(id);
  element.innerHTML = `${icon(type === "error" ? "alert" : type === "success" ? "check-circle" : "info")}<span>${esc(message)}</span>`;
  toastRoot.appendChild(element);
  window.setTimeout(() => {
    element.classList.add("leaving");
    window.setTimeout(() => element.remove(), 220);
  }, duration);
}

function setBusy({ title = "正在处理…", subtitle = "", steps = [] } = {}) {
  state.busy = true;
  if (state.modalOpen) {
    state.modalOpen = false;
    state.modalOnClose = null;
    state.confirmCallback = null;
  }
  state.lastFocus = document.activeElement;
  let index = 0;
  const dots = steps.length
    ? `<div class="busy-steps">${steps.map((_, i) => `<span class="busy-step ${i === 0 ? "active" : ""}"></span>`).join("")}</div>`
    : "";
  overlayRoot.innerHTML = `
    <div class="busy-overlay" role="alertdialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="busy-card">
        <div class="busy-visual">
          <span class="ring"></span>
          ${icon("scan")}
        </div>
        <h3>${esc(title)}</h3>
        <p id="busy-subtitle">${esc(subtitle || steps[0] || "请稍候")}</p>
        ${dots}
      </div>
    </div>`;
  syncBodyLock();
  clearInterval(busyStepTimer);
  if (steps.length > 1) {
    busyStepTimer = window.setInterval(() => {
      index = (index + 1) % steps.length;
      const subtitle = $("#busy-subtitle");
      if (subtitle) subtitle.textContent = steps[index];
      $$(".busy-step").forEach((dot, i) => {
        dot.classList.toggle("active", i === index);
        dot.classList.toggle("done", i < index);
      });
    }, 1700);
  }
}

function hideBusy() {
  state.busy = false;
  clearInterval(busyStepTimer);
  busyStepTimer = null;
  if ($(".busy-overlay")) overlayRoot.innerHTML = "";
  syncBodyLock();
}

function openModal(html, { className = "", onClose = null } = {}) {
  state.lastFocus = document.activeElement;
  state.modalOpen = true;
  state.modalOnClose = onClose;
  overlayRoot.innerHTML = `
    <div class="overlay" role="presentation">
      <div class="modal ${className}" role="dialog" aria-modal="true">
        ${html}
      </div>
    </div>`;
  syncBodyLock();
  window.setTimeout(() => {
    const target = $(".modal [data-autofocus]") || $(".modal button, .modal input, .modal textarea");
    target?.focus?.();
  }, 30);
}

function closeModal({ runCallback = true } = {}) {
  if (!state.modalOpen) return;
  state.modalOpen = false;
  overlayRoot.innerHTML = "";
  const callback = runCallback ? state.modalOnClose : null;
  state.modalOnClose = null;
  state.confirmCallback = null;
  state.lastFocus?.focus?.();
  state.lastFocus = null;
  syncBodyLock();
  if (typeof callback === "function") callback();
}

function modalHeader({ eyebrow = "", title = "", description = "", wide = false } = {}) {
  return `
    <div class="modal-head">
      <div>
        ${eyebrow ? `<div class="modal-eyebrow">${esc(eyebrow)}</div>` : ""}
        <h2>${esc(title)}</h2>
        ${description ? `<p>${esc(description)}</p>` : ""}
      </div>
      <button class="modal-close" data-action="close-modal" aria-label="关闭">${icon("x")}</button>
    </div>`;
}

function openConfirm({ title = "确认操作", message = "", confirmLabel = "确认", danger = false, onConfirm = null }) {
  state.confirmCallback = onConfirm;
  openModal(
    `${modalHeader({ eyebrow: "PLEASE CONFIRM", title, description: "" })}
     <p class="confirm-copy">${message}</p>
     <div class="modal-actions">
       <div class="spacer"></div>
       <button class="btn ghost" data-action="close-modal">取消</button>
       <button class="btn ${danger ? "coral" : "primary"}" data-action="confirm-modal" data-autofocus>${esc(confirmLabel)}</button>
     </div>`,
    { className: "narrow" },
  );
}

function openErrorModal(title, message, { retryAction = "", retryLabel = "重试" } = {}) {
  openModal(
    `${modalHeader({ eyebrow: "SOMETHING WENT WRONG", title, description: "" })}
     <p class="confirm-copy">${esc(message)}</p>
     <div class="modal-actions">
       <button class="btn ghost" data-action="close-modal">关闭</button>
       <button class="btn" data-action="go-settings">打开设置</button>
       ${retryAction ? `<button class="btn primary" data-action="${esc(retryAction)}" data-force="1" data-autofocus>${esc(retryLabel)}</button>` : `<button class="btn primary" data-action="close-modal" data-autofocus>知道了</button>`}
     </div>`,
    { className: "narrow" },
  );
}

function syncBodyLock() {
  const locked = Boolean(state.busy || state.modalOpen || state.drawer?.open);
  document.body.classList.toggle("no-scroll", locked);
}

function trapFocus(event) {
  const container = $(".modal") || $(".word-drawer");
  if (!container) return;
  const focusables = $$(
    'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    container,
  ).filter((el) => el.offsetParent !== null);
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/* --------------------------------------------------------------------------
   Reading persistence and boot
   -------------------------------------------------------------------------- */
function persistReading() {
  if (!state.reading) {
    localStorage.removeItem(READING_KEY);
    return;
  }
  const reading = state.reading;
  const analysis = { ...reading.analysis };
  delete analysis.raw_text;
  const payload = {
    version: 1,
    savedAt: Date.now(),
    analysis,
    ai: reading.ai || null,
    rawText: reading.rawText,
    titleOverride: reading.titleOverride || "",
    previewUrl: reading.previewUrl && !reading.previewUrl.startsWith("data:") ? reading.previewUrl : "",
    originalName: reading.originalName || "",
    userAnswers: reading.userAnswers || {},
    reveal: reading.reveal || {},
    translationOn: Boolean(reading.translationOn),
    activeRailTab: reading.activeRailTab || "vocab",
  };
  try {
    localStorage.setItem(READING_KEY, JSON.stringify(payload));
  } catch {
    // AI notes can be large; keep the reading and drop the optional AI payload.
    payload.ai = null;
    payload.previewUrl = "";
    try {
      localStorage.setItem(READING_KEY, JSON.stringify(payload));
      if (!state.storageWarned) {
        state.storageWarned = true;
        toast("AI 讲解较大，已仅保存原文与题目；刷新后 AI 内容需要重新生成。", "error", 5000);
      }
    } catch {
      if (!state.storageWarned) {
        state.storageWarned = true;
        toast("当前文章较长，浏览器无法暂存；刷新页面后可能丢失。", "error", 4500);
      }
    }
  }
}

function restoreReading() {
  try {
    const raw = localStorage.getItem(READING_KEY);
    if (!raw) return null;
    const payload = JSON.parse(raw);
    if (!payload?.analysis?.paragraphs) return null;
    return {
      analysis: payload.analysis,
      ai: payload.ai || null,
      rawText: payload.rawText || payload.analysis.raw_text || "",
      titleOverride: payload.titleOverride || "",
      previewUrl: payload.previewUrl || "",
      originalName: payload.originalName || "",
      userAnswers: payload.userAnswers || {},
      reveal: payload.reveal || {},
      translationOn: Boolean(payload.translationOn),
      activeRailTab: payload.activeRailTab || "vocab",
      savedAt: payload.savedAt || Date.now(),
    };
  } catch {
    return null;
  }
}

function makeReading({ analysis, rawText, titleOverride = "", previewUrl = "", originalName = "" }) {
  return {
    analysis,
    ai: null,
    rawText: rawText || analysis?.raw_text || "",
    titleOverride,
    previewUrl,
    originalName,
    userAnswers: {},
    reveal: {},
    translationOn: false,
    activeRailTab: "vocab",
    savedAt: Date.now(),
  };
}

async function boot() {
  bindGlobalEvents();
  applyReadingSize(getReadingSize());
  try {
    const [bootData, book] = await Promise.all([api.bootstrap(), api.wordbook()]);
    state.boot = bootData;
    state.wordbook = {
      items: book?.items || [],
      stats: book?.stats || { total: 0, learning: 0, mastered: 0 },
    };
    state.reading = restoreReading();
    state.studioMode = state.reading ? "reader" : "landing";
    state.page = getPageFromHash();
    if (state.page === "studio") state.studioMode = state.reading ? "reader" : "landing";
    loadVoices();
    render();
  } catch (error) {
    renderFatal(error);
  }
}

function renderFatal(error) {
  const pwa = Boolean(window.__LEXIREAD_PWA__);
  viewEl.innerHTML = `
    <section class="empty-state" style="margin-top:40px">
      <div class="empty-visual">${icon("alert")}</div>
      <h3>${pwa ? "应用没有启动" : "本地服务没有响应"}</h3>
      <p>${esc(error?.message || (pwa ? "请刷新页面重试。" : "请确认启动窗口仍在运行，然后刷新页面。"))}</p>
      <button class="btn primary" data-action="reload-page">${icon("refresh")}刷新页面</button>
    </section>`;
}

function render() {
  state.page = getPageFromHash();
  updateShell();
  if (!state.boot) return;
  if (state.page === "studio") {
    viewEl.innerHTML = state.reading && state.studioMode === "reader" ? renderReader() : renderLanding();
    applyReadingSize(getReadingSize());
    syncTranslationState();
  } else if (state.page === "wordbook") {
    viewEl.innerHTML = renderWordbook();
  } else {
    if (!state.settingsDraft) state.settingsDraft = buildSettingsDraft();
    viewEl.innerHTML = renderSettings();
  }
}

function updateShell() {
  const meta = PAGE_META[state.page] || PAGE_META.studio;
  $("#topbar-kicker").textContent = meta.kicker;
  $("#topbar-page").textContent = meta.label;
  document.title =
    state.page === "wordbook" ? "生词本 · LexiRead" : state.page === "settings" ? "设置 · LexiRead" : state.reading ? `${state.reading.analysis.title} · LexiRead` : "LexiRead · 精读工坊";

  $$(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.nav === state.page);
  });

  const count = state.wordbook?.stats?.total || state.wordbook?.items?.length || 0;
  const badge = $("#nav-wordbook-count");
  if (badge) {
    badge.textContent = String(count);
    badge.hidden = count === 0;
  }

  const configured = Boolean(state.boot?.ai_status?.configured);
  const pill = $("#ai-pill");
  if (pill) {
    pill.classList.toggle("connected", configured);
    $("#ai-pill-label").textContent = configured ? "AI 已配置" : "AI 未配置";
    pill.title = configured
      ? `已配置 ${state.boot.ai_status.model}，点击管理`
      : "点击配置 AI，解锁翻译与答案解析";
  }
}

function navigate(page) {
  if (!PAGE_META[page]) page = "studio";
  if (location.hash !== `#${page}`) {
    location.hash = page;
  } else {
    handleRouteChange();
  }
}

function handleRouteChange() {
  closeModal();
  closeDrawer();
  state.page = getPageFromHash();
  if (state.page === "studio") {
    state.studioMode = state.reading ? "reader" : "landing";
  }
  if (state.page === "settings") state.settingsDraft = null;
  render();
  window.scrollTo({ top: 0, behavior: "auto" });
}

/* --------------------------------------------------------------------------
   Core reading actions
   -------------------------------------------------------------------------- */
async function analyzeText(text, { title = "", previewUrl = "", originalName = "", sampleLabel = "" } = {}) {
  const value = String(text || "").trim();
  if (!value) {
    toast("请先粘贴或识别一些英文题目。", "error");
    return;
  }
  setBusy({
    title: "正在整理这篇精读",
    steps: ["拆分文章与题目", "提取词汇、短语与重点句", "排版阅读页"],
  });
  try {
    const analysis = await api.analyze(value, title);
    state.reading = makeReading({ analysis, rawText: value, titleOverride: title, previewUrl, originalName });
    state.studioMode = "reader";
    state.page = "studio";
    if (location.hash !== "#studio") {
      history.replaceState(null, "", "#studio");
    }
    persistReading();
    hideBusy();
    render();
    window.scrollTo({ top: 0, behavior: "auto" });
    const questions = analysis?.questions?.length || 0;
    toast(questions ? `已拆出 ${questions} 道题，点击文中单词即可学习。` : sampleLabel ? "示例已载入，点击文中单词开始精读。" : "精读页已生成。", "success");
  } catch (error) {
    hideBusy();
    openErrorModal("这篇内容暂时没整理好", error?.message || "请检查文本后重试。");
  }
}

async function loadSample(sampleId) {
  setBusy({
    title: "正在载入示例",
    steps: ["准备原题", "拆解文章结构", "生成学习卡"],
  });
  try {
    const sample = await api.sample(sampleId);
    await analyzeText(sample.text, { sampleLabel: sample.label });
  } catch (error) {
    hideBusy();
    openErrorModal("示例载入失败", error?.message || "请稍后再试。");
  }
}

async function handleFile(file) {
  if (!file) return;
  const looksImage = /^image\//i.test(file.type) || /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(file.name || "");
  if (!looksImage) {
    toast("请选择 PNG、JPG、WebP 等图片文件。", "error");
    return;
  }
  if (file.size > 30 * 1024 * 1024) {
    toast("图片超过 30MB，请压缩后再试。", "error");
    return;
  }
  setBusy({
    title: "正在识别题目图片",
    steps: ["增强图片清晰度", "识别题目文字", "整理段落与换行"],
  });
  try {
    const result = await api.uploadOcr(file);
    hideBusy();
    state.ocrDraft = result;
    openOcrReview(result);
  } catch (error) {
    hideBusy();
    openErrorModal("图片识别没有完成", error?.message || "请换一张更清晰的图片。", {
      retryAction: "choose-file",
      retryLabel: "换一张图片",
    });
  }
}

function openOcrReview(result) {
  const preview = result.preview_url
    ? `<div class="ocr-image-panel">
         <span class="ocr-image-badge">ORIGINAL</span>
         <img src="${esc(result.preview_url)}" alt="题目原图">
       </div>`
    : "";
  const meta = result.meta || {};
  const warning = meta.warning
    ? `<div class="ocr-warning">${icon("alert")}<span>${esc(meta.warning)}</span></div>`
    : "";
  openModal(
    `${modalHeader({
      eyebrow: "OCR REVIEW",
      title: "识别完成，先快速校对",
      description: "识别结果可以直接修改。确认无误后进入精读，所有单词都会变成可点击的学习入口。",
    })}
     <div class="ocr-review">
       ${preview || `<div class="ocr-image-panel" style="align-items:center;color:var(--faint);font-size:11px">图片预览不可用</div>`}
       <div class="ocr-text-panel">
         <div class="ocr-text-top">
           <span>识别文字 · 可直接编辑</span>
           <span>${esc(meta.engine || "Windows OCR")} · ${meta.duration_ms ? `${(meta.duration_ms / 1000).toFixed(1)}s` : "本机处理"}</span>
         </div>
         ${warning}
         <textarea class="ocr-textarea" id="ocr-text" spellcheck="false">${esc(result.text || "")}</textarea>
         <div class="upload-foot" style="justify-content:flex-start;margin-top:0">
           ${icon("shield")}${meta.ai_vision
             ? "图片已发送给你配置的 AI 模型识别；识别结果只在本机排版。"
             : "图片只在本机识别；查词会联网获取释义，只有点击“AI 精讲”后题目文本才会发送给你配置的模型。"}
         </div>
       </div>
     </div>
     <div class="modal-actions">
       <button class="btn ghost" data-action="close-modal">取消</button>
       <button class="btn" data-action="retry-image">重新选择图片</button>
       <button class="btn primary" data-action="start-ocr-analysis" data-autofocus>${icon("arrow-right")}进入精读</button>
     </div>`,
    { className: "wide", onClose: () => { state.ocrDraft = null; } },
  );
}

function openEditModal() {
  if (!state.reading) return;
  openModal(
    `${modalHeader({
      eyebrow: "EDIT SOURCE",
      title: "编辑原文",
      description: "修正 OCR 错字或补充题目后，会重新拆分题目并清空本篇的 AI 讲解。",
    })}
     <div class="field-title">
       <label for="edit-title">文章标题 <span style="color:var(--faint)">（可留空自动识别）</span></label>
       <input class="input" id="edit-title" value="${esc(state.reading.titleOverride || "")}" placeholder="${esc(state.reading.analysis.title || "文章标题")}">
     </div>
     <div class="field-title" style="margin-bottom:0">
       <label for="edit-source">原文文本</label>
       <textarea class="edit-textarea" id="edit-source" spellcheck="false">${esc(state.reading.rawText || "")}</textarea>
     </div>
     <div class="modal-actions">
       <span class="form-note" style="margin:0">${icon("info")} 生词本不会受影响</span>
       <div class="spacer"></div>
       <button class="btn ghost" data-action="close-modal">取消</button>
       <button class="btn primary" data-action="save-edit">${icon("refresh")}重新精读</button>
     </div>`,
    { className: "wide" },
  );
}

async function runAI(force = false) {
  if (!state.reading) {
    toast("请先载入一篇题目。", "error");
    return;
  }
  if (!state.boot?.ai_status?.configured) {
    openAIRequiredModal();
    return;
  }
  if (state.modalOpen) {
    closeModal({ runCallback: false });
  }
  if (state.reading.ai && !force) {
    openConfirm({
      title: "重新生成 AI 讲解？",
      message: "本篇已有 AI 讲解。重新生成会再次调用模型，并可能覆盖当前的译文与解析。",
      confirmLabel: "重新生成",
      onConfirm: () => runAI(true),
    });
    return;
  }
  setBusy({
    title: "AI 正在精读这篇文章",
    steps: ["通读全文，定位题目依据", "生成译文与答案解析", "整理词汇、长难句与语法"],
  });
  try {
    const result = await api.aiAnalyze(state.reading.rawText, state.reading.titleOverride || "", force);
    state.reading.ai = result;
    state.reading.reveal = {};
    persistReading();
    hideBusy();
    render();
    toast("AI 精讲已生成：参考答案、译文和语法卡都在页面里了。", "success", 4200);
  } catch (error) {
    hideBusy();
    openErrorModal("AI 讲解没有完成", error?.message || "请稍后重试。", {
      retryAction: "run-ai",
      retryLabel: force ? "重新尝试" : "再试一次",
    });
  }
}

function openAIRequiredModal() {
  openModal(
    `${modalHeader({
      eyebrow: "AI STUDY COMPANION",
      title: "连接一个 AI，让精读更完整",
      description: "本地 OCR、词典和生词本不需要 AI。连接后，还可以生成参考译文、答案依据、长难句拆解和语法讲解。",
    })}
     <ul class="result-list">
       <li>支持 DeepSeek、OpenAI、通义千问、智谱以及本地 Ollama。</li>
       <li>只需要兼容 OpenAI 的 Base URL、模型名和 API Key。</li>
       <li>只有你主动点击“AI 精讲”时，文章文本才会发送给模型。</li>
     </ul>
     <div class="modal-actions">
       <button class="btn ghost" data-action="close-modal">先用本地功能</button>
       <button class="btn primary" data-action="go-settings">${icon("settings")}去连接 AI</button>
     </div>`,
    { className: "narrow" },
  );
}

function toggleTranslation() {
  if (!state.reading) return;
  const translation = state.reading.ai?.translation || [];
  if (!translation.length) {
    toast("运行 AI 精讲后才能生成参考译文。", "info");
    return;
  }
  state.reading.translationOn = !state.reading.translationOn;
  persistReading();
  syncTranslationState();
}

function syncTranslationState() {
  const reading = state.reading;
  if (!reading) return;
  const article = $("#article-body");
  if (article) article.classList.toggle("show-translations", Boolean(reading.translationOn));
  const only = $("#translation-only");
  if (only) only.classList.toggle("show", Boolean(reading.translationOn && !translationByParagraph()));
  $$('[data-action="toggle-translation"]').forEach((button) => {
    button.classList.toggle("active", Boolean(reading.translationOn));
    button.setAttribute("aria-pressed", reading.translationOn ? "true" : "false");
  });
}

function translationByParagraph() {
  const reading = state.reading;
  const paragraphs = reading?.analysis?.paragraphs || [];
  const translation = reading?.ai?.translation || [];
  return translation.length === paragraphs.length && paragraphs.length > 0;
}

function selectOption(questionNumber, label) {
  if (!state.reading) return;
  state.reading.userAnswers[questionNumber] = label;
  persistReading();
  const card = $(`.question-card[data-question="${questionNumber}"]`);
  if (card) card.outerHTML = renderQuestionCard(questionByNumber(questionNumber));
  updateProgressRail();
}

function toggleReveal(questionNumber, force = null) {
  if (!state.reading) return;
  const current = Boolean(state.reading.reveal?.[questionNumber]);
  const next = force === null ? !current : Boolean(force);
  state.reading.reveal[questionNumber] = next;
  persistReading();
  const card = $(`.question-card[data-question="${questionNumber}"]`);
  if (card) card.outerHTML = renderQuestionCard(questionByNumber(questionNumber));
}

function questionByNumber(number) {
  return (state.reading?.analysis?.questions || []).find((question) => Number(question.number) === Number(number));
}

function updateProgressRail() {
  const host = $("#progress-card-host");
  if (host) host.innerHTML = renderProgressCard();
}

/* --------------------------------------------------------------------------
   Wordbook actions
   -------------------------------------------------------------------------- */
async function saveCurrentWord() {
  const drawer = state.drawer;
  if (!drawer?.entry) {
    toast("词条还没有加载完成。", "error");
    return;
  }
  const existing = savedMap().get(wordKey(drawer.word));
  if (existing) {
    toast("这个词已经在生词本里了。");
    return;
  }
  const button = $('[data-action="save-current-word"]');
  button?.classList.add("loading");
  try {
    const response = await api.addWord(
      drawer.entry.word || drawer.word,
      drawer.entry,
      drawer.context || "",
      drawer.sourceTitle || "",
    );
    const item = response?.item;
    if (item) {
      state.wordbook.items = [item, ...state.wordbook.items.filter((entry) => entry.id !== item.id)];
    }
    state.wordbook.stats = response?.stats || state.wordbook.stats;
    if (state.drawer) state.drawer.savedId = item?.id || null;
    persistReading();
    updateShell();
    markSavedTokens(drawer.word, true);
    renderDrawer();
    toast("已收进生词本，之后可以随时复习。", "success");
    if (state.page === "wordbook") render();
  } catch (error) {
    toast(error?.message || "收藏失败。", "error");
  } finally {
    button?.classList.remove("loading");
  }
}

async function removeSavedWordById(id, { silent = false } = {}) {
  try {
    const response = await api.deleteWord(id);
    state.wordbook.items = state.wordbook.items.filter((item) => item.id !== id);
    state.wordbook.stats = response?.stats || state.wordbook.stats;
    if (state.drawer?.savedId === id) state.drawer.savedId = null;
    updateShell();
    if (state.drawer?.open) renderDrawer();
    if (state.page === "wordbook") render();
    if (!silent) toast("已从生词本移除。");
    return true;
  } catch (error) {
    toast(error?.message || "移除失败。", "error");
    return false;
  }
}

async function toggleMasteredById(id) {
  const item = state.wordbook.items.find((entry) => entry.id === id);
  if (!item) return;
  const next = item.status === "mastered" ? "learning" : "mastered";
  try {
    const response = await api.updateWord(id, { status: next });
    if (response?.item) {
      state.wordbook.items = state.wordbook.items.map((entry) => (entry.id === id ? response.item : entry));
    }
    state.wordbook.stats = response?.stats || state.wordbook.stats;
    updateShell();
    if (state.page === "wordbook") render();
    if (state.drawer?.open) renderDrawer();
    if (state.review) renderReviewModal();
    toast(next === "mastered" ? "标记为已掌握。真棒。" : "已移回“学习中”。", "success");
  } catch (error) {
    toast(error?.message || "更新失败。", "error");
  }
}

function markSavedTokens(word, saved) {
  const key = wordKey(word);
  $$(".word-token").forEach((token) => {
    if (wordKey(token.dataset.word) === key) token.classList.toggle("is-saved", saved);
  });
}

/* --------------------------------------------------------------------------
   Word drawer
   -------------------------------------------------------------------------- */
async function openWord(rawWord, context = "", sourceTitle = "") {
  const word = String(rawWord || "").trim();
  if (!word) return;
  const existing = savedMap().get(wordKey(word));
  state.drawer = {
    open: true,
    word: existing?.word || word,
    lookup: normalizeLookup(existing?.word || word),
    context: context || existing?.source || "",
    sourceTitle: sourceTitle || existing?.source_title || "",
    entry: existing?.data || null,
    savedId: existing?.id || null,
    loading: !existing?.data,
    error: "",
  };
  state.lastFocus = document.activeElement;
  renderDrawer();
  syncBodyLock();
  window.setTimeout(() => drawerRoot.querySelector(".drawer-top button")?.focus(), 20);
  if (!existing?.data) await fetchDrawerWord();
}

function focusDrawer() {
  window.setTimeout(() => {
    if (state.drawer?.open) drawerRoot.querySelector(".drawer-top button")?.focus();
  }, 20);
}

async function fetchDrawerWord(force = false) {
  const drawer = state.drawer;
  if (!drawer) return;
  drawer.loading = true;
  drawer.error = "";
  renderDrawer();
  try {
    const entry = await api.word(drawer.lookup || drawer.word, force);
    if (!state.drawer) return;
    state.drawer.entry = entry;
    state.drawer.word = entry.word || state.drawer.word;
    state.drawer.loading = false;
    renderDrawer();
    focusDrawer();
  } catch (error) {
    if (!state.drawer) return;
    state.drawer.loading = false;
    state.drawer.error = error?.message || "查词失败，请稍后再试。";
    renderDrawer();
    focusDrawer();
  }
}

function closeDrawer() {
  if (!state.drawer?.open) return;
  state.drawer = null;
  drawerRoot.innerHTML = "";
  state.lastFocus?.focus?.();
  state.lastFocus = null;
  syncBodyLock();
}

function playDrawerAudio(accent) {
  const entry = state.drawer?.entry;
  if (!entry) return;
  const button = $(`[data-action="play-word"][data-accent="${accent}"]`);
  const url = entry.audio?.[accent] || entry.audio?.us || entry.audio?.uk || "";
  playAudio(url, entry.word || state.drawer.word, button);
}

function playDrawerExample(index) {
  const example = state.drawer?.entry?.examples?.[Number(index)];
  if (!example) return;
  const button = $(`[data-action="play-example"][data-index="${index}"]`);
  playAudio(example.audio || "", example.en, button);
}

/* --------------------------------------------------------------------------
   Settings actions
   -------------------------------------------------------------------------- */
function buildSettingsDraft() {
  const settings = deepClone(state.boot?.settings || {});
  const ai = settings.ai || {};
  const learning = settings.learning || {};
  const ocr = settings.ocr || {};
  return {
    ai: {
      provider: ai.provider || "deepseek",
      base_url: ai.base_url || "",
      model: ai.model || "",
      temperature: ai.temperature ?? 0.2,
      api_key: "",
    },
    learning: {
      exam: learning.exam || "CET-4",
      accent: learning.accent || "us",
      voice_rate: Number(learning.voice_rate ?? 1),
    },
    ocr: {
      ai_vision: Boolean(ocr.ai_vision),
    },
    keySet: Boolean(ai.api_key_set),
    clearKey: false,
  };
}

function settingsPathSet(path, value) {
  if (!state.settingsDraft) return;
  const [section, key] = path.split(".");
  if (!state.settingsDraft[section]) return;
  state.settingsDraft[section][key] = value;
}

async function persistSettings({ silent = false, target = "ai-form-status", rerender = true } = {}) {
  const draft = state.settingsDraft || buildSettingsDraft();
  const ai = {
    provider: draft.ai.provider,
    base_url: draft.ai.base_url.trim(),
    model: draft.ai.model.trim(),
    temperature: draft.ai.temperature,
  };
  if (draft.ai.api_key) ai.api_key = draft.ai.api_key.trim();
  else if (draft.clearKey) ai.api_key = "";
  const patch = {
    ai,
    learning: {
      exam: draft.learning.exam,
      accent: draft.learning.accent,
      voice_rate: Number(draft.learning.voice_rate),
    },
    ocr: {
      ai_vision: Boolean(draft.ocr?.ai_vision),
    },
  };
  const data = await api.saveSettings(patch);
  state.boot.settings = data.settings;
  state.boot.ai_status = data.ai_status;
  state.settingsDraft = buildSettingsDraft();
  updateShell();
  if (!silent) {
    if (rerender) render();
    showFormStatus("设置已保存。", "ok", target);
    toast("设置已保存。", "success");
  }
  return data;
}

function showFormStatus(message, type = "ok", targetId = "ai-form-status") {
  const status = document.getElementById(targetId) || $("#ai-form-status") || $("#settings-form-status");
  if (!status) {
    if (message) toast(message, type === "ok" ? "success" : "error");
    return;
  }
  status.textContent = message;
  status.className = `form-status show ${type}`;
}

/* --------------------------------------------------------------------------
   Review mode
   -------------------------------------------------------------------------- */
function startReview(items = null) {
  const source = items || state.wordbook.items;
  if (!source.length) {
    toast("生词本还是空的，先去精读页收藏几个词吧。", "error");
    return;
  }
  state.review = { items: shuffle(source), index: 0, revealed: false, mastered: 0, learning: 0 };
  renderReviewModal();
}

function advanceReview(status) {
  if (!state.review) return;
  const item = state.review.items[state.review.index];
  if (status === "mastered") state.review.mastered += 1;
  else state.review.learning += 1;
  if (item) {
    const nextStatus = status === "mastered" ? "mastered" : "learning";
    api.updateWord(item.id, { status: nextStatus }).then((response) => {
      if (response?.item) {
        state.wordbook.items = state.wordbook.items.map((entry) => (entry.id === item.id ? response.item : entry));
      }
      state.wordbook.stats = response?.stats || state.wordbook.stats;
      updateShell();
    }).catch(() => {});
  }
  state.review.index += 1;
  state.review.revealed = false;
  renderReviewModal();
}

function reviewMeaning(item) {
  return wordMeaning(item?.data) || "这个词还没有释义。";
}

/* --------------------------------------------------------------------------
   Token rendering
   -------------------------------------------------------------------------- */
function tokenizeHTML(text, { focus = null, saved = null } = {}) {
  const source = String(text || "");
  const focusSet = focus || focusWordSet();
  const savedSet = saved || savedWordSet();
  const pattern = /(_{2,}\s*\d{0,2}\s*_{2,}|_{2,}|…{2,})|([A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*)/g;
  let html = "";
  let last = 0;
  for (const match of source.matchAll(pattern)) {
    if (match.index > last) html += esc(source.slice(last, match.index));
    if (match[1]) {
      const number = (match[1].match(/\d{1,2}/) || [])[0] || "";
      html += `<span class="blank-chip" role="img" aria-label="空格${number ? ` ${number}` : ""}"><span class="blank-stroke"></span>${number ? `<sup>${esc(number)}</sup>` : ""}</span>`;
    } else if (match[2]) {
      const display = match[2];
      const lookup = normalizeLookup(display);
      if (!lookup) {
        html += esc(display);
      } else {
        const key = lookup.toLowerCase();
        const isFocus = focusSet.has(key);
        const isSaved = savedSet.has(key);
        const classes = [
          "word-token",
          isFocus ? "is-focus" : "",
          isSaved ? "is-saved" : "",
        ].filter(Boolean).join(" ");
        html += `<span class="${classes}" role="button" tabindex="${isFocus || isSaved ? "0" : "-1"}" data-action="open-word" data-word="${esc(lookup)}" aria-label="查询单词 ${esc(display)}">${esc(display)}</span>`;
      }
    }
    last = match.index + match[0].length;
  }
  html += esc(source.slice(last));
  return html;
}

/* --------------------------------------------------------------------------
   Landing
   -------------------------------------------------------------------------- */
function renderLanding() {
  const samples = state.boot?.samples || [];
  const imageActive = state.uploadMode === "image";
  return `
    <div class="landing">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow">Read deeper · remember longer</div>
          <h1>把一张题图，<br><em>读成一堂课。</em></h1>
          <p class="hero-lead">上传英语阅读或完形填空的图片，自动识别并排成一张干净的阅读页。点任意单词听发音、看释义，把遇见的词收进自己的生词本。</p>
          <div class="hero-notes">
            <span class="hero-note">${icon("scan")}本机 OCR 识别</span>
            <span class="hero-note">${icon("feather")}点词即查</span>
            <span class="hero-note">${icon("sparkles")}AI 精讲</span>
            <span class="hero-note">${icon("bookmark")}生词收藏</span>
          </div>
          <p class="hero-footnote">${icon("shield")}图片默认只在本机识别；AI 视觉识别与 AI 精讲都由你主动开启。</p>
        </div>

        <div class="upload-card">
          <div class="upload-head">
            <div class="upload-title">新建精读</div>
            <div class="mode-tabs" role="tablist" aria-label="输入方式">
              <button class="mode-tab ${imageActive ? "active" : ""}" data-action="switch-mode" data-mode="image" role="tab" aria-selected="${imageActive}">图片识别</button>
              <button class="mode-tab ${!imageActive ? "active" : ""}" data-action="switch-mode" data-mode="paste" role="tab" aria-selected="${!imageActive}">粘贴文本</button>
            </div>
          </div>
          <div class="upload-body">
            <div class="dropzone ${imageActive ? "" : "hidden"}" data-action="choose-file">
              <div class="scan-visual">
                <span class="scan-frame">${icon("scan")}</span>
                <span class="scan-paper"><i></i><i></i><i></i></span>
                <span class="scan-spark">${icon("sparkles")}</span>
              </div>
              <h3>把题目图片拖到这里</h3>
              <p>支持阅读、完形、语法填空等题型。识别后可以先校对文字，再进入精读。</p>
              <button class="btn primary" data-action="choose-file">${icon("upload")}选择图片</button>
              <div class="upload-or">或将截图直接拖入</div>
              <input type="file" id="file-input" accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff" hidden>
            </div>
            <div class="paste-panel ${imageActive ? "hidden" : ""}">
              <div class="paste-label"><span>粘贴文章、题目与选项</span><span>Ctrl / ⌘ + Enter 开始</span></div>
              <textarea class="paste-area" id="paste-input" spellcheck="false" placeholder="Paste the passage, questions and choices here…

Example:
Many students find it difficult to remember new words.
The best way is to read every day and take notes.

1. What is the best way to learn?
A. To avoid new words.
B. To read and take notes.
...">${esc(state.pasteText)}</textarea>
              <button class="btn primary" data-action="submit-paste">${icon("arrow-right")}开始精读</button>
            </div>
          </div>
          <div class="upload-foot">${icon("shield")}本地识别 · 查词联网 · 文本仅在 AI 精讲时发送</div>
        </div>
      </section>

      <section class="steps">
        <div class="rule-label">How it works / 精读三步</div>
        <div class="steps-grid">
          <div class="step">
            <span class="step-num">01</span>
            <div><h4>识别与校对</h4><p>本机 OCR 读取题目图片，自动整理换行与段落。识别错了，可以直接改。</p></div>
          </div>
          <div class="step">
            <span class="step-num">02</span>
            <div><h4>精读与点词</h4><p>文章按试卷质感排版。鼠标点任意单词，看音标、释义、例句和搭配。</p></div>
          </div>
          <div class="step">
            <span class="step-num">03</span>
            <div><h4>做题与积累</h4><p>先完成题目，再用 AI 核对答案依据。把值得记的词收进生词本。</p></div>
          </div>
        </div>
      </section>

      <section class="samples-block">
        <div class="samples-head">
          <div>
            <div class="rule-label">Sample library</div>
            <h2>还没有题？先从一篇开始。</h2>
          </div>
          <p>内置原创示例，可直接体验完整流程</p>
        </div>
        <div class="samples-grid">
          ${samples.map((sample, index) => renderSampleCard(sample, index)).join("")}
        </div>
      </section>
    </div>`;
}

function renderSampleCard(sample, index) {
  const kindLetter = sample.kind === "完形" ? "C" : "R";
  const numberLabel = `No. ${String(index + 1).padStart(2, "0")}`;
  return `
    <button class="sample-card" data-action="use-sample" data-id="${esc(sample.id)}">
      <span class="sample-cover">
        <small>${numberLabel}</small>
        <strong>${kindLetter}</strong>
        <span>${esc(sample.kind)} · PRACTICE</span>
      </span>
      <span class="sample-info">
        <span class="sample-kind">${esc(sample.label)}</span>
        <h3>${esc(sample.title)}</h3>
        <p>${esc(sample.subtitle)} · 点击载入</p>
      </span>
      <span class="sample-arrow">${icon("arrow-right")}</span>
    </button>`;
}

/* --------------------------------------------------------------------------
   Reader
   -------------------------------------------------------------------------- */
function renderReader() {
  const reading = state.reading;
  const analysis = reading.analysis;
  const ai = reading.ai;
  const questions = analysis.questions || [];
  const kindLabel = analysis.kind === "cloze" ? "CLOZE" : analysis.kind === "reading" ? "READING" : "TEXT";
  const difficulty = analysis.stats?.difficulty?.label || "本地精读";
  const wordCount = analysis.stats?.word_count || 0;
  const minutes = analysis.stats?.reading_minutes || 1;
  const focus = focusWordSet();
  const saved = savedWordSet();
  const paragraphs = analysis.paragraphs || [];
  const translations = ai?.translation || [];
  const perParagraph = translations.length === paragraphs.length && paragraphs.length > 0;
  const instructions = (analysis.instructions || []).filter(Boolean);
  const hasTranslation = translations.length > 0;

  const paragraphHtml = paragraphs.map((paragraph, index) => {
    const translation = perParagraph ? translations[index] : "";
    return `
      <p class="para" data-para="${index + 1}">
        <span class="para-index">${String(index + 1).padStart(2, "0")}</span>${tokenizeHTML(paragraph.text, { focus, saved })}
      </p>
      ${translation ? `<aside class="para-translation">${esc(translation)}</aside>` : ""}`;
  }).join("");

  const translationOnly = !perParagraph && translations.length
    ? `<div class="translation-only ${reading.translationOn ? "show" : ""}" id="translation-only">
         <h3>参考译文</h3>
         ${translations.map((text) => `<p class="translation-paragraph">${esc(text)}</p>`).join("")}
       </div>`
    : "";

  const questionsHtml = questions.length
    ? `<div class="questions-divider">
         <div class="q-divider-label">${icon("target")}Questions <span>题目</span></div>
         <div class="q-divider-line"></div>
         <span class="q-divider-count">${questions.length.toString().padStart(2, "0")} ITEMS</span>
       </div>
       <div class="question-list">${questions.map((question) => renderQuestionCard(question)).join("")}</div>`
    : "";

  return `
    <section class="reader-head">
      <div class="reader-head-left">
        <button class="text-link" data-action="new-reading">${icon("plus")}新的精读</button>
        <span class="reader-divider"></span>
        <span class="reader-state"><span class="pulse-dot"></span>精读模式 · ${esc(kindLabel)}</span>
      </div>
      <div class="reader-head-actions">
        ${reading.previewUrl ? `<button class="btn ghost" data-action="view-image">${icon("image")}查看原图</button>` : ""}
        <button class="btn ghost" data-action="edit-text">${icon("edit")}编辑原文</button>
        <button class="btn ${ai ? "" : "primary"}" data-action="run-ai">${icon("sparkles")}${ai ? "重新精讲" : "AI 精讲"}</button>
      </div>
    </section>

    <div class="reader-layout">
      <main class="reader-main">
        <article class="paper">
          <div class="paper-top">
            <div class="paper-kicker">${esc(kindLabel)} · PASSAGE</div>
            <div class="paper-tools">
              <button class="paper-tool font-tool" data-action="font-minus" title="减小字号" aria-label="减小字号">A−</button>
              <button class="paper-tool font-tool" data-action="font-plus" title="增大字号" aria-label="增大字号">A+</button>
              <button class="paper-tool ${reading.translationOn ? "active" : ""}" data-action="toggle-translation" title="${hasTranslation ? "对照参考译文" : "运行 AI 精讲后可查看译文"}" aria-pressed="${reading.translationOn ? "true" : "false"}">${icon("book")}<span>译文</span></button>
            </div>
          </div>
          <h1 class="paper-title">${esc(analysis.title)}</h1>
          ${ai?.title_zh ? `<p class="paper-title-zh">${esc(ai.title_zh)}</p>` : ""}
          <div class="paper-meta">
            <span class="meta-level">${esc(difficulty)}</span>
            <span>${icon("file-text")}${wordCount} 词</span>
            <span>${icon("clock")}约 ${minutes} 分钟</span>
            ${questions.length ? `<span>${icon("target")}${questions.length} 题</span>` : ""}
            ${ai?.level ? `<span class="chip green" style="height:20px">AI · ${esc(ai.level)}</span>` : ""}
          </div>
          ${instructions.length ? `<div class="paper-instructions">${instructions.map((line) => `<p>${esc(line)}</p>`).join("")}</div>` : ""}
          <div class="article-body ${reading.translationOn ? "show-translations" : ""}" id="article-body">${paragraphHtml}</div>
          ${translationOnly}
          <div class="paper-end">End of passage</div>
          ${questionsHtml}
        </article>
      </main>

      <aside class="study-rail" aria-label="学习卡">
        <div id="progress-card-host">${renderProgressCard()}</div>
        ${renderAIBrief()}
        <section class="rail-card">
          <div class="rail-head">
            <div class="rail-title">${icon("feather")}学习卡</div>
            <span class="rail-head-note">${ai ? "AI 精讲已加载" : "点击单词查看词条"}</span>
          </div>
          <div class="rail-tabs" role="tablist" aria-label="学习卡分类">
            ${renderRailTabs()}
          </div>
          <div class="rail-body">${renderRailBody()}</div>
        </section>
      </aside>
    </div>`;
}

function renderProgressCard() {
  const reading = state.reading;
  const questions = reading?.analysis?.questions || [];
  const total = questions.length;
  const answered = answeredCount();
  const percent = total ? Math.round((answered / total) * 100) : 0;
  const circumference = 2 * Math.PI * 17;
  const offset = circumference * (1 - percent / 100);
  return `
    <section class="progress-card">
      <div class="progress-top">
        <div>
          <div class="progress-label">答题进度</div>
          <div class="progress-count">${answered}<small> / ${total} 题</small></div>
        </div>
        <div class="progress-ring">
          <svg viewBox="0 0 42 42" aria-hidden="true">
            <circle class="ring-bg" cx="21" cy="21" r="17"></circle>
            <circle class="ring-fill" cx="21" cy="21" r="17" stroke-dasharray="${circumference.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}"></circle>
          </svg>
          <span>${percent}%</span>
        </div>
      </div>
      <div class="progress-bar"><span style="width:${percent}%"></span></div>
      <div class="progress-foot">
        <span>${total ? (answered === total ? "已完成作答，去核对依据" : "先独立作答，再核对答案") : "本篇没有检测到题目"}</span>
        ${total ? `<button class="progress-jump" data-action="scroll-questions">查看题目${icon("chevron-down")}</button>` : ""}
      </div>
    </section>`;
}

function renderAIBrief() {
  const ai = state.reading?.ai;
  const configured = Boolean(state.boot?.ai_status?.configured);
  if (ai?.summary_zh) {
    return `
      <section class="ai-summary">
        <div class="ai-summary-head">${icon("sparkles")}AI 速览 ${ai.level ? `<span class="chip green">${esc(ai.level)}</span>` : ""}</div>
        <p>${esc(ai.summary_zh)}</p>
        <div class="ai-summary-foot">
          <span>${esc(ai._meta?.model || state.boot?.ai_status?.model || "AI")}${ai._meta?.cached ? " · 已缓存" : ""}</span>
          <button data-action="run-ai">${icon("refresh")}重新生成</button>
        </div>
      </section>`;
  }
  if (configured) {
    return `
      <section class="ai-cta">
        <div class="ai-cta-head">${icon("sparkles")}AI 精讲已配置</div>
        <p>生成全文译文、每道题的答案依据，以及长难句与语法拆解。</p>
        <button class="btn primary small" data-action="run-ai">${icon("sparkles")}讲解这一篇</button>
      </section>`;
  }
  return `
    <section class="ai-cta">
      <div class="ai-cta-head">${icon("sparkles")}让 AI 做你的同桌</div>
      <p>连接模型后可用：参考译文 · 答案解析 · 原文依据 · 语法拆解。本地功能无需 AI。</p>
      <button class="btn small" data-action="go-settings">${icon("settings")}连接 AI</button>
    </section>`;
}

function renderRailTabs() {
  const active = state.reading?.activeRailTab || "vocab";
  const tabs = [
    { id: "vocab", label: "词汇", count: mergedVocabulary().length },
    { id: "phrases", label: "短语", count: mergedPhrases().length },
    { id: "keys", label: "长难句", count: effectiveKeySentences().length },
    { id: "grammar", label: "语法", count: state.reading?.ai?.grammar?.length || 0 },
  ];
  return tabs.map((tab) => `
    <button class="rail-tab ${active === tab.id ? "active" : ""}" role="tab" aria-selected="${active === tab.id}" data-action="rail-tab" data-tab="${tab.id}">
      <span>${tab.label}</span><span class="rail-tab-count">${tab.count}</span>
    </button>`).join("");
}

function renderRailBody() {
  const active = state.reading?.activeRailTab || "vocab";
  if (active === "vocab") {
    const items = mergedVocabulary();
    if (!items.length) return railEmpty("词汇卡还在路上", "这篇没有提取到重点词，可以直接点击文章中的任意词查词典。", "sparkles", "运行 AI 精讲", "run-ai");
    return items.map((item, index) => {
      const context = sentenceAround(item.context || "", item.lookup || item.word);
      return `
        <button class="rail-item" data-action="open-word" data-word="${esc(item.lookup || item.word)}" data-context="${esc(context)}" data-source-title="${esc(state.reading.analysis.title)}">
          <span class="rail-item-num">${String(index + 1).padStart(2, "0")}</span>
          <span class="rail-item-body">
            <span class="rail-word-row">
              <span class="rail-word">${esc(item.word)}${item.source === "ai" ? icon("sparkles") : ""}</span>
              ${item.pos ? `<span class="rail-word-meta">${esc(item.pos)}</span>` : item.count > 1 ? `<span class="rail-word-meta">×${item.count}</span>` : ""}
            </span>
            ${item.meaning_zh ? `<span class="rail-word-meaning">${esc(truncate(item.meaning_zh, 92))}</span>` : context ? `<span class="rail-word-context">“${esc(truncate(context, 100))}”</span>` : ""}
            ${item.meaning_zh && context ? `<span class="rail-word-context">“${esc(truncate(context, 88))}”</span>` : ""}
          </span>
        </button>`;
    }).join("");
  }

  if (active === "phrases") {
    const items = mergedPhrases();
    if (!items.length) return railEmpty("暂时没有识别到固定短语", "点击文中单词可以查看常见搭配，或运行 AI 生成短语讲解。", "quote", "运行 AI 精讲", "run-ai");
    return items.map((item) => `
      <button class="rail-item phrase-item" data-action="open-word" data-word="${esc(item.phrase)}" data-context="${esc(truncate(item.context || "", 240))}" data-source-title="${esc(state.reading.analysis.title)}">
        <span class="rail-phrase">${esc(item.phrase)}${item.kind ? `<span class="phrase-kind">${esc(item.kind)}</span>` : ""}</span>
        ${item.meaning_zh ? `<span class="rail-phrase-meaning">${esc(truncate(item.meaning_zh, 100))}</span>` : item.context ? `<span class="rail-context">“${esc(truncate(item.context, 105))}”</span>` : ""}
        ${item.meaning_zh && item.context ? `<span class="rail-context">“${esc(truncate(item.context, 95))}”</span>` : ""}
      </button>`).join("");
  }

  if (active === "keys") {
    const items = effectiveKeySentences();
    if (!items.length) return railEmpty("还没有挑出重点句", "运行 AI 精讲，可以得到主旨句、转折句和长难句的逐句拆解。", "quote", "运行 AI 精讲", "run-ai");
    return items.map((item, index) => `
      <div class="rail-item phrase-item" style="cursor:default">
        <div class="key-card-row">
          <span class="chip ${item.source === "ai" ? "green" : "gold"}">${esc(item.label || "重点句")}</span>
          ${item.paragraph ? `<span class="rail-word-meta">第 ${item.paragraph} 段</span>` : ""}
          <button class="key-play" data-action="speak-key" data-index="${index}" title="朗读句子" aria-label="朗读句子">${icon("volume")}</button>
        </div>
        <div class="key-sentence">${tokenizeHTML(item.sentence)}</div>
        ${item.translation_zh ? `<div class="key-translation">${esc(item.translation_zh)}</div>` : ""}
        ${item.analysis_zh ? `<div class="key-analysis">${esc(item.analysis_zh)}</div>` : ""}
      </div>`).join("");
  }

  const grammar = state.reading?.ai?.grammar || [];
  if (!grammar.length) {
    return railEmpty(
      "语法讲解还未生成",
      "运行 AI 精讲后，会结合本文句子整理 2–4 个关键语法点。",
      "graduation",
      state.boot?.ai_status?.configured ? "运行 AI 精讲" : "连接 AI",
      state.boot?.ai_status?.configured ? "run-ai" : "go-settings",
    );
  }
  return grammar.map((item) => `
    <div class="rail-item phrase-item" style="cursor:default">
      <div class="grammar-point">${esc(item.point)}</div>
      <div class="grammar-explain">${esc(item.explanation_zh)}</div>
      ${item.example ? `<div class="grammar-example">${esc(item.example)}</div>` : ""}
    </div>`).join("");
}

function railEmpty(title, text, iconName = "feather", buttonLabel = "", action = "") {
  return `
    <div class="rail-empty">
      <div class="empty-mark">${icon(iconName)}</div>
      <p><strong style="color:var(--ink-2);font-weight:600">${esc(title)}</strong><br>${esc(text)}</p>
      ${buttonLabel && action ? `<button class="btn small" data-action="${esc(action)}">${esc(buttonLabel)}</button>` : ""}
    </div>`;
}

function renderQuestionCard(question) {
  if (!question) return "";
  const reading = state.reading;
  const number = Number(question.number);
  const selected = reading?.userAnswers?.[number] || "";
  const answer = aiAnswerMap().get(number);
  const revealed = Boolean(reading?.reveal?.[number]) && Boolean(answer);
  const correctLetter = String(answer?.answer || "").match(/^[A-H]/i)?.[0]?.toUpperCase() || "";
  const options = question.options || [];
  const compact = question.type === "cloze" || (options.length > 0 && options.every((option) => option.text.length <= 24));
  const hasEvidence = (question.evidence?.length || 0) > 0 || (question.keywords?.length || 0) > 0;
  const configured = Boolean(state.boot?.ai_status?.configured);
  const optionHtml = options.map((option) => {
    const isSelected = selected === option.label;
    let className = "option";
    if (revealed) {
      if (option.label === correctLetter) className += " correct";
      else if (isSelected) className += " wrong";
    } else if (isSelected) {
      className += " selected";
    }
    return `
      <button class="${className}" data-action="select-option" data-number="${number}" data-label="${esc(option.label)}">
        <span class="option-label">${esc(option.label)}</span>
        <span>${esc(option.text)}</span>
      </button>`;
  }).join("");

  let answerState = "未作答";
  let answerStateClass = "";
  if (selected) answerState = `已选 ${selected}`;
  if (revealed && correctLetter) {
    if (selected && selected === correctLetter) {
      answerState = "答对了";
      answerStateClass = "correct";
    } else if (selected) {
      answerState = "答错了";
      answerStateClass = "wrong";
    } else {
      answerState = "已核对";
    }
  }

  const stemHtml = question.stem
    ? `<div class="q-stem">${tokenizeHTML(question.stem)}</div>`
    : question.context
      ? `<div class="q-context"><span class="q-context-label">空格所在句</span>${tokenizeHTML(question.context)}</div>`
      : `<div class="q-stem">第 ${number} 题</div>`;

  const evidenceHtml = hasEvidence
    ? `<div class="evidence-panel">
         <div class="panel-label">定位词</div>
         <div class="keyword-row">${(question.keywords || []).map((word) => `<span class="keyword-chip">${esc(word)}</span>`).join("") || `<span class="evidence-empty">暂未提取到明显定位词</span>`}</div>
         ${question.evidence?.length ? `
           <div class="panel-label" style="margin-top:10px">相关原文线索</div>
           ${question.evidence.map((item) => `<div class="evidence-item">${esc(item.sentence)}${item.paragraph ? `<span class="source-pos">第 ${item.paragraph} 段</span>` : ""}</div>`).join("")}
         ` : `<div class="evidence-empty">本地模式暂未找到直接对应的句子，可以运行 AI 获取更完整的依据。</div>`}
         <div class="evidence-item" style="border-left:0;padding-left:0;margin-top:9px;color:#8f8066">${esc(question.strategy_zh || question.local_hint || "")}</div>
       </div>`
    : "";

  const explainHtml = revealed
    ? `<div class="explain-panel open">
         <div class="explain-answer">
           <span class="answer-letter">${esc(correctLetter || "?")}</span>
           <span>参考答案${answer?.answer && answer.answer.length > 1 ? `：${esc(answer.answer)}` : ` ${esc(correctLetter)}`}</span>
           <span class="confidence">${answer?.confidence === "high" ? "把握较高" : answer?.confidence === "low" ? "把握较低" : "可结合原文核对"}</span>
         </div>
         ${answer?.reason_zh ? `<div class="explain-reason">${esc(answer.reason_zh)}</div>` : ""}
         ${answer?.evidence ? `<div class="explain-evidence">“${esc(answer.evidence)}”</div>` : `<div class="explain-missing">AI 没有给出可直接引用的原文依据，建议回文核对。</div>`}
         ${answer?.strategy_zh ? `<div class="explain-strategy">${esc(answer.strategy_zh)}</div>` : ""}
         ${selected && correctLetter && selected !== correctLetter ? `<div class="explain-missing">你选择的是 ${esc(selected)}，注意回看原文中限定范围和转折关系。</div>` : ""}
       </div>`
    : "";

  return `
    <article class="question-card" data-question="${number}">
      <div class="question-head">
        <span class="qnum">${String(number).padStart(2, "0")}</span>
        <span class="chip qtype">${esc(question.type_label || "阅读理解")}</span>
        <span class="q-answer-state ${answerStateClass}">${selected ? icon("check-circle") : ""}${esc(answerState)}</span>
      </div>
      ${stemHtml}
      ${options.length ? `<div class="options ${compact ? "compact" : ""}">${optionHtml}</div>` : ""}
      <div class="q-tools">
        ${hasEvidence ? `<button class="q-tool" data-action="toggle-evidence">${icon("target")}定位线索</button>` : ""}
        ${revealed
          ? `<button class="q-tool accent" data-action="toggle-answer" data-number="${number}">${icon("sparkles")}收起解析</button>`
          : answer
            ? `<button class="q-tool accent" data-action="toggle-answer" data-number="${number}">${icon("sparkles")}查看答案与解析</button>`
            : configured
              ? `<button class="q-tool accent" data-action="run-ai">${icon("sparkles")}AI 讲题</button>`
              : `<span class="q-tool">本地模式 · 不直接判断答案</span>`}
        <span class="q-tool-spacer"></span>
        ${question.options?.length ? `<span class="q-tool" style="cursor:default">${question.options.length} 个选项</span>` : ""}
      </div>
      ${evidenceHtml}
      ${explainHtml}
    </article>`;
}

/* --------------------------------------------------------------------------
   Wordbook
   -------------------------------------------------------------------------- */
function renderWordbook() {
  const stats = state.wordbook.stats || { total: 0, learning: 0, mastered: 0 };
  const hasTotal = (state.wordbook.items || []).length > 0 || stats.total > 0;
  return `
    <section class="page-heading">
      <div class="page-heading-copy">
        <div class="eyebrow">Your word garden</div>
        <h1>我的生词本</h1>
        <p>收藏的每一个词，都是下一次阅读的路标。点开卡片可以重听发音、看完整释义，也可以标记掌握程度。</p>
      </div>
      <div class="page-heading-actions">
        ${hasTotal ? `<button class="btn primary" data-action="start-review">${icon("play")}开始复习</button>` : ""}
        <button class="btn" data-action="export-wordbook">${icon("download")}<span class="btn-label">导出 CSV</span></button>
        <button class="btn" data-action="new-reading">${icon("plus")}<span class="btn-label">精读新题</span></button>
      </div>
    </section>

    <div class="stats-strip">
      <div class="stat-card green">
        <div class="stat-label">All words</div>
        <div class="stat-value">${stats.total || 0}</div>
        <div class="stat-note">已经收集的单词与短语</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Learning</div>
        <div class="stat-value">${stats.learning || 0}</div>
        <div class="stat-note">还需要再见几面</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Mastered</div>
        <div class="stat-value">${stats.mastered || 0}</div>
        <div class="stat-note">已经能认出并使用</div>
      </div>
    </div>

    ${hasTotal ? `
      <div class="wordbook-toolbar">
        <div class="search-box">
          ${icon("search")}
          <input class="search-input" id="wordbook-search" type="search" placeholder="搜索单词、释义或来源" value="${esc(state.wordbookQuery)}" autocomplete="off">
        </div>
        <div class="filter-tabs" role="tablist" aria-label="筛选生词">
          <button class="filter-tab ${state.wordbookStatus === "" ? "active" : ""}" data-action="wordbook-filter" data-status="">全部</button>
          <button class="filter-tab ${state.wordbookStatus === "learning" ? "active" : ""}" data-action="wordbook-filter" data-status="learning">学习中</button>
          <button class="filter-tab ${state.wordbookStatus === "mastered" ? "active" : ""}" data-action="wordbook-filter" data-status="mastered">已掌握</button>
        </div>
        <div class="spacer"></div>
        <span class="rail-head-note">${state.wordbook.items.length} 个词条</span>
      </div>
      <div id="wordbook-grid-host">${renderWordbookBody()}</div>
    ` : `
      <section class="empty-state">
        <div class="empty-visual">${icon("bookmark")}</div>
        <h3>生词本还是一片空地</h3>
        <p>去精读一篇题目，点击不熟悉的单词，在词条面板里点一下“加入生词本”。它们会在这里慢慢长成你的词库。</p>
        <button class="btn primary" data-action="new-reading">${icon("arrow-right")}去精读一篇</button>
      </section>`}`;
}

function filteredWordbookItems() {
  const query = state.wordbookQuery.trim().toLowerCase();
  return (state.wordbook.items || []).filter((item) => {
    if (state.wordbookStatus && item.status !== state.wordbookStatus) return false;
    if (!query) return true;
    const entry = item.data || {};
    const haystack = [
      item.word,
      item.source_title,
      item.source,
      wordMeaning(entry, 4),
      JSON.stringify(entry.definitions || []),
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });
}

function renderWordbookBody() {
  const items = filteredWordbookItems();
  if (!items.length) {
    return `
      <section class="empty-state" style="padding:58px 24px">
        <div class="empty-visual">${icon("search")}</div>
        <h3>没有找到对应的词</h3>
        <p>换一个关键词，或切换到“全部”看看。也可以回到精读页继续收藏。</p>
        <button class="btn" data-action="clear-filters">${icon("refresh")}清除筛选</button>
      </section>`;
  }
  return `<div class="word-grid">${items.map(renderWordCard).join("")}</div>`;
}

function renderWordCard(item) {
  const entry = item.data || {};
  const meaning = wordMeaning(entry, 2);
  const phonetic = wordPhonetic(entry);
  const mastered = item.status === "mastered";
  const context = item.source || "";
  return `
    <article class="word-card ${mastered ? "mastered" : ""}" data-action="open-word" data-word="${esc(item.word)}" data-context="${esc(truncate(item.source || "", 300))}" data-source-title="${esc(item.source_title || "")}" tabindex="0" role="button" aria-label="学习单词 ${esc(item.word)}">
      <div class="word-card-top">
        <div class="word-card-title">
          <h3>${esc(item.word)}</h3>
          ${phonetic ? `<span class="phonetic">${esc(phonetic)}</span>` : item.source_title ? `<span class="phonetic">${esc(item.source_title)}</span>` : ""}
        </div>
        <button class="word-audio" data-action="play-saved-word" data-id="${item.id}" title="播放发音" aria-label="播放发音">${icon("volume")}</button>
      </div>
      <p class="word-card-meaning">${esc(meaning || "暂无释义，点开重新查询。")}</p>
      ${context ? `<p class="word-card-context">“${esc(truncate(context, 105))}”</p>` : ""}
      <div class="word-card-foot">
        <span class="status-pill ${mastered ? "mastered" : ""}">${mastered ? "已掌握" : "学习中"}</span>
        <span class="word-date">${formatDate(item.created_at)}</span>
        <div class="word-card-menu">
          <button class="word-menu-btn" data-action="toggle-mastered" data-id="${item.id}" title="${mastered ? "移回学习中" : "标记已掌握"}" aria-label="${mastered ? "移回学习中" : "标记已掌握"}">${icon(mastered ? "refresh" : "check-circle")}</button>
          <button class="word-menu-btn" data-action="delete-word" data-id="${item.id}" title="移出生词本" aria-label="移出生词本">${icon("trash")}</button>
        </div>
      </div>
    </article>`;
}

/* --------------------------------------------------------------------------
   Settings
   -------------------------------------------------------------------------- */
function renderSettings() {
  const draft = state.settingsDraft || (state.settingsDraft = buildSettingsDraft());
  const presets = state.boot?.provider_presets || [];
  const activePreset = presets.find((preset) => preset.id === draft.ai.provider) || presets[presets.length - 1] || null;
  const aiStatus = state.boot?.ai_status || {};
  const ocr = state.boot?.ocr || {};
  const dictionaryInfo = state.boot?.dictionary || {};
  const dictionaryProviders = dictionaryInfo.providers || [];
  const offlineDictionary = dictionaryProviders.find((item) => item.id === "ecdict");
  const onlineDictionary = dictionaryProviders.find((item) => item.id === "wiktionary");
  const stats = state.wordbook.stats || { total: 0 };
  const keyPlaceholder = draft.keySet ? "已保存密钥，留空保持不变" : "sk-...";
  const providerUrl = draft.ai.base_url || activePreset?.base_url || "尚未填写";
  const providerModel = draft.ai.model || activePreset?.model || "尚未填写";
  const languages = ocr.languages || [];
  const englishOcr = ocr.english_available !== false;
  const aiVision = Boolean(draft.ocr?.ai_vision);
  const aiVisionAvailable = ocr.ai_vision_available !== false;
  const pwa = Boolean(window.__LEXIREAD_PWA__);

  return `
    <section class="page-heading">
      <div class="page-heading-copy">
        <div class="eyebrow">Preferences</div>
        <h1>设置</h1>
        <p>把 AI、本地 OCR 和学习偏好调到适合你的样子。所有设置只保存在这台电脑上。</p>
      </div>
      <div class="page-heading-actions">
        <span class="settings-status ${aiStatus.configured ? "on" : ""}">${aiStatus.configured ? "AI 已配置" : "本地模式"}</span>
      </div>
    </section>

    <div class="settings-grid">
      <section class="settings-card span-2">
        <div class="settings-card-head">
          <div>
            <div class="settings-title">${icon("sparkles")}AI 精讲连接</div>
            <p class="settings-desc">任意兼容 OpenAI Chat Completions 的服务都可以。推荐 DeepSeek；不配置也能使用 OCR、词典和生词本。</p>
          </div>
          <span class="settings-status ${aiStatus.configured ? "on" : ""}">${aiStatus.configured ? esc(aiStatus.model || "已配置") : "未配置"}</span>
        </div>
        <div class="ai-card-inner">
          <div class="ai-form-col">
            <div class="provider-chips" role="group" aria-label="选择服务商">
              ${presets.map((preset) => `<button class="provider-chip ${draft.ai.provider === preset.id ? "active" : ""}" data-action="set-provider" data-provider="${esc(preset.id)}">${esc(preset.name)}</button>`).join("")}
            </div>
            <div class="form-grid">
              <div class="field full">
                <label for="setting-base-url">API Base URL <span>· 以 /v1 结尾</span></label>
                <input class="input" id="setting-base-url" data-setting="ai.base_url" value="${esc(draft.ai.base_url)}" placeholder="https://api.deepseek.com/v1" spellcheck="false" autocomplete="off">
              </div>
              <div class="field">
                <label for="setting-model">模型名称</label>
                <input class="input" id="setting-model" data-setting="ai.model" value="${esc(draft.ai.model)}" placeholder="deepseek-chat" spellcheck="false" autocomplete="off">
              </div>
              <div class="field">
                <label for="api-key-input">API Key</label>
                <div class="api-key-wrap">
                  <input class="input" id="api-key-input" data-setting="ai.api_key" type="password" value="${esc(draft.ai.api_key || "")}" placeholder="${esc(keyPlaceholder)}" spellcheck="false" autocomplete="new-password">
                  <button class="key-toggle" type="button" data-action="toggle-key-visibility" aria-label="显示或隐藏密钥">${icon("eye")}</button>
                </div>
              </div>
            </div>
            <div class="key-hint">
              <span>${draft.clearKey ? "保存后将清除已存密钥。" : draft.keySet ? "密钥已保存在本机 SQLite 中。" : "没有密钥？本地 Ollama 也可以。"}${activePreset?.hint ? ` · ${esc(activePreset.hint)}` : ""}</span>
              ${draft.keySet && !draft.clearKey ? `<button data-action="clear-api-key">清除密钥</button>` : ""}
            </div>
            <div class="form-actions">
              <button class="btn primary" data-action="save-ai-settings">${icon("check")}保存设置</button>
              <button class="btn" data-action="test-ai">${icon("zap")}保存并测试连接</button>
            </div>
            <div class="form-status" id="ai-form-status" role="status"></div>
            <p class="form-note">${pwa ? "密钥只保存在本机浏览器存储中；AI 请求由浏览器直接发送给你配置的服务商，部分服务商可能限制跨域请求。" : "密钥只保存在本机，不会写入前端 JavaScript。AI 调用由本地 Python 服务转发。"}</p>
          </div>
          <div class="ai-side-col">
            <div class="ai-provider-card">
              <div class="provider-name">${esc(activePreset?.name || "自定义服务")}</div>
              <div class="provider-url">${esc(providerUrl)}</div>
              <div class="provider-models"><span class="chip green">${esc(providerModel)}</span>${aiStatus.configured ? `<span class="chip gold">已配置</span>` : `<span class="chip">待配置</span>`}</div>
              <p class="form-note" style="margin-top:9px">${esc(activePreset?.hint || "填写任意 OpenAI 兼容服务的地址与模型。")}</p>
            </div>
            <div class="privacy-panel">
              <h4>${icon("shield")}隐私边界</h4>
              <p>默认图片和 OCR 识别都在本机完成。开启“AI 视觉识别”后，图片会发送给你配置的服务商；离线词典未收录的单词会发给在线 Wiktionary；只有你主动点击“AI 精讲”时，题目全文才会发送到你配置的服务商。</p>
            </div>
            <div class="privacy-panel">
              <h4>${icon("info")}推荐模型</h4>
              <p>DeepSeek Chat / Qwen Plus / GLM-4 Flash 都适合做英语讲解。题目较长时，建议使用上下文 32K 以上的模型。</p>
            </div>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div>
            <div class="settings-title">${icon("scan")}本地 OCR</div>
            <p class="settings-desc">${pwa ? "使用浏览器内置的 Tesseract 英文引擎，图片无需联网，也不会上传。" : "默认使用 Windows 自带的识别引擎，图片无需联网；也可以开启 AI 视觉识别处理拍照题图。"}</p>
          </div>
          <span class="settings-status ${ocr.available && englishOcr ? "on" : ocr.available ? "warn" : ""}">${ocr.available ? (englishOcr ? "可用" : "缺英文包") : "不可用"}</span>
        </div>
        <div class="ocr-status-panel">
          <div class="ocr-status-icon">${icon("scan")}</div>
          <div class="ocr-status-copy">
            <h4>${esc(ocr.engine || "Windows OCR")}${ocr.available ? " 已就绪" : " 未就绪"}</h4>
            <p>${esc(ocr.message || "当前系统未检测到可用的 OCR 组件。")}</p>
            <div class="ocr-langs">${languages.length ? languages.map((lang) => `<code>${esc(lang)}</code>`).join("") : `<code>no language</code>`}</div>
          </div>
        </div>
        ${aiVisionAvailable
          ? `<div class="settings-section-divider"></div>
        <div class="pref-row">
          <div class="pref-info">
            <h4>AI 视觉识别</h4>
            <p>把图片发给你配置的视觉模型识别，适合拍照、倾斜、光线不均的题图。需要模型支持图片输入${activePreset?.vision_model ? `，例如 ${esc(activePreset.vision_model)}` : ""}。</p>
          </div>
          <button class="provider-chip ${aiVision ? "active" : ""}" data-action="toggle-ai-vision">${aiVision ? "已开启" : "开启"}</button>
        </div>
        <p class="form-note">${aiVision ? "开启后图片会发送到你的 AI 服务商；识别失败时自动回退本机 OCR。" : "关闭时图片只在本机处理；AI 未配置时开启也会回退本机 OCR。"}</p>`
          : `<p class="form-note">PWA 版本使用 Tesseract.js 本地识别；AI 视觉识别请在桌面版或原生版本中使用。</p>`}
        ${ocr.available && !englishOcr
          ? `<div class="ocr-warning">${icon("alert")}<span>当前只检测到 ${languages.length ? languages.map((lang) => `<code>${esc(lang)}</code>`).join("") : "非英语"} OCR 语言包。英文识别准确率会明显下降，建议安装 English 语言包（含“光学字符识别”可选功能）后重新识别。</span></div>
             <div class="form-actions" style="margin-top:10px">
               ${ocr.can_open_language_settings === false ? "" : `<button class="btn" data-action="open-language-settings">${icon("settings")}打开 Windows 语言设置</button>`}
             </div>`
          : `<p class="form-note">${pwa ? "Tesseract.js 已内置英文模型，无需安装语言包。" : "在 Windows 设置的“语言”中添加 English 语言包，并勾选“光学字符识别”，识别会更稳定。"}</p>`}
        <div class="settings-section-divider"></div>
        <div class="ocr-status-panel">
          <div class="ocr-status-icon">${icon("book")}</div>
          <div class="ocr-status-copy">
            <h4>离线词典 · ${offlineDictionary?.entries ? `${Number(offlineDictionary.entries).toLocaleString("en-US")} 词条` : "ECDICT"}</h4>
            <p>${offlineDictionary?.available ? "音标、中文释义、词形变化均可离线查询；本地未收录时，再尝试在线词典。" : "离线词库文件未找到，将只使用在线词典。"}</p>
            <div class="ocr-langs">
              ${offlineDictionary ? `<code>${esc(offlineDictionary.name)}</code><code>${esc(offlineDictionary.license || "开放许可")}</code>` : ""}
              ${onlineDictionary ? `<code>${esc(onlineDictionary.name)} · ${esc(onlineDictionary.license || "CC BY-SA")}</code>` : ""}
            </div>
          </div>
        </div>
        <p class="form-note">离线词典数据来自 ECDICT（MIT）；在线补充来自 Wiktionary（CC BY-SA）。具体署名见 THIRD_PARTY_NOTICES.md。</p>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div>
            <div class="settings-title">${icon("graduation")}学习偏好</div>
            <p class="settings-desc">这些偏好会用于 AI 讲题时的难度判断与语音朗读。</p>
          </div>
        </div>
        <div class="pref-list">
          <div class="pref-row">
            <div class="pref-info"><h4>目标考试</h4><p>影响 AI 的讲解深度与用词</p></div>
            <select class="select compact" data-setting="learning.exam">
              ${["CET-4", "CET-6", "考研", "高考", "IELTS", "TOEFL"].map((exam) => `<option value="${esc(exam)}" ${draft.learning.exam === exam ? "selected" : ""}>${esc(exam)}</option>`).join("")}
            </select>
          </div>
          <div class="pref-row">
            <div class="pref-info"><h4>发音口音</h4><p>单词音频与句子朗读优先使用</p></div>
            <div class="segmented">
              <button class="${draft.learning.accent === "us" ? "active" : ""}" data-action="set-accent" data-accent="us">美音</button>
              <button class="${draft.learning.accent === "uk" ? "active" : ""}" data-action="set-accent" data-accent="uk">英音</button>
            </div>
          </div>
          <div class="pref-row">
            <div class="pref-info"><h4>朗读速度</h4><p>仅影响浏览器朗读，不影响单词音频</p></div>
            <div class="range-wrap">
              <input type="range" min="0.7" max="1.3" step="0.05" value="${draft.learning.voice_rate}" data-setting="learning.voice_rate" id="voice-rate-input">
              <span class="range-value" id="voice-rate-value">${Number(draft.learning.voice_rate).toFixed(2)}×</span>
            </div>
          </div>
        </div>
        <div class="form-actions">
          <button class="btn" data-action="save-learning">${icon("check")}保存学习偏好</button>
        </div>
        <div class="form-status" id="settings-form-status" role="status"></div>
      </section>

      <section class="settings-card">
        <div class="settings-card-head">
          <div>
            <div class="settings-title">${icon("notebook")}数据管理</div>
            <p class="settings-desc">${pwa ? "生词本数据保存在浏览器本地的 SQLite 存储中，清理浏览器数据会删除它。" : "生词本数据保存在本机的 SQLite 文件中。"}</p>
          </div>
          <span class="settings-status">${stats.total || 0} 词</span>
        </div>
        <div class="data-actions">
          <div class="data-action-row">
            <div class="data-action-icon">${icon("download")}</div>
            <div class="data-action-copy"><h4>导出全部生词</h4><p>CSV 文件，可用 Excel 打开</p></div>
            <button class="btn small" data-action="export-wordbook">导出</button>
          </div>
          <div class="data-action-row">
            <div class="data-action-icon">${icon("refresh")}</div>
            <div class="data-action-copy"><h4>清除词典缓存</h4><p>下次查词会重新获取最新释义</p></div>
            <button class="btn small" data-action="clear-cache">清除</button>
          </div>
          <div class="data-action-row">
            <div class="data-action-icon">${icon("trash")}</div>
            <div class="data-action-copy"><h4>清空生词本</h4><p>会删除全部收藏，操作不可撤销</p></div>
            <button class="danger-link" data-action="clear-wordbook">清空</button>
          </div>
        </div>
      </section>

      <section class="settings-card about-card">
        <div class="settings-title">${icon("feather")}关于 LexiRead</div>
        <p class="settings-desc">一张题图，读成一堂课。</p>
        <div class="about-copy">为英语精读而做：本机 OCR、点词释义、AI 讲题和一本不丢词的生词本。</div>
        <div class="about-meta">
          <span>${icon("book")}Version 1.0.0</span>
          <span>${icon("shield")}Local first</span>
          <span>${icon("sparkles")}AI optional</span>
          <span>PolyForm NC 1.0.0</span>
          <span>© sonic111222</span>
        </div>
      </section>
    </div>`;
}

/* --------------------------------------------------------------------------
   Word drawer
   -------------------------------------------------------------------------- */
function renderDrawer() {
  const drawer = state.drawer;
  if (!drawer?.open) {
    drawerRoot.innerHTML = "";
    syncBodyLock();
    return;
  }
  const saved = savedMap().get(wordKey(drawer.word));
  const savedId = drawer.savedId || saved?.id;
  let content = "";
  if (drawer.loading) {
    content = `
      <div class="drawer-loading">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line wide" style="height:24px;margin-top:18px"></div>
        <div class="skeleton-line mid"></div>
        <div class="skeleton-line wide" style="margin-top:28px"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line mid"></div>
      </div>`;
  } else if (drawer.error) {
    content = `
      <div class="drawer-error">
        <div class="error-icon">${icon("alert")}</div>
        <h3>暂时查不到这个词</h3>
        <p>${esc(drawer.error)}</p>
        <button class="btn" data-action="retry-drawer">${icon("refresh")}再查一次</button>
      </div>`;
  } else if (drawer.entry) {
    content = renderWordEntry(drawer.entry);
  }

  const footer = drawer.entry
    ? savedId
      ? `<button class="btn primary" data-action="go-wordbook">${icon("check")}已在生词本</button>
         <button class="btn" data-action="remove-current-word" data-id="${savedId}" title="移出生词本" aria-label="移出生词本">${icon("trash")}</button>`
      : `<button class="btn primary" data-action="save-current-word">${icon("star")}加入生词本</button>`
    : "";

  drawerRoot.innerHTML = `
    <div class="word-drawer-layer">
      <div class="drawer-backdrop" data-action="close-drawer"></div>
      <aside class="word-drawer" role="dialog" aria-modal="true" aria-label="词条详情">
        <div class="drawer-top">
          <div class="drawer-label">${icon("notebook")}WORD NOTE · 词条</div>
          <div class="drawer-top-actions">
            <button class="icon-btn" data-action="close-drawer" aria-label="关闭词条">${icon("x")}</button>
          </div>
        </div>
        <div class="drawer-scroll">${content}</div>
        ${footer ? `<div class="drawer-footer">${footer}</div>` : ""}
      </aside>
    </div>`;
  syncBodyLock();
}

function renderWordEntry(entry) {
  const drawer = state.drawer;
  const saved = savedMap().get(wordKey(drawer.word));
  const aiMatch = aiVocabMatch(drawer.word);
  const context = drawer.context || "";
  const definitions = entry.definitions || [];
  const examples = entry.examples || [];
  const phrases = entry.phrases || [];
  const forms = entry.forms || [];
  const synonyms = entry.synonyms || [];
  const englishDefs = entry.english_definitions || [];
  const examTags = entry.exam_tags || [];
  const us = formatIpa(entry.phonetic?.us);
  const uk = formatIpa(entry.phonetic?.uk);
  const phoneticBits = [];
  if (us) phoneticBits.push(`<span class="ipa">US ${esc(us)}</span>`);
  if (uk && uk !== us) phoneticBits.push(`<span class="ipa">UK ${esc(uk)}</span>`);
  const staleNote = entry.stale ? `<div class="form-note" style="color:var(--coral)">当前展示的是本地缓存，网络恢复后可再刷新。</div>` : "";
  const matchNote = entry.matched_form ? `<span class="modal-flag">${icon("info")}按原形 ${esc(entry.matched_form)} 查询</span>` : "";
  const englishOnlyDefinitions = entry.definition_lang === "en";

  return `
    <div class="word-head">
      <div class="word-head-copy">
        <h2 class="word-title">${esc(entry.word || drawer.word)}</h2>
        <div class="phonetic-line">
          ${phoneticBits.length ? phoneticBits.join('<span class="dot-sep">·</span>') : `<span class="ipa" style="color:var(--faint)">暂无音标</span>`}
          ${entry.source ? `<span class="dot-sep">·</span><span style="font-family:var(--sans);font-size:9px;color:var(--faint)">${esc(entry.source)}</span>` : ""}
        </div>
        <div class="audio-buttons">
          <button class="audio-btn" data-action="play-word" data-accent="us">${icon("volume")}美音</button>
          <button class="audio-btn" data-action="play-word" data-accent="uk">${icon("volume")}英音</button>
          ${entry.audio?.us || entry.audio?.uk ? "" : `<span class="rail-word-meta">使用浏览器朗读</span>`}
        </div>
        <div class="word-tags">
          ${examTags.slice(0, 4).map((tag) => `<span class="chip">${esc(tag)}</span>`).join("")}
          ${matchNote}
        </div>
      </div>
      <button class="save-btn ${saved ? "saved" : ""}" data-action="save-current-word" title="${saved ? "已收藏" : "加入生词本"}" aria-label="${saved ? "已收藏" : "加入生词本"}">${icon("star")}</button>
    </div>

    ${aiMatch ? `
      <div class="ai-usage-box">
        <div class="ai-usage-head">${icon("sparkles")}AI 语境讲解</div>
        ${aiMatch.meaning_zh ? `<p>${esc(aiMatch.meaning_zh)}</p>` : ""}
        ${aiMatch.usage_zh ? `<p>${esc(aiMatch.usage_zh)}</p>` : ""}
        ${aiMatch.example ? `<p class="example">“${esc(aiMatch.example)}”${aiMatch.example_zh ? ` ${esc(aiMatch.example_zh)}` : ""}</p>` : ""}
      </div>` : ""}

    ${context ? `
      <div class="word-section">
        <div class="word-section-title"><span>In context</span><span>原文语境</span></div>
        <div class="example-item" style="border-left-color:var(--gold)">
          <div class="example-en">${highlightWord(context, drawer.lookup || drawer.word)}</div>
          ${drawer.sourceTitle ? `<div class="example-source">来自《${esc(drawer.sourceTitle)}》</div>` : ""}
        </div>
      </div>` : ""}

    <div class="word-section">
      <div class="word-section-title"><span>Meaning</span><span>${englishOnlyDefinitions ? "英文释义" : "释义"}</span></div>
      ${definitions.length ? `<div class="def-list">${definitions.map((item) => `
        <div class="def-row">
          ${item.pos ? `<span class="pos-badge">${esc(item.pos)}</span>` : ""}
          <div class="def-text">${esc(item.meaning)}</div>
        </div>`).join("")}</div>` : `<p class="form-note">这个词暂时没有可用释义，可以刷新重试，或配置 AI 获取语境讲解。</p>`}
      ${englishOnlyDefinitions ? `<p class="form-note">当前释义来自在线词典的英文内容。配置 AI 后，可以在“AI 语境讲解”里看到中文用法。</p>` : ""}
      ${!englishOnlyDefinitions && !examples.length ? `<p class="form-note">离线词库提供音标、释义和词形变化；例句可以结合上方原文语境理解，也可以运行 AI 精讲补全用法。</p>` : ""}
    </div>

    ${examples.length ? `
      <div class="word-section">
        <div class="word-section-title"><span>Examples</span><span>双语例句</span></div>
        <div class="example-list">
          ${examples.map((example, index) => `
            <div class="example-item">
              <div class="example-en">${highlightWord(example.en, drawer.lookup || drawer.word)}</div>
              ${example.zh ? `<div class="example-zh">${esc(example.zh)}</div>` : ""}
              ${example.source ? `<div class="example-source">${esc(example.source)}</div>` : ""}
              <button class="example-play" data-action="play-example" data-index="${index}" title="朗读例句" aria-label="朗读例句">${icon("volume")}</button>
            </div>`).join("")}
        </div>
      </div>` : ""}

    ${phrases.length ? `
      <div class="word-section">
        <div class="word-section-title"><span>Collocations</span><span>常见搭配</span></div>
        <div class="phrase-tags">
          ${phrases.map((phrase) => `<div class="phrase-tag"><strong>${esc(phrase.phrase)}</strong><span>${esc(phrase.meaning || "")}</span></div>`).join("")}
        </div>
      </div>` : ""}

    ${forms.length ? `
      <div class="word-section">
        <div class="word-section-title"><span>Word forms</span><span>词形变化</span></div>
        <div class="form-chips">${forms.map((form) => `<span class="form-chip"><b>${esc(form.value)}</b>${esc(form.name)}</span>`).join("")}</div>
      </div>` : ""}

    ${synonyms.length ? `
      <div class="word-section">
        <div class="word-section-title"><span>Synonyms</span><span>同义词</span></div>
        ${synonyms.map((synonym) => `<div class="synonym-row"><span class="synonym-pos">${esc(synonym.pos || "")}</span><span class="synonym-words">${esc((synonym.words || []).join(" · "))}${synonym.meaning ? ` — ${esc(synonym.meaning)}` : ""}</span></div>`).join("")}
      </div>` : ""}

    ${englishDefs.length ? `
      <div class="word-section">
        <details class="english-defs">
          <summary>${icon("chevron-right")}英文释义</summary>
          <div class="english-defs-body">
            ${englishDefs.slice(0, 5).map((item) => `<div class="english-def-item">${item.pos ? `<span class="pos-badge">${esc(item.pos)}</span>` : ""}${esc(item.definition)}</div>`).join("")}
          </div>
        </details>
      </div>` : ""}

    <div class="drawer-source">
      ${icon("info")}数据来源：${entry.source_url ? `<a href="${esc(entry.source_url)}" target="_blank" rel="noopener noreferrer">${esc(entry.source || "在线词典")}</a>` : esc(entry.source || "在线词典")}
      ${entry.license ? ` · ${esc(entry.license)}` : ""}
      ${entry.cached ? " · 本地缓存" : ""}
      ${entry.matched_form ? ` · 已按 ${esc(entry.matched_form)} 查询` : ""}
    </div>
    ${staleNote}`;
}

/* --------------------------------------------------------------------------
   Review flashcards
   -------------------------------------------------------------------------- */
function renderReviewModal() {
  if (!state.review) return;
  const html = renderReviewContent();
  if (!state.modalOpen) {
    openModal(html, {
      className: "review-shell",
      onClose: () => {
        state.review = null;
        if (state.page === "wordbook") render();
      },
    });
  } else {
    const modal = $(".modal");
    if (modal) {
      modal.className = "modal review-shell";
      modal.innerHTML = html;
    }
  }
}

function renderReviewContent() {
  const review = state.review;
  if (!review) return "";
  const total = review.items.length;
  const heading = `
    <div class="modal-head" style="margin-bottom:13px">
      <div>
        <div class="modal-eyebrow">WORD REVIEW</div>
        <h2 style="font-size:21px">生词复习</h2>
      </div>
      <button class="modal-close" data-action="close-modal" aria-label="关闭">${icon("x")}</button>
    </div>`;
  if (review.index >= total) {
    return `
      ${heading}
      <div class="review-done">
        <div class="review-done-icon">${icon("check-circle")}</div>
        <h3>这一轮复习完成</h3>
        <p>记住了 ${review.mastered} 个，还需要再见 ${review.learning} 个。下一次精读时继续留意它们。</p>
        <div class="modal-actions" style="justify-content:center;border:0;padding-top:10px">
          <button class="btn" data-action="review-restart">${icon("refresh")}再来一轮</button>
          <button class="btn primary" data-action="close-modal">回到生词本</button>
        </div>
      </div>`;
  }
  const item = review.items[review.index];
  const entry = item.data || {};
  const phonetic = wordPhonetic(entry);
  const meaning = reviewMeaning(item);
  const progress = ((review.index + 1) / total) * 100;
  return `
    ${heading}
    <div class="review-progress-row">
      <span class="review-progress-text">${review.index + 1} / ${total}</span>
      <div class="review-progress-track"><span style="width:${progress}%"></span></div>
      <span class="review-progress-text">${Math.round(progress)}%</span>
    </div>
    <div class="flashcard">
      <div class="flashcard-kicker">Do you remember?</div>
      <div class="flashcard-word">${esc(item.word)}</div>
      ${phonetic ? `<div class="flashcard-phonetic">${esc(phonetic)}</div>` : ""}
      <button class="audio-btn" data-action="review-audio" style="margin-top:13px">${icon("volume")}听发音</button>
      <div class="flashcard-answer ${review.revealed ? "show" : ""}">
        <div class="flashcard-meaning">${esc(meaning)}</div>
        ${item.source ? `<div class="flashcard-context">“${esc(truncate(item.source, 180))}”</div>` : ""}
      </div>
    </div>
    <div class="review-actions">
      ${review.revealed
        ? `<button class="btn" data-action="review-again">${icon("refresh")}还不熟</button>
           <button class="btn primary" data-action="review-known">${icon("check")}记住了</button>`
        : `<button class="btn ghost" data-action="review-skip">先跳过</button>
           <button class="btn primary" data-action="review-reveal">${icon("eye")}看释义</button>`}
    </div>`;
}

/* --------------------------------------------------------------------------
   Help / lightbox
   -------------------------------------------------------------------------- */
function openHelpModal() {
  openModal(
    `${modalHeader({
      eyebrow: "QUICK GUIDE",
      title: "怎样把一篇题读透",
      description: "LexiRead 把一张题图拆成：原文、题目、知识卡和生词本。",
    })}
     <div class="help-list">
       <div class="help-item"><span class="help-num">1</span><div><h4>导入题目</h4><p>拖入截图或用文本粘贴。图片默认只在本机跑 OCR；识别结果可以先改错字。</p></div></div>
       <div class="help-item"><span class="help-num">2</span><div><h4>先做题，再看解析</h4><p>题目选项可以直接点选。本地模式会给出定位词和原文线索；连接 AI 后可核对答案与依据。</p></div></div>
       <div class="help-item"><span class="help-num">3</span><div><h4>点词积累</h4><p>文章中所有单词都可点击。词条面板提供音标、真人音频、释义、例句、搭配和词形变化，可一键收藏。</p></div></div>
       <div class="help-item"><span class="help-num">4</span><div><h4>在生词本里复习</h4><p>生词本支持搜索、标记掌握和抽认卡复习。数据保存在本机 SQLite，也可以导出 CSV。</p></div></div>
     </div>
     <div class="help-tip"><strong>小提示：</strong>按 <span class="mono">Esc</span> 关闭词条或弹窗；右上角的 AI 状态胶囊可以快速进入设置。</div>
     <div class="modal-actions"><button class="btn primary" data-action="close-modal" data-autofocus>开始精读</button></div>`,
    { className: "narrow" },
  );
}

function openImageViewer() {
  if (!state.reading?.previewUrl) return;
  state.lastFocus = document.activeElement;
  state.modalOpen = true;
  overlayRoot.innerHTML = `
    <div class="lightbox" role="dialog" aria-modal="true" aria-label="题目原图">
      <button class="lightbox-close" data-action="close-modal" aria-label="关闭图片" data-autofocus>${icon("x")}</button>
      <img src="${esc(state.reading.previewUrl)}" alt="题目原图">
      <p>原图仅保存在本机 · 点击右上角关闭</p>
    </div>`;
  syncBodyLock();
}

/* --------------------------------------------------------------------------
   Events
   -------------------------------------------------------------------------- */
function bindGlobalEvents() {
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onDocumentKeydown);
  document.addEventListener("input", onDocumentInput);
  document.addEventListener("change", onDocumentChange);
  document.addEventListener("dragover", onDragOver);
  document.addEventListener("dragleave", onDragLeave);
  document.addEventListener("drop", onDrop);
  window.addEventListener("hashchange", handleRouteChange);
  overlayRoot.addEventListener("click", (event) => {
    if (event.target.classList.contains("overlay") || event.target.classList.contains("lightbox")) {
      closeModal();
    }
  });
  if ("speechSynthesis" in window) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }
}

function hasTextSelection() {
  const selection = window.getSelection?.();
  return Boolean(selection && selection.toString().trim());
}

async function onDocumentClick(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (!action) return;
  if (action === "open-word" && hasTextSelection()) return;
  if (target.disabled) return;
  event.preventDefault();
  try {
    await handleAction(action, target, event);
  } catch (error) {
    console.error(error);
    toast(error?.message || "操作没有完成，请再试一次。", "error");
  }
}

async function handleAction(action, element) {
  switch (action) {
    case "reload-page":
      location.reload();
      break;

    case "choose-file": {
      if (state.modalOpen) closeModal({ runCallback: false });
      const input = $("#file-input");
      if (input) input.click();
      break;
    }

    case "switch-mode": {
      const mode = element.dataset.mode === "paste" ? "paste" : "image";
      state.uploadMode = mode;
      $$(".mode-tab").forEach((tab) => {
        const active = tab.dataset.mode === mode;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", active ? "true" : "false");
      });
      $(".dropzone")?.classList.toggle("hidden", mode !== "image");
      $(".paste-panel")?.classList.toggle("hidden", mode !== "paste");
      if (mode === "paste") window.setTimeout(() => $("#paste-input")?.focus(), 30);
      break;
    }

    case "submit-paste": {
      const text = $("#paste-input")?.value || state.pasteText;
      state.pasteText = text;
      await analyzeText(text);
      break;
    }

    case "use-sample":
      await loadSample(element.dataset.id);
      break;

    case "new-reading": {
      if (!state.reading) {
        state.studioMode = "landing";
        navigate("studio");
        break;
      }
      openConfirm({
        title: "开始新的精读？",
        message: `当前这篇《${esc(state.reading.analysis.title)}》会被新内容替换。生词本里的词不会被删除。`,
        confirmLabel: "开始新精读",
        onConfirm: () => {
          localStorage.removeItem(READING_KEY);
          state.reading = null;
          state.studioMode = "landing";
          state.page = "studio";
          if (location.hash !== "#studio") history.replaceState(null, "", "#studio");
          render();
          window.scrollTo({ top: 0, behavior: "auto" });
        },
      });
      break;
    }

    case "edit-text":
      openEditModal();
      break;

    case "save-edit": {
      const text = $("#edit-source")?.value?.trim() || "";
      const title = $("#edit-title")?.value?.trim() || "";
      if (!text) {
        toast("原文不能为空。", "error");
        return;
      }
      const { previewUrl, originalName } = state.reading || {};
      closeModal();
      await analyzeText(text, { title, previewUrl, originalName });
      break;
    }

    case "view-image":
      openImageViewer();
      break;

    case "start-ocr-analysis": {
      const text = $("#ocr-text")?.value?.trim() || "";
      const draft = state.ocrDraft;
      if (!text) {
        toast("识别结果为空，请重新选择图片。", "error");
        return;
      }
      closeModal();
      await analyzeText(text, {
        previewUrl: draft?.preview_url || "",
        originalName: draft?.original_name || "",
      });
      break;
    }

    case "retry-image":
      closeModal();
      window.setTimeout(() => $("#file-input")?.click(), 60);
      break;

    case "run-ai":
      await runAI(element.dataset.force === "1");
      break;

    case "font-minus":
    case "font-plus": {
      const current = getReadingSize();
      applyReadingSize(current + (action === "font-plus" ? 1 : -1));
      break;
    }

    case "toggle-translation":
      toggleTranslation();
      break;

    case "toggle-evidence": {
      const card = element.closest(".question-card");
      const panel = card?.querySelector(".evidence-panel");
      if (!panel) return;
      const open = panel.classList.toggle("open");
      element.setAttribute("aria-expanded", open ? "true" : "false");
      break;
    }

    case "select-option": {
      const number = Number(element.dataset.number);
      if (state.reading?.reveal?.[number]) {
        toast("解析已展开。先收起解析，再重新选择。", "info");
        return;
      }
      selectOption(number, element.dataset.label || "");
      break;
    }

    case "toggle-answer":
      toggleReveal(Number(element.dataset.number));
      break;

    case "scroll-questions": {
      const divider = $(".questions-divider");
      if (divider) {
        const top = divider.getBoundingClientRect().top + window.scrollY - 90;
        window.scrollTo({ top, behavior: "smooth" });
      }
      break;
    }

    case "rail-tab": {
      const tab = element.dataset.tab || "vocab";
      if (!state.reading) return;
      state.reading.activeRailTab = tab;
      persistReading();
      $$(".rail-tab").forEach((item) => {
        const active = item.dataset.tab === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      const body = $(".rail-body");
      if (body) body.innerHTML = renderRailBody();
      break;
    }

    case "speak-key": {
      const items = effectiveKeySentences();
      const item = items[Number(element.dataset.index)];
      if (item?.sentence) speakText(item.sentence, element);
      break;
    }

    case "open-word": {
      let context = element.dataset.context || "";
      const sourceTitle = element.dataset.sourceTitle || state.reading?.analysis?.title || "";
      if (!context && element.classList.contains("word-token")) {
        const container = element.closest(".para, .key-sentence, .q-stem, .q-context");
        if (container) context = sentenceAround(container.textContent, element.dataset.word || "");
      }
      await openWord(element.dataset.word || "", context, sourceTitle);
      break;
    }

    case "close-drawer":
      closeDrawer();
      break;

    case "retry-drawer":
      await fetchDrawerWord(true);
      break;

    case "play-word":
      playDrawerAudio(element.dataset.accent === "uk" ? "uk" : "us");
      break;

    case "play-example":
      playDrawerExample(Number(element.dataset.index));
      break;

    case "save-current-word":
      await saveCurrentWord();
      break;

    case "remove-current-word": {
      const id = Number(element.dataset.id);
      const word = state.drawer?.word || "这个单词";
      openConfirm({
        title: "移出生词本？",
        message: `确定要把 <strong>${esc(word)}</strong> 从生词本移除吗？之后仍然可以重新收藏。`,
        confirmLabel: "移出生词本",
        danger: true,
        onConfirm: () => removeSavedWordById(id),
      });
      break;
    }

    case "go-wordbook":
      closeDrawer();
      navigate("wordbook");
      break;

    case "go-settings":
      closeModal({ runCallback: false });
      closeDrawer();
      navigate("settings");
      break;

    case "open-help":
      openHelpModal();
      break;

    case "close-modal":
      closeModal();
      break;

    case "confirm-modal": {
      const callback = state.confirmCallback;
      closeModal({ runCallback: false });
      if (typeof callback === "function") await callback();
      break;
    }

    case "wordbook-filter": {
      state.wordbookStatus = element.dataset.status || "";
      $$(".filter-tab").forEach((tab) => {
        tab.classList.toggle("active", (tab.dataset.status || "") === state.wordbookStatus);
      });
      const host = $("#wordbook-grid-host");
      if (host) host.innerHTML = renderWordbookBody();
      break;
    }

    case "clear-filters": {
      state.wordbookStatus = "";
      state.wordbookQuery = "";
      const input = $("#wordbook-search");
      if (input) input.value = "";
      $$(".filter-tab").forEach((tab) => {
        tab.classList.toggle("active", (tab.dataset.status || "") === "");
      });
      const host = $("#wordbook-grid-host");
      if (host) host.innerHTML = renderWordbookBody();
      break;
    }

    case "play-saved-word": {
      const item = state.wordbook.items.find((entry) => Number(entry.id) === Number(element.dataset.id));
      const entry = item?.data;
      if (!entry) return;
      const accent = state.boot?.settings?.learning?.accent === "uk" ? "uk" : "us";
      playAudio(entry.audio?.[accent] || entry.audio?.us || "", item.word, element);
      break;
    }

    case "toggle-mastered":
      await toggleMasteredById(Number(element.dataset.id));
      break;

    case "delete-word": {
      const item = state.wordbook.items.find((entry) => Number(entry.id) === Number(element.dataset.id));
      if (!item) return;
      openConfirm({
        title: "移出生词本？",
        message: `确定要移除 <strong>${esc(item.word)}</strong> 吗？`,
        confirmLabel: "移出",
        danger: true,
        onConfirm: () => removeSavedWordById(item.id),
      });
      break;
    }

    case "start-review":
      startReview();
      break;

    case "review-reveal":
      if (state.review) {
        state.review.revealed = true;
        renderReviewModal();
      }
      break;

    case "review-again":
      advanceReview("learning");
      break;

    case "review-known":
      advanceReview("mastered");
      break;

    case "review-skip":
      if (state.review) {
        state.review.index += 1;
        state.review.revealed = false;
        renderReviewModal();
      }
      break;

    case "review-restart":
      startReview(state.wordbook.items);
      break;

    case "review-audio": {
      if (!state.review) return;
      const item = state.review.items[state.review.index];
      if (!item) return;
      const accent = state.boot?.settings?.learning?.accent === "uk" ? "uk" : "us";
      playAudio(item.data?.audio?.[accent] || item.data?.audio?.us || "", item.word, element);
      break;
    }

    case "set-provider": {
      if (!state.settingsDraft) state.settingsDraft = buildSettingsDraft();
      const preset = (state.boot?.provider_presets || []).find((item) => item.id === element.dataset.provider);
      if (!preset) return;
      state.settingsDraft.ai.provider = preset.id;
      state.settingsDraft.ai.base_url = preset.base_url || "";
      state.settingsDraft.ai.model = preset.model || "";
      render();
      break;
    }

    case "toggle-key-visibility": {
      const input = $("#api-key-input");
      if (!input) return;
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      element.innerHTML = icon(showing ? "eye" : "eye-off");
      break;
    }

    case "clear-api-key": {
      if (!state.settingsDraft) return;
      state.settingsDraft.clearKey = true;
      state.settingsDraft.ai.api_key = "";
      render();
      break;
    }

    case "save-ai-settings": {
      const button = element;
      button.disabled = true;
      try {
        await persistSettings({ target: "ai-form-status" });
      } catch (error) {
        showFormStatus(error?.message || "设置保存失败。", "err", "ai-form-status");
        toast(error?.message || "设置保存失败。", "error");
      } finally {
        button.disabled = false;
      }
      break;
    }

    case "test-ai": {
      const button = element;
      const original = button.innerHTML;
      button.disabled = true;
      button.classList.add("loading");
      button.innerHTML = `${icon("loader")}正在测试…`;
      try {
        await persistSettings({ silent: true });
        const result = await api.testAI();
        render();
        showFormStatus(`连接成功 · ${result.model || "模型"} · ${result.latency_ms || 0}ms`, "ok", "ai-form-status");
        toast("AI 连接成功，可以开始精讲了。", "success");
      } catch (error) {
        showFormStatus(error?.message || "连接失败，请检查配置。", "err", "ai-form-status");
        toast("AI 连接失败。", "error");
        button.disabled = false;
        button.classList.remove("loading");
        button.innerHTML = original;
      }
      break;
    }

    case "export-wordbook": {
      try {
        if (typeof api.exportWordbook === "function") {
          await api.exportWordbook();
        } else {
          window.location.href = api.wordbookExportUrl;
        }
        toast("生词本已导出。", "success");
      } catch (error) {
        toast(error?.message || "导出失败。", "error");
      }
      break;
    }

    case "toggle-ai-vision": {
      if (!state.settingsDraft) state.settingsDraft = buildSettingsDraft();
      state.settingsDraft.ocr.ai_vision = !state.settingsDraft.ocr.ai_vision;
      const enabled = state.settingsDraft.ocr.ai_vision;
      try {
        await persistSettings({ silent: true });
        render();
        toast(enabled ? "AI 视觉识别已开启。" : "已关闭 AI 视觉识别。", "success");
      } catch (error) {
        toast(error?.message || "设置保存失败。", "error");
        render();
      }
      break;
    }

    case "open-language-settings": {
      try {
        await api.openLanguageSettings();
        toast("已打开 Windows 语言设置。安装 English 语言包后重启程序。", "success");
      } catch (error) {
        toast(error?.message || "无法打开系统设置。", "error");
      }
      break;
    }

    case "save-learning": {
      const button = element;
      button.disabled = true;
      try {
        await persistSettings({ target: "settings-form-status" });
      } catch (error) {
        showFormStatus(error?.message || "偏好保存失败。", "err", "settings-form-status");
        toast(error?.message || "保存失败。", "error");
      } finally {
        button.disabled = false;
      }
      break;
    }

    case "set-accent": {
      if (!state.settingsDraft) state.settingsDraft = buildSettingsDraft();
      state.settingsDraft.learning.accent = element.dataset.accent === "uk" ? "uk" : "us";
      render();
      break;
    }

    case "clear-cache": {
      try {
        await api.clearCache("all");
        toast("缓存已清除，下次查词会获取最新内容。", "success");
      } catch (error) {
        toast(error?.message || "清除失败。", "error");
      }
      break;
    }

    case "clear-wordbook": {
      openConfirm({
        title: "清空整个生词本？",
        message: `这会把目前的 <strong>${state.wordbook.stats?.total || 0}</strong> 个词条全部删除，且无法恢复。建议先导出 CSV。`,
        confirmLabel: "全部清空",
        danger: true,
        onConfirm: async () => {
          try {
            const result = await api.clearWordbook();
            state.wordbook.items = [];
            state.wordbook.stats = result?.stats || { total: 0, learning: 0, mastered: 0 };
            updateShell();
            if (state.page === "settings") render();
            if (state.page === "wordbook") render();
            toast("生词本已清空。");
          } catch (error) {
            toast(error?.message || "清空失败。", "error");
          }
        },
      });
      break;
    }

    default:
      console.warn("Unknown action:", action);
      break;
  }
}

function onDocumentKeydown(event) {
  const tag = event.target?.tagName?.toLowerCase();
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && event.target?.id === "paste-input") {
    event.preventDefault();
    const text = event.target.value;
    state.pasteText = text;
    analyzeText(text);
    return;
  }
  if (event.key === "Escape") {
    if (state.modalOpen) {
      event.preventDefault();
      closeModal();
      return;
    }
    if (state.drawer?.open) {
      event.preventDefault();
      closeDrawer();
      return;
    }
  }
  if (event.key === "Tab" && (state.modalOpen || state.drawer?.open)) {
    trapFocus(event);
  }
  if ((event.key === "Enter" || event.key === " ") && event.target?.matches?.(".word-token")) {
    event.preventDefault();
    openWord(event.target.dataset.word || "", "", state.reading?.analysis?.title || "");
  }
  if ((event.key === "Enter" || event.key === " ") && event.target?.matches?.(".word-card")) {
    event.preventDefault();
    openWord(
      event.target.dataset.word || "",
      event.target.dataset.context || "",
      event.target.dataset.sourceTitle || "",
    );
  }
  if (event.key === "Escape" && event.target?.id === "wordbook-search") {
    event.target.blur();
  }
  if (tag === "textarea" || tag === "input") return;
}

async function onDocumentInput(event) {
  const target = event.target;
  if (target.matches?.("[data-setting]")) {
    const path = target.dataset.setting;
    let value = target.value;
    if (path === "learning.voice_rate") {
      value = Number(value);
      const label = $("#voice-rate-value");
      if (label) label.textContent = `${Number(value).toFixed(2)}×`;
    }
    if (path === "ai.api_key" && value) {
      state.settingsDraft.clearKey = false;
    }
    settingsPathSet(path, value);
  }
  if (target.id === "wordbook-search") {
    state.wordbookQuery = target.value;
    const host = $("#wordbook-grid-host");
    if (host) host.innerHTML = renderWordbookBody();
  }
  if (target.id === "paste-input") {
    state.pasteText = target.value;
  }
}

async function onDocumentChange(event) {
  if (event.target?.id === "file-input") {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) await handleFile(file);
  }
}

function onDragOver(event) {
  const zone = event.target.closest?.(".dropzone");
  if (!zone || !event.dataTransfer?.types?.includes("Files")) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
  zone.classList.add("dragover");
}

function onDragLeave(event) {
  const zone = event.target.closest?.(".dropzone");
  if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("dragover");
}

async function onDrop(event) {
  const zone = event.target.closest?.(".dropzone");
  if (!zone) return;
  event.preventDefault();
  zone.classList.remove("dragover");
  const file = event.dataTransfer?.files?.[0];
  if (file) await handleFile(file);
}

boot();


