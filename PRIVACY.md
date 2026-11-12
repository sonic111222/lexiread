# Privacy

LexiRead is a local-first desktop app. This document describes what the
open-source build does by default.

## Data kept on this computer

- `data/lexiread.db`: wordbook, settings, dictionary cache, AI cache
- `data/uploads/`: normalized images you upload (for "view original image")
- Browser `localStorage`: the last reading you opened, reading font size

Removing `data/lexiread.db` resets the wordbook and settings. Removing
`data/uploads/` removes the local image copies. Uninstalling the app without
removing these files leaves them on disk.

## Network requests

The app does not include analytics or telemetry.

| Action | Data sent | Destination |
| --- | --- | --- |
| OCR (default) | Nothing; image stays local | Tesseract or Windows OCR on this computer |
| OCR with "AI 视觉识别" enabled | The exam image (compressed JPEG) | The OpenAI-compatible endpoint you configured |
| Point at a word not in the offline dictionary | The word/phrase | `api.dictionaryapi.dev` (Wiktionary data) |
| Click "AI 精讲" | The passage, questions and options | The OpenAI-compatible endpoint you configured |
| Play an audio sample returned by the online dictionary | The word/phrase and media request | The audio host returned by that provider |
| Open a source/credits link | Normal browser request | The linked site |

AI vision recognition is off by default. It is only used after you enable it in
Settings, and it automatically falls back to the local Windows OCR engine if
the request fails.

The bundled ECDICT subset covers many common words and is fully offline.
The online lookup only happens when the offline dictionary has no entry.

## PWA (browser) edition

The installable PWA has no backend server. The Python core runs in the browser
via Pyodide, OCR uses Tesseract.js, and dictionary/wordbook/settings data is
stored in browser storage (IndexedDB/IDBFS, exposed as a local SQLite file).
Nothing is uploaded unless you enable an online feature.

- Clearing the site's browser storage deletes the wordbook and settings.
  Export a CSV first if you need a backup.
- AI requests from the PWA go directly from the browser to the provider you
  configured. The API key is kept in browser storage and may be exposed to
  scripts running on that origin; use a dedicated key. Some providers block
  browser CORS requests, in which case AI is unavailable in the PWA.
- AI vision OCR is not available in the PWA; it uses local Tesseract.js only.
- iOS may evict unused site data. Export regularly.

## AI keys

Your AI API key is stored in `data/lexiread.db` in plain text. It is not sent to
the browser or included in API responses, but anyone with access to your user
account and that file can read it. Use a dedicated key with a spending limit,
and do not use the app on a shared computer if that is a concern.

## Children and exam content

The project is intended for general English reading practice, not for K-12
photo-search homework services. Do not upload personal information or
third-party copyrighted material that you do not have the right to process.

## Contact

For privacy or security issues, open a private GitHub security advisory rather
than posting sensitive details in a public issue.
