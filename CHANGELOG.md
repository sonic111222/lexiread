# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added

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
- OCR word correction now uses a frequency list derived from ECDICT (MIT).
- The public-source client works with no AI key; AI remains an opt-in feature.

### Fixed

- AI prompt input is capped instead of silently exceeding the model context.
- Download/cache handling now uses a versioned provider cache namespace.
