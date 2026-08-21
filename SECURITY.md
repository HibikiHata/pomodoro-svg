# Security Policy

## Reporting a vulnerability

Report privately through GitHub's [Security Advisories](https://github.com/HibikiHata/pomodoro-svg/security/advisories/new).
Please do not open a public issue for a security problem.

Expect an initial response within a week.

## What this project touches

Knowing the boundaries is usually enough to judge whether something is a
security problem here.

- **Network.** None. The SVGs are pre-generated and committed under `dist/`;
  nothing runs on the viewer's side beyond the browser rendering an image.
- **Tokens and secrets.** None are read anywhere in the repository.
- **Dependencies.** The generator uses the Python standard library only. The
  test suite additionally needs `pytest`; `fontTools` is used once at
  development time to subset the bundled font.
- **The SVGs.** CSS animation only: no `<script>`, no external references.
  CI regenerates `dist/` and fails on any drift from the committed files.
- **Third-party Actions.** Every `uses:` in this repository is pinned to a
  full commit SHA.
