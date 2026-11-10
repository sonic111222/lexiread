# Contributing

Thanks for helping LexiRead. This project is intentionally small, local-first
and easy to run.

## Development setup

```bat
python -m pip install -r requirements-dev.txt
python app.py
```

The app opens at `http://127.0.0.1:5057`. If that port is busy, check the
startup log for the selected port.

Run the tests:

```bat
python -m unittest discover -s tests -v
```

## Project layout

- `backend/analyzer.py` — parsing reading/cloze text into paragraphs, questions,
  vocabulary, phrases and key sentences.
- `backend/ocr.py` — Windows OCR bridge, image normalization and conservative
  OCR cleanup.
- `backend/dictionary.py` — cache/fallback service.
- `backend/providers/` — interchangeable dictionary sources.
- `backend/ai.py` — optional OpenAI-compatible structured analysis.
- `static/js/app.js` — single-page UI.
- `backend/data/` — licensed offline data and license texts.

## Adding a dictionary provider

1. Add a class implementing `backend.providers.base.DictionaryProvider`.
2. Return the normalized entry shape used by `backend.providers.ecdict`.
3. Never bundle scraped web data or an API key.
4. Include source, license and attribution fields.
5. Register the provider in `backend/providers/__init__.py`.
6. Add a test using offline fixture data where possible.

Providers must not silently make network requests during import. Network
providers should fail soft and let the service try the next provider.

## Data and privacy rules

- Do not commit `data/lexiread.db`, `data/uploads/`, API keys or personal data.
- Do not add unlicensed dictionaries, exam papers, textbooks or audio.
- If you add a data source, add its attribution to `THIRD_PARTY_NOTICES.md`.
- Keep local OCR as the default; AI must remain opt-in.

## Licensing of contributions

The project is source-available under the PolyForm Noncommercial License 1.0.0.
By submitting a pull request, you agree that your contribution is licensed to
the project under the same license. Do not contribute code, data or media you
cannot license on those terms.

Do not add telemetry, accounts, payment code or AI keys without a separate
design discussion.

## Pull requests

- Keep changes focused and explain the user-facing effect.
- Run `python -m pyflakes app.py backend` if available and the test suite.
- Update `README.md` / `CHANGELOG.md` for visible changes.
- Screenshots are welcome for UI changes.

## Scope

Useful contributions include:

- Windows OCR accuracy improvements (without uploading images)
- reading/cloze parser edge cases
- a licensed dictionary provider
- keyboard/accessibility improvements
- portable Windows build/release tooling
- tests for analyzer and provider behavior

Please avoid adding telemetry, accounts, payment code or AI keys to the
public-source client without a separate design discussion.
