/* Pyodide worker: runs the existing Python core inside the PWA. */
/* global loadPyodide */
importScripts("../../vendor/pyodide/pyodide.js");

const DATA_DIR = "/data";
const APP_DIR = "/app";
const VENDOR_URL = new URL("../../vendor/pyodide/", self.location.href).href;
const BACKEND_ZIP_URL = new URL("../../backend.zip", self.location.href).href;

let pyodide = null;
let ready = null;
let bridge = null;
const MUTATING = new Set([
  "wordbook_add",
  "wordbook_update",
  "wordbook_delete",
  "wordbook_clear",
  "settings_save",
  "cache_clear",
  "word",
  "ai_analyze",
]);

function progress(message) {
  self.postMessage({ type: "progress", message });
}

function syncfs(populate = false) {
  return new Promise((resolve, reject) => {
    pyodide.FS.syncfs(populate, (error) => (error ? reject(error) : resolve()));
  });
}

async function boot() {
  progress("加载 Python 运行环境…");
  pyodide = await loadPyodide({
    indexURL: VENDOR_URL,
    stdout: () => {},
    stderr: () => {},
  });

  pyodide.FS.mkdirTree(DATA_DIR);
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, DATA_DIR);
  await syncfs(true);

  progress("加载 SQLite 与网络组件…");
  await pyodide.loadPackage("sqlite3", {
    messageCallback: (message) => progress(message),
    errorCallback: (message) => progress(message),
  });
  try {
    await pyodide.loadPackage("requests", {
      messageCallback: (message) => progress(message),
      errorCallback: (message) => progress(message),
    });
  } catch (error) {
    // Requests is only needed for online dictionary/AI; local features must work.
    progress(`网络组件加载失败：${String(error?.message || error)}`);
  }

  progress("解压应用核心…");
  const response = await fetch(BACKEND_ZIP_URL);
  if (!response.ok) throw new Error(`无法加载 backend.zip（HTTP ${response.status}）`);
  const zip = new Uint8Array(await response.arrayBuffer());
  pyodide.FS.writeFile("/backend.zip", zip);
  await pyodide.runPythonAsync(`
import zipfile
zipfile.ZipFile('/backend.zip').extractall('${APP_DIR}')
`);

  progress("启动本地存储与词典…");
  await pyodide.runPythonAsync(`
import json, os, sys
os.environ.update({
    'LEXIREAD_PWA': '1',
    'LEXIREAD_RESOURCE_DIR': '${APP_DIR}',
    'LEXIREAD_BASE_DIR': '${APP_DIR}',
    'LEXIREAD_STATIC_DIR': '${APP_DIR}/static',
    'LEXIREAD_BUNDLED_DATA_DIR': '${APP_DIR}/backend/data',
    'LEXIREAD_DATA_DIR': '${DATA_DIR}',
    'LEXIREAD_UPLOAD_DIR': '${DATA_DIR}/uploads',
    'LEXIREAD_DB_PATH': '${DATA_DIR}/lexiread.db',
})
sys.path.insert(0, '${APP_DIR}')
import pwa_bridge.service as service
service.init()

def __bridge_call(method, payload):
    import json
    import pwa_bridge.service as s
    data = json.loads(payload or '{}')
    try:
        if method == 'health':
            out = s.health()
        elif method == 'bootstrap':
            out = s.bootstrap()
        elif method == 'samples':
            out = s.sample_list()
        elif method == 'sample_get':
            out = s.sample_get(data.get('sample_id', ''))
        elif method == 'analyze':
            out = s.analyze(data.get('text', ''), data.get('title', ''))
        elif method == 'ai_analyze':
            out = s.ai_analyze(data.get('text', ''), data.get('title', ''), bool(data.get('force')))
        elif method == 'word':
            out = s.word_lookup(data.get('word', ''), bool(data.get('force')))
        elif method == 'wordbook_list':
            out = s.wordbook_list(data.get('status', ''), data.get('search', ''))
        elif method == 'wordbook_add':
            out = s.wordbook_add(data.get('word', ''), data.get('entry'), data.get('source', ''), data.get('source_title', ''))
        elif method == 'wordbook_update':
            out = s.wordbook_update(data.get('word_id'), data.get('status'), data.get('notes'))
        elif method == 'wordbook_delete':
            out = s.wordbook_delete(data.get('word_id'))
        elif method == 'wordbook_clear':
            out = s.wordbook_clear()
        elif method == 'wordbook_export':
            out = s.wordbook_export()
        elif method == 'settings_get':
            out = s.settings_get()
        elif method == 'settings_save':
            out = s.settings_save(data)
        elif method == 'ai_test':
            out = s.ai_test()
        elif method == 'cache_clear':
            out = s.cache_clear(data.get('kind', 'all'))
        elif method == 'ocr_clean':
            out = s.ocr_clean(data.get('text', ''))
        else:
            return json.dumps({'ok': False, 'error': f'未知方法：{method}', 'code': 'unknown_method', 'status': 400}, ensure_ascii=False)
        return json.dumps({'ok': True, 'data': out}, ensure_ascii=False)
    except s.BridgeError as exc:
        return json.dumps({'ok': False, 'error': str(exc), 'code': exc.code, 'status': exc.status}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({'ok': False, 'error': str(exc), 'code': 'bridge_error', 'status': 500}, ensure_ascii=False)
`);
  bridge = pyodide.globals.get("__bridge_call");
  progress("准备完成");
}

function ensureReady() {
  if (!ready) ready = boot();
  return ready;
}

self.onmessage = async (event) => {
  const message = event.data || {};
  if (message.type === "warmup") {
    try {
      await ensureReady();
      self.postMessage({ id: message.id, ok: true, result: { ready: true } });
    } catch (error) {
      self.postMessage({ id: message.id, ok: false, error: String(error?.message || error), code: "boot_error", status: 500 });
    }
    return;
  }
  const { id, method, args } = message;
  try {
    await ensureReady();
    const raw = bridge(method, JSON.stringify(args || {}));
    const payload = JSON.parse(raw);
    if (!payload.ok) {
      const error = new Error(payload.error || "本地服务调用失败");
      self.postMessage({ id, ok: false, error: error.message, code: payload.code, status: payload.status });
      return;
    }
    if (MUTATING.has(method)) {
      try {
        await syncfs(false);
      } catch (error) {
        self.postMessage({ id, ok: false, error: `数据保存失败：${String(error?.message || error)}`, code: "storage_sync", status: 500 });
        return;
      }
    }
    self.postMessage({ id, ok: true, result: payload.data });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String(error?.message || error), code: "worker_error", status: 500 });
  }
};
