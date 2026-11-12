/* Main-thread bridge to the Pyodide worker and Tesseract.js. */

const WORKER_URL = new URL("./pyodide-worker.js", import.meta.url);

class Bridge {
  constructor() {
    this.worker = null;
    this.sequence = 0;
    this.pending = new Map();
    this.startError = null;
    this.progressHandler = null;
  }

  setProgressHandler(handler) {
    this.progressHandler = handler;
  }

  _start() {
    if (this.worker) return this.worker;
    if (this.startError) throw this.startError;
    try {
      this.worker = new Worker(WORKER_URL);
    } catch (error) {
      this.startError = error;
      throw error;
    }
    this.worker.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "progress") {
        this.progressHandler?.(message.message);
        return;
      }
      const entry = this.pending.get(message.id);
      if (!entry) return;
      this.pending.delete(message.id);
      if (message.ok) entry.resolve(message.result);
      else {
        const error = new Error(message.error || "本地服务调用失败");
        error.code = message.code || "bridge_error";
        error.status = message.status || 500;
        entry.reject(error);
      }
    };
    this.worker.onerror = (event) => {
      const error = new Error(event.message || "Python 运行环境加载失败");
      this.startError = error;
      for (const entry of this.pending.values()) entry.reject(error);
      this.pending.clear();
    };
    return this.worker;
  }

  warmup() {
    return this.call("health");
  }

  call(method, args = {}) {
    const worker = this._start();
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timeoutMs = method.startsWith("ai_") ? 240000 : 90000;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("Python 运行环境加载超时，请刷新页面重试。"));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
      worker.postMessage({ id, method, args });
    });
  }
}

export const bridge = new Bridge();
window.__LEXIREAD_BRIDGE__ = bridge;
window.__LEXIREAD_BOOT_LOG__ = [];
bridge.setProgressHandler((message) => {
  window.__LEXIREAD_BOOT_LOG__.push({ at: Date.now(), message });
});

function readAsBitmap(file) {
  if (self.createImageBitmap) return createImageBitmap(file);
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("无法读取这张图片，请换一张 JPG 或 PNG。"));
    };
    image.src = url;
  });
}

function drawPrepared(bitmap, targetWidth = 1600) {
  const scale = Math.max(0.25, Math.min(3.2, targetWidth / Math.max(1, bitmap.width)));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(bitmap, 0, 0, width, height);
  try {
    const image = context.getImageData(0, 0, width, height);
    const data = image.data;
    for (let index = 0; index < data.length; index += 4) {
      const gray = data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114;
      const value = Math.max(0, Math.min(255, (gray - 128) * 1.18 + 128));
      data[index] = value;
      data[index + 1] = value;
      data[index + 2] = value;
    }
    context.putImageData(image, 0, 0);
  } catch {
    // Canvas filters/pixel access can be restricted; Tesseract can still use color.
  }
  return canvas;
}

function drawPreview(bitmap, maxSide = 1600) {
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext("2d");
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.82);
}

export async function runOcr(file) {
  if (!file) throw new Error("请选择一张题目图片。");
  if (file.size > 30 * 1024 * 1024) throw new Error("图片超过 30MB，请压缩后再试。");
  if (typeof Tesseract === "undefined") throw new Error("OCR 组件没有加载，请刷新页面。");

  const started = performance.now();
  const bitmap = await readAsBitmap(file);
  try {
    const preview = drawPreview(bitmap);
    const prepared = drawPrepared(bitmap, 1600);
    const worker = await Tesseract.createWorker("eng", 1, {
      workerPath: new URL("../../vendor/tesseract/worker.min.js", import.meta.url).href,
      corePath: new URL("../../vendor/tesseract/", import.meta.url).href,
      langPath: new URL("../../vendor/tesseract/lang/", import.meta.url).href,
      cacheMethod: "none",
      workerBlobURL: false,
      gzip: true,
    });
    let text = "";
    try {
      const result = await worker.recognize(prepared, {}, { blocks: true });
      const lines = [];
      if (Array.isArray(result?.data?.lines) && result.data.lines.length) {
        lines.push(...result.data.lines);
      } else {
        for (const block of result?.data?.blocks || []) {
          for (const paragraph of block.paragraphs || []) {
            for (const line of paragraph.lines || []) lines.push(line);
          }
        }
      }
      const heading = lines.findIndex((line) =>
        /^\s*(?:passa\w*\s*\d?|reading comprehension)\s*[;:.]?\s*$/i.test(line.text || ""),
      );
      if (heading > 0) {
        text = lines.slice(heading).map((line) => line.text || "").join("\n");
      } else {
        text = result?.data?.text || "";
      }
    } finally {
      await worker.terminate().catch(() => {});
    }
    text = await bridge.call("ocr_clean", { text });
    if ((text.match(/[A-Za-z]/g) || []).length < 10) {
      throw new Error("图片中的英文太少，未能识别出可用题目。请确认图片清晰并包含完整文字。");
    }
    return {
      text,
      meta: {
        engine: "Tesseract.js",
        language: "eng",
        english_available: true,
        ai_vision: false,
        duration_ms: Math.round(performance.now() - started),
      },
      preview_url: preview,
      original_name: file.name || "question.png",
    };
  } finally {
    bitmap.close?.();
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export async function exportWordbook() {
  const csv = await bridge.call("wordbook_export");
  downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), "lexiread-wordbook.csv");
  return true;
}

export async function openLanguageSettings() {
  throw new Error("PWA 版本使用 Tesseract.js，不需要安装 Windows 语言包。");
}

window.__LEXIREAD_RUN_OCR__ = runOcr;
