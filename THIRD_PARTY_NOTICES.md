# Third-party notices

LexiRead is licensed under the PolyForm Noncommercial License 1.0.0 (see
LICENSE and NOTICE). It also uses the following third-party software, data and
services. Their licenses remain in effect for their respective parts; the
project license does not override them.

## Bundled data

### ECDICT

- Files: `backend/data/ecdict_subset.json.gz`, `backend/data/words_frequency.txt`
- Source: https://github.com/skywind3000/ECDICT
- License: MIT
- Full text: `LICENSES/ECDICT.txt`
- Notes: the bundled files are a reduced, frequency-ordered subset generated
  from the project's CSV data for offline lookup and OCR word correction.
  The upstream repository contains data assembled from multiple historical
  sources and community contributions; keep the upstream attribution when
  redistributing.

## Icons

### Lucide

- Files: SVG icon paths in `static/index.html`
- Source: https://lucide.dev
- License: ISC, with portions derived from Feather under MIT
- Full text: `LICENSES/Lucide.txt`

## Runtime dependencies

These packages are installed from PyPI by `requirements.txt`; their own
license files accompany the installed packages. The portable Windows build
also ships their full license texts in
`LICENSES/PYTHON_DEPENDENCIES.txt` and `LICENSES/Python.txt`.

| Package | License | Source |
| --- | --- | --- |
| Flask | BSD-3-Clause | https://flask.palletsprojects.com/ |
| Werkzeug | BSD-3-Clause | https://werkzeug.palletsprojects.com/ |
| Jinja2 | BSD-3-Clause | https://jinja.palletsprojects.com/ |
| MarkupSafe | BSD-3-Clause | https://github.com/pallets/markupsafe |
| itsdangerous | BSD-3-Clause | https://github.com/pallets/itsdangerous |
| click | BSD-3-Clause | https://github.com/pallets/click |
| blinker | MIT | https://github.com/pallets-eco/blinker |
| requests | Apache-2.0 | https://requests.readthedocs.io/ |
| urllib3 | MIT | https://urllib3.readthedocs.io/ |
| certifi | MPL-2.0 | https://github.com/certifi/python-certifi |
| charset-normalizer | MIT | https://github.com/jawah/charset_normalizer |
| idna | BSD-3-Clause | https://github.com/kjd/idna |
| Pillow | HPND | https://python-pillow.org/ |
| Python | PSF-2.0 | https://www.python.org/ |

## Data services

### Wiktionary / Free Dictionary API

- Used when a word is not present in the bundled offline dictionary.
- Endpoint: https://api.dictionaryapi.dev/
- Content source: https://en.wiktionary.org/
- Wiktionary text is available under CC BY-SA; individual quotations, audio
  files and media may carry additional terms. The app displays the source name
  and links back to Wiktionary when this provider is used.
- Do not bulk-scrape this service. API responses are cached locally per lookup.

### AI providers

AI is optional and requires the user's own API key. The project does not ship
or proxy any API key. Requests go directly from the local application to the
provider selected by the user; that provider's terms and privacy policy apply.

## Sample content

The built-in reading and cloze samples in `backend/samples.py` were written for
this project and are covered by the project's PolyForm Noncommercial license.

## Windows OCR

OCR uses the OCR engine included with Windows via the PowerShell bridge in
`tools/windows_ocr.ps1`. Windows and its OCR language components remain subject
to Microsoft's terms.
