# SkillBouncer — Marketing / Dashboard Page

A premium, dark-themed cybersecurity landing page for **SkillBouncer** (the public face of the Estes auditor).

It is intentionally a **single self-contained HTML file** — no build step, no node_modules. Tailwind is loaded via CDN; particles, the constellation, and the animated risk gauge are vanilla JS / `<canvas>`.

## Run it

Just open the file in a browser:

```bash
open web/index.html
```

…or serve it locally if you prefer (so the CDN can warm cache):

```bash
python3 -m http.server -d web 5173
# then visit http://localhost:5173
```

## Design notes

- **Palette** — deep ink (`#04080a`) with neon green (`#00ff9d`) and cyan accents.
- **Typography** — Inter for UI, JetBrains Mono for code/eyebrows.
- **Background** — fixed `<canvas>` with floating particles, CSS-driven sweeping light beams, a top-of-page volumetric green spotlight, and a faint masked grid.
- **Hero** — gradient headline, animated constellation network under the copy, floating mono chips around it.
- **Feature cards** — gradient hairline border (revealed on hover), glowing top accent line, lifts on hover.
- **Live demo** — animated SVG risk gauge (gradient stroke green → amber → red) plus side-by-side Before / After code cards.
- **Reveal-on-scroll** — `IntersectionObserver` toggles a `.in` class on `.reveal` elements; per-element `data-d="N"` adds staggered delays.
- **Reduced motion** — all animations are disabled under `prefers-reduced-motion`.

## What lives where

| Concern              | Location in `index.html`                                |
| -------------------- | ------------------------------------------------------- |
| Color tokens         | `:root { --neon, --ink-… }` near the top of `<style>`   |
| Background canvas    | `initBgCanvas` IIFE in `<script>`                       |
| Hero constellation   | `initConstellation` IIFE                                |
| Risk gauge animation | `animateGauge` + `gaugeIO` observer                     |
| Card / button styles | `.card`, `.btn`, `.btn-primary`, `.btn-ghost`           |
| Footer nav           | bottom `<footer>` block                                 |

## Notes on the existing Streamlit app

This page lives at `web/index.html` so it does **not** interfere with the Streamlit auditor (`app.py`). They can ship side-by-side: the Streamlit app remains the working scanner, this page is the public-facing dashboard / marketing surface.
