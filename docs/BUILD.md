# Building a Windows portable release

The repository includes `lexiread.spec` and `build_windows.bat`. The resulting
build is a single `LexiRead.exe`; the app creates its own `data/` directory next
to the executable on first run.

## Local build

```bat
build_windows.bat
```

Or manually:

```bat
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --clean --noconfirm lexiread.spec
```

Output: `dist\LexiRead.exe` (roughly 40–60 MB).

For a clean, reproducible build use a fresh virtual environment. Building from
a large global Python installation can accidentally pull unrelated packages.

## Publish from GitHub Actions

`.github/workflows/build-windows.yml` builds a zip on:

- a version tag such as `v0.1.0`
- manual `workflow_dispatch`

The zip contains the executable plus README, license, privacy and third-party
notice files. It is uploaded as a workflow artifact and attached to a GitHub
Release when the workflow runs on a tag.

## Code signing

The build is unsigned by default. Windows SmartScreen may warn users. If the
project grows, sign releases with a Windows code-signing certificate and keep
the certificate outside the repository. Do not upload signing keys or
passwords to GitHub Secrets unless the release workflow explicitly requires
them.

## Release checklist

- [ ] Update `CHANGELOG.md`
- [ ] Bump the version/tag
- [ ] Run `python -m unittest discover -s tests -v`
- [ ] Build from a clean virtual environment
- [ ] Test the exe on a clean Windows folder
- [ ] Verify OCR, local dictionary lookup and “new reading” flow
- [ ] Verify the zip does not contain `data/lexiread.db`, API keys or uploads
- [ ] Upload the zip and publish release notes
- [ ] Verify README and release links point to the real GitHub repository path
