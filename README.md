# PediAid Landing

Single-page, frosted-glass landing site for the PediAid platform.

**Live URL:** https://mulgundsunil1918.github.io/pediaid-landing/

## What it is

A static marketing / overview page for **PediAid — Paediatric & Neonatal
Clinical Reference**. Explains what's inside, links to the live web app,
and holds placeholders for the Play Store and App Store buttons (links to
be added on launch).

## Tech

Plain static HTML + CSS — no build step, no JS framework.

- Inter font (matches `pediaid-frontend`)
- PediAid colour palette (`#1e3a5f` navy, `#3182ce` accent, etc.)
- Frosted-glass cards via `backdrop-filter: blur(...)`
- Animated radial-gradient background
- Fully responsive (1180 / 880 / 560 / 480 breakpoints)
- Reduced-motion respected via `prefers-reduced-motion`

Deploys via the `deploy.yml` workflow in `.github/workflows/`
(GitHub Pages, `actions/deploy-pages@v4`).

## Local preview

Just open `index.html` in a browser.

## Updating store links

Search for `data-store="play"` and `data-store="apple"` in `index.html`.
Replace the `href="#"` and remove the `aria-disabled` attribute and
`onclick` handler when the real links are ready.
