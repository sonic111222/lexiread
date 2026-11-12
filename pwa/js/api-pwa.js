/* PWA API adapter: same surface as the Flask-backed api.js. */
import { bridge, exportWordbook, openLanguageSettings, runOcr } from "./bridge.js";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", payload = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

async function call(method, args = {}) {
  try {
    return await bridge.call(method, args);
  } catch (error) {
    throw new ApiError(error?.message || "本地操作失败", {
      status: error?.status || 0,
      code: error?.code || "bridge_error",
    });
  }
}

export const api = {
  bootstrap: () => call("bootstrap"),
  uploadOcr: (file) => runOcr(file),
  analyze: (text, title = "") => call("analyze", { text, title }),
  aiAnalyze: (text, title = "", force = false) => call("ai_analyze", { text, title, force }),
  samples: () => call("samples"),
  sample: (id) => call("sample_get", { sample_id: id }),
  word: (word, force = false) => call("word", { word, force }),
  wordbook: ({ status = "", search = "" } = {}) => call("wordbook_list", { status, search }),
  addWord: (word, entry, source = "", sourceTitle = "") =>
    call("wordbook_add", { word, entry, source, source_title: sourceTitle }),
  updateWord: (id, patch) => call("wordbook_update", { word_id: id, status: patch?.status, notes: patch?.notes }),
  deleteWord: (id) => call("wordbook_delete", { word_id: id }),
  clearWordbook: () => call("wordbook_clear"),
  settings: () => call("settings_get"),
  saveSettings: (patch) => call("settings_save", patch),
  testAI: () => call("ai_test"),
  clearCache: (kind = "all") => call("cache_clear", { kind }),
  exportWordbook: () => exportWordbook(),
  openLanguageSettings: () => openLanguageSettings(),
  wordbookExportUrl: "",
};

window.__LEXIREAD_PWA__ = true;
