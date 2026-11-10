# Security policy

## Reporting a vulnerability

Please use GitHub's private **Security → Report a vulnerability** flow for this
repository. Do not post API keys, personal data or exploit details in a public
issue.

## Scope

LexiRead runs a local HTTP server bound to `127.0.0.1`. Relevant issues include:

- path traversal or arbitrary file read through uploads
- XSS involving analysis, dictionary or AI content
- command injection in the OCR bridge
- unintended outbound requests or leakage of local files
- credential exposure in logs, responses or repository history

## Secrets

The app does not ship with an AI key. Users provide their own key through the
local settings UI; it is stored in the local SQLite database. Never commit
`data/lexiread.db`, `.env` files or screenshots containing a key.

## Supported versions

Security fixes are applied to the latest release and `main`. There is no
long-term support branch for pre-release versions.
