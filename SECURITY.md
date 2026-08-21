# Security Policy

## Reporting a vulnerability

Report privately through GitHub's [Security Advisories](https://github.com/HibikiHata/pomodoro-svg/security/advisories/new).
Please do not open a public issue for a security problem.

You will get an acknowledgment within 7 days.

After triage I will confirm or decline the report, develop a fix privately,
and publish a security advisory crediting you (unless you prefer otherwise)
once a fixed release is out. This is a solo-maintained project; complex fixes
may take a few weeks.

## Supported versions

Only the latest release (and the moving `v1` tag that follows it) is
supported. Fixes are not backported.

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

## Out of scope

- Vulnerabilities in GitHub Actions itself or in the third-party actions this
  repository pins — report those upstream.
- A dependency version with a known CVE, unless the vulnerable code is
  actually reachable from this project.
- Anything that requires write access to this repository or a compromised
  workflow token.

If you used AI tools to find or write up the issue, say so, and verify the
proof of concept reproduces before reporting. Unverified machine-generated
reports are closed without response.
