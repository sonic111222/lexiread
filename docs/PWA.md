# LexiRead PWA（跨平台版）

LexiRead PWA 用一个代码库覆盖 **Windows、macOS、Android、iPhone、iPad**：
它是可离线安装的网页应用，Python 核心通过 Pyodide 在浏览器里运行，OCR 使用
Tesseract.js，数据保存在浏览器本地的 SQLite（IndexedDB）中。

> 这是 PWA 跨平台版，不是 App Store / Play Store 的原生安装包。原生 APK/IPA/dmg
> 需要 Android SDK、Mac + Xcode 和 Apple 签名，当前仓库暂不提供。

## 构建

需要 Python 3.10+ 和网络（仅首次下载依赖）。

```bat
python tools/fetch_pwa_vendor.py
python tools/build_pwa.py
```

产物在 `dist_pwa/`，约 24 MB（Pyodide + Tesseract.js + ECDICT）。

本地预览：

```bat
python pwa/serve_pwa.py
```

打开 `http://127.0.0.1:8080/`。`localhost` 是安全上下文，可以直接测试 Service
Worker 和安装。

## 部署与安装

PWA 安装和 Service Worker 需要 **HTTPS**。把 `dist_pwa/` 整个目录上传到任意静态
主机即可，不需要服务器端 Python：

- GitHub Pages
- Cloudflare Pages
- Netlify / Vercel
- 自己的 Nginx / IIS（配置 HTTPS）

安装方式：

| 平台 | 操作 |
| --- | --- |
| Windows | Edge/Chrome 地址栏右侧「安装」图标，或菜单 → 应用 → 安装此站点 |
| macOS | Safari 文件 → 添加到程序坞；Chrome 地址栏「安装」 |
| Android | Chrome 菜单 → 安装应用 / 添加到主屏幕 |
| iPhone/iPad | Safari 分享 → 添加到主屏幕（必须 HTTPS） |

首次打开需要下载约 24 MB 资源并初始化 Python，通常 3–10 秒；之后 Service Worker
会缓存全部资源，断网也能启动。

## 功能与边界

已对齐桌面版：

- OCR 校对：Tesseract.js 英文识别 + 现有 OCR 纠错规则
- 阅读排版、题目拆分、点词查询、词形/音标/释义
- 生词本增删、搜索、学习/已掌握、CSV 导出
- 内置示例、设置、学习偏好、离线词典
- 本地 SQLite 存储（在浏览器 IndexedDB 中），刷新/重启后保留

PWA 版限制：

- **AI 视觉识别不可用**：浏览器里没有 Pillow/Windows OCR；OCR 走 Tesseract.js。
- **AI 精讲直连服务商**：受浏览器 CORS 限制，部分服务商可能无法从 PWA 调用；
  密钥保存在浏览器本地，请使用专用 Key。桌面完整版仍通过本地 Python 转发。
- OCR 在手机上约 10–30 秒，弯曲书页仍可能串行；建议拍照时压平页面或裁剪到正文。
- iOS 可能清理长期不用的站点数据；请定期用「导出 CSV」备份生词本。
- 浏览器存储上限通常足够（约 32 MB 缓存 + 文章数据），清理站点数据会清空生词本。

## 数据与隐私

- 图片、OCR、词典、生词本都在浏览器本机处理；PWA 没有后端。
- 只有你点击「AI 精讲」并配置了 API 时，文章文本才会发送给服务商。
- 在线词典只在离线词库未收录时请求 `api.dictionaryapi.dev`。
- 清除浏览器站点数据 = 删除 PWA 本地数据；请先导出。

## 开发提示

- `pwa/js/pyodide-worker.js`：Pyodide、IDBFS、SQLite、Python RPC。
- `pwa/js/bridge.js`：主线程 RPC、Tesseract.js OCR、CSV 导出。
- `pwa/js/api-pwa.js`：与 Flask API 相同的 `api` 对象。
- `pwa_bridge/service.py`：复用 `backend/` 的服务层，不导入 Flask/Windows OCR。
- `tools/build_pwa.py` 会生成 manifest、Service Worker、图标，并把
  `backend.zip` 打包进 `dist_pwa/`。
- 修改 `pwa/js/*.js` 后必须重新构建；Service Worker 缓存版本会随构建变化。
- 若要调试启动，可在浏览器控制台查看 `window.__LEXIREAD_BOOT_LOG__`。
