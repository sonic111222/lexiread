# Bundled dictionary data

- `ecdict_subset.json.gz` — 26,000 frequency-ordered ECDICT entries with
  Chinese translations, phonetics, exam tags and word forms.
- `words_frequency.txt` — a 25,995-word frequency list used for conservative
  OCR word-splitting cleanup.
- `ECDICT_LICENSE.txt` — upstream MIT license.

Source: <https://github.com/skywind3000/ECDICT>  
License: MIT (see `ECDICT_LICENSE.txt` and `LICENSES/ECDICT.txt`)

These are reduced versions generated from the upstream CSV for offline use.
They are not a complete dictionary and are not intended to be redistributed as
a standalone dictionary product.

Regenerate from an ECDICT checkout:

```bat
python tools/build_ecdict_subset.py path\to\ecdict.csv
```

Do not add scraped dictionaries, proprietary dictionary data or unlicensed
audio to this directory.
