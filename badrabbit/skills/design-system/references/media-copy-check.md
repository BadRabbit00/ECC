# Responsive check, media, copy

## Responsive and the screenshot check
- Widths: **375, 768, 1024, 1440** (first screen also 390 × 844). Phone layout from ~860–900 px; shorten the menu at 900–1100 px.
- Type and spacing via `clamp()`; full-screen blocks `100svh`; scalable slides in container units (`cqw`).
- Phone: first-screen text at the bottom; buttons stacked full width (hide the secondary if it does not fit); sticky scenes become sequential (photo above each step); ribbons `scroll-snap`; touch targets ≥ 44 px; inputs 16 px.
- No horizontal page scroll ever: `document.documentElement.scrollWidth <= innerWidth` at every width.
- Before showing: headless Chromium or Playwright, screenshots of the first screen and the full page after animations (or with reduced motion). Look for overflow and overlaps, orphaned words in headings, photo crops, text contrast on photos, the header at top and after scroll, the open mobile menu, the form error state, console errors.
- For sites and interfaces the four widths are mandatory for every visual change, small ones included (for a small change, screenshot the touched block). Documents and slides: see `documents-slides.md`.
- When reporting, name the widths checked.

## Photos and video
- Priority: the client's real photos and video → generated as one series → stock NEVER (especially smiling people and handshakes). Poor real material → say so and offer a way out (another crop, a triptych of vertical shots); never silently AI-upscale.
- One series: one light (direction, warmth), one palette, one background. Illustration on a coloured page: image background equals the page (adjust in post), edges softened with a 6–14% mask; graphics on "paper" via `mix-blend-mode: multiply`. Generated images have no text, logos, or watermarks; check every one for artefacts (fingers, paired-object symmetry, counts of small details, merged elements, crooked lettering) and discard flawed ones; tone down AI oversaturation.
- Technique: WebP or AVIF, `srcset` and `sizes` (≥ ~1280 and ~2560 px for full-screen), `loading="lazy"` below the first screen, `fetchpriority="high"` for the first-screen poster, `width`/`height` or `aspect-ratio`, a colour placeholder while loading. Ratios: product 1:1 or 4:5; wide 3:2 or 16:9; vertical 9:16. `object-fit: cover` with a deliberate `object-position` per layout.
- Video: background video only where it carries meaning (usually the home first screen); inner pages use topical photos; the same clip on every page — NEVER. `muted autoplay loop playsinline`, `poster`, WebM (VP9) + MP4 (H.264), 1–4 MB per 8–15 s loop, a phone version, a pause button. Hard cuts and one soft grade only; no transitions, zooms, shake, titles, logos, sound. Seamless loops: nature with a crossfade, small human movement as forward-backward; motion must be noticeable.

## Copy
- The heading says what the company does or what the block is about; the lead says what the client gets and how.
- One sentence, one thought; a lead at most two lines; a product description 2–3 sentences.
- NEVER: metaphorical slogans in headings, puns on the brand name, exclamation marks, shouting caps, empty superlatives («премиальный», «эксклюзивный», «лучший», «инновационный»).
- Mood comes from photos, composition, and motion, not words.
- Client documents are a draft: take the facts, rewrite for the block. Agreed copy is not changed without asking. Numbers and facts only from sources; conflicting sources → ask.

| Do | Not |
|---|---|
| Ремонтируем ноутбуки за один день, диагностика бесплатно. | Технологии, которые вдохновляют! |
| Привезём заказ завтра до 12:00. | Название, которое говорит само за себя. |
| Спасибо, заявка у нас. Менеджер напишет в течение часа. | Ваша заявка принята в обработку. Ожидайте. |
| Смотреть каталог | Узнать больше |
