# HTML documents, guides, presentations

## HTML documents, guides, reports
- ALWAYS two themes, light and dark: the system theme by default (`prefers-color-scheme`) plus a switch; the choice stored in `localStorage` (wrapped in `try/catch`). Both themes are full token sets. Dark background not pure black (lightness 5–8%), text not pure white (90–93%), accent lightened to pass contrast.
- Neutral styling: light background, Inter, Golos Text, or the system font, one accent. With a brand book and a branded document: accent from the brand book; otherwise purple by default. Service documents (references, reports, specs) are NEVER in the product's brand colours with brand caps; brand fonts and colours only inside samples.
- Text column 720–800 px, body 17–18 px with 1.65–1.7 line height. From 1024 px a sticky TOC on the left (220–260 px) highlighting the current section; headings with `scroll-margin-top`.
- Content: real tables, SVG diagrams, monospace 14 px code blocks, callouts, expandable answers with `<details>`.
- Print: `@media print`, A4, margins 16–18 mm, `break-inside: avoid` for sections, `print-color-adjust: exact`, no controls.
- Offline needed → one file: woff2 fonts and WebP images embedded by a build script. Check: no external URLs in the result (search for `http`) except source links.

```css
/* Default accent for a document without a brand book — purple */
:root { --bg:#FAFAFC; --ink:#1C1A24; --muted:#5F5B70; --line:#E3E1EA; --accent:#6A3FD6; --accent-soft:#EEE8FD; color-scheme: light; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --bg:#0E0D13; --ink:#EBE9F3; --muted:#A6A2B8; --line:#2D2B38; --accent:#A98BFA; --accent-soft:#251D40; color-scheme: dark; }
}
:root[data-theme="dark"] { --bg:#0E0D13; --ink:#EBE9F3; --muted:#A6A2B8; --line:#2D2B38; --accent:#A98BFA; --accent-soft:#251D40; color-scheme: dark; }
```

## Learning and reference material (mini-guide)
When asked to explain a topic, write up lectures, or make a reference or study notes: by default **one local HTML file** next to the sources; publish only on request.
- **Language**: plain, detailed, explanatory. NEVER a compressed retelling or a literal translation: the reader must understand the material.
- **Structure**, in order: title and 1–2 lines on what and for whom → TOC (at the top, and sticky on the left from 1024 px) → sections: explanation → example → real-life analogy → common mistakes («как думают неправильно» → «как правильно») → self-check with answers in `<details>` → cheat sheet (everything important on one screen) → glossary (for foreign sources: original term → translation → short explanation), sources.
- **Examples** are real HTML tables, SVG diagrams, code blocks. Images of text and screenshots of tables — NEVER.
- **Styling** per the document rules above; callouts «ошибка», «запомни», «пример» with their own soft token backgrounds.
- **Before handing over**: headless screenshots in both themes at 375 and 1440 (tables and diagrams fit; wide tables scroll inside their block), `<details>` work, TOC anchors land.

## Presentations (HTML)
Use the BR template (`~/.claude/br/templates/slides.html`) through the `presenter` agent; it implements these rules:
- One HTML file, 16:9 slides scaled with `container-type: inline-size` and `cqw` units.
- Controls: ←/→, Space, PageUp/PageDown, Home/End, click on the left/right half, swipe; F for fullscreen; slide number in `#hash`; a 3 px progress bar and a `03 / 10` counter; a control panel on mouse move, hidden in fullscreen.
- A slide has a heading, chip theses, a diagram, an image. The full talk is a separate document in the same typography: per slide number, heading, 40–60 s (≈ 90–120 words), an «на слайде →» hint, sources at the end.
- A service line on every slide: `NN / SECTION` left, topic right, a thin line below; equal margins (~4cqw).
- "Paper" background (warm near-white) with a faint grid or dots (opacity 0.04–0.08, step 1.2–2.5cqw).
- One accent; when two entities are compared, each keeps its own colour on every slide.
- Diagrams draw in on entry: bars with `scaleX` from the left, lines with `stroke-dashoffset` using a length measured in JS (`pathLength="1"` is unreliable).
- Element reveal: `opacity` + `translateY(~1cqw)`, 320–520 ms, `--ease-out`, step 50–70 ms; reduced motion → opacity only.
- Print: `@page { size: 1600px 900px; margin: 0 }`, one slide per page, everything in the final state, controls hidden; fallback PDF via headless Chromium.
- Check: a screenshot of every slide at 1600 × 900 and in a narrow window — nothing overflows or overlaps.
