const API_ROOT = "/api";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", payload = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

async function request(path, { method = "GET", body, headers = {}, signal } = {}) {
  const options = { method, headers: { ...headers }, signal };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("无法连接本地服务，请确认启动窗口仍在运行。", { code: "network" });
  }
  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok || (payload && payload.ok === false)) {
    throw new ApiError(
      (payload && (payload.error || payload.message)) || `请求失败（HTTP ${response.status}）`,
      {
        status: response.status,
        code: payload?.code || "http_error",
        payload,
      },
    );
  }
  return payload?.data ?? payload;
}

export const api = {
  bootstrap: () => request("/bootstrap"),
  uploadOcr(file) {
    const form = new FormData();
    form.append("image", file, file.name || "question.png");
    return request("/ocr", { method: "POST", body: form });
  },
  analyze: (text, title = "") => request("/analyze", { method: "POST", body: { text, title } }),
  aiAnalyze: (text, title = "", force = false) =>
    request("/ai/analyze", { method: "POST", body: { text, title, force } }),
  samples: () => request("/samples"),
  sample: (id) => request(`/samples/${encodeURIComponent(id)}`),
  word: (word, force = false) =>
    request(`/word/${encodeURIComponent(word)}${force ? "?force=1" : ""}`),
  wordbook: ({ status = "", search = "" } = {}) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (search) params.set("search", search);
    const suffix = params.toString() ? `?${params}` : "";
    return request(`/wordbook${suffix}`);
  },
  addWord: (word, entry, source = "", sourceTitle = "") =>
    request("/wordbook", { method: "POST", body: { word, entry, source, source_title: sourceTitle } }),
  updateWord: (id, patch) => request(`/wordbook/${id}`, { method: "PATCH", body: patch }),
  deleteWord: (id) => request(`/wordbook/${id}`, { method: "DELETE" }),
  clearWordbook: () => request("/wordbook/clear", { method: "POST" }),
  settings: () => request("/settings"),
  saveSettings: (patch) => request("/settings", { method: "PUT", body: patch }),
  testAI: () => request("/settings/test", { method: "POST" }),
  clearCache: (kind = "all") => request("/settings/clear-cache", { method: "POST", body: { kind } }),
  wordbookExportUrl: `${API_ROOT}/wordbook/export`,
};
