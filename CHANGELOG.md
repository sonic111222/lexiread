# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added

- Installable cross-platform PWA (`dist_pwa/`): Windows/macOS/Android/iOS/iPadOS,
  offline-capable, with the existing Python core running through Pyodide and
  Tesseract.js for local OCR. See `docs/PWA.md`.
- PWA build tooling: `tools/fetch_pwa_vendor.py`, `tools/build_pwa.py`,
  `pwa/serve_pwa.py`, manifest/service worker/icon generation.
- Optional Tesseract English OCR runtime (`runtime/tesseract`) that works
  without a Windows language pack. The app prefers it for English photos and
  falls back to Windows OCR when it is absent.
- Optional AI vision recognition for photographed pages. Off by default; sends
  the compressed image to the configured OpenAI-compatible endpoint and falls
  back to local OCR on failure.
- Settings and the OCR review dialog now warn when no English OCR language pack
  is installed, with a button that opens the Windows language settings.
- Multi-scale local OCR pre-processing and dictionary-based repair for common
  photo errors (split/joined words, `rn/m`, `l/i`, digit lookalikes and
  full-width punctuation).
- Offline English-Chinese dictionary based on an ECDICT subset (26,000 common
  entries) with Chinese definitions, phonetics, exam tags and word forms.
- Replaceable dictionary provider architecture; Wiktionary is used only as an
  online fallback when the local dictionary has no entry.
- Source-available PolyForm Noncommercial license, author/copyright notice,
  privacy/security/contribution docs and third-party notices.
- GitHub Actions test workflow.
- Settings now shows the active dictionary sources and their licenses.

### Changed

- Removed the bundled unlicensed dictionary endpoint/audio dependency from the
  default lookup path. Browser speech is used when no licensed audio is
  available.
- OCR word correction now uses a frequency list derived from ECDICT (MIT) plus
  ECDICT's exact inflected forms, while leaving names, dates and clean prose
  untouched.
- Windows OCR now prefers any installed `en-*` recognizer instead of falling
  back silently to the Chinese engine, and runs three pre-processed scales in
  parallel.
- The public-source client works with no AI key; AI remains an opt-in feature.

### Fixed

- `build_windows.bat` and `start.bat` now use CRLF so double-clicking works.
- The Windows release zip now includes the external Tesseract runtime when present.
- PWA reading persistence no longer stores large data-URL previews in localStorage.
- OCR cleanup no longer corrupts contractions such as `I'll`.
- PWA settings copy is platform-aware and no longer claims Windows-only behavior.
- AI prompt input is capped instead of silently exceeding the model context.
- Download/cache handling now uses a versioned provider cache namespace.
