# Layout and components

## Grid, spacing, radii, shadows
- Container up to 1440 px (1680 px for photo-led shop fronts), 12 columns, gutter 24 px (16 px on phones), side padding `clamp(20px, 3.4vw, 48px)`.
- Spacing scale 4, 8, 12, 16, 24, 32, 48, 64, 96, 128 (multiples of 8; 4 and 12 only for small things).
- Section vertical padding `clamp(96px, 11vw, 168px)` desktop, 64–72 px phone. Label → heading 14–28 px; heading → lead 14–28 px; lead → content 40–96 px.
- Asymmetric section header: label or number in columns 1–3, heading and lead in 4–12; or text in 1–6 and media in 7–12 offset vertically.
- **One radius system per project**, in tokens: A — square photos, cards, fields + pill `999px` buttons, chips, filters; or B — 4–8 px everywhere, buttons included. No other radii (exceptions: a phone frame in a mock-up 32–42 px, avatars 50%).
- **Shadows** off by default: objects separate by background change and a 1 px line. Only floating layers (dropdown, popover, card over a photo, phone mock-up) get one soft shadow with negative spread, e.g. `0 24px 60px -20px rgb(0 0 0 / .35)`. NEVER a default shadow on every card.
- Lines 1 px, text colour at 10–20% opacity; thicker borders only as a meaningful accent.

## Block composition
- Each block: one task, one main element (photo, number, or heading), one main action. Reading order: label → heading → lead → content → action.
- Layering moves, 1–2 per block:
  - a photo reaching into the neighbouring block or under a text card (overlap 40–120 px);
  - a text card over a photo: light panel, thin double frame (1 px outside + a second line inside at 6 px) — when such a frame fits the domain (certificate, product passport, tag);
  - alternating asymmetry: rows 46/54 and 54/46, the photo switching sides;
  - sticky media + scrolling steps: media `position: sticky; top: 14vh; height: ~72vh`, each step `min-height: 50–56vh`, inactive steps at 0.25–0.35 opacity, the active one highlighted with the accent;
  - a ribbon: section cover on the left, a moving row of objects on the right, edge fading with a 24–32 px mask;
  - a full-width photo with directional darkening and text in a lower corner;
  - contrast of scale: a huge heading or number next to a small caption;
  - rhythm of light and dark sections, a dark finale before the footer;
  - one domain detail (a "handwritten" note, a drawing line, a material sample), at most once per screen.
- **Numbers** belong in the story: "before → after" large with an arrow, timeline points, a number inside a heading, a caption on a photo. Standalone: large (52–92 px, 500, `tabular-nums`) on a thin line, caption below, at most three in a row, no tiles, backgrounds, or icons. NEVER a first-screen row of four "number + caption" cards. Numbers only real, with a source.
- **First screen**: shows the product or service itself (real photo or video). Heading = what the company does, plainly; lead = what the client gets; one filled button, at most one secondary. Desktop text in the less detailed half with darkening; phone text at the bottom. Height `100svh`, `min-height: 600–640px`. No widgets, HUD captions, fake order cards, tickers over media; interactivity only if it sells (hotspots opening a mini product card).
- **Numbering** 01, 02… only where order matters (steps, stages, timelines), not on every section.

## Buttons and CTAs
- Primary: filled (text or accent colour), height 48–54 px (min 44), padding `0 22–26px`, label 15–16 px/500 or 12–13 px caps 500 with 0.14em spacing, an arrow on the right with a 12–14 px gap.
- Secondary: 1 px outline or a translucent panel on photos. One primary per screen.
- Label = verb + object: «Смотреть каталог», «Оставить заявку», «Обсудить проект». Not «Узнать больше». NEVER a small underlined «Подробнее» link for an action; text links only inside text, menus, footer.
- States: hover — colour change 200–380 ms and arrow shift 4–5 px; press — `scale(.98)` 120–180 ms; `:focus-visible` — 1–2 px outline offset 3–4 px; loading — `disabled`, opacity 0.6–0.8, `cursor: progress`.
- Phone columns: full-width buttons, label left, arrow right.

```css
.btn {
  display: inline-flex; align-items: center; gap: 12px;
  min-height: 52px; padding: 0 24px;
  font: 500 16px/1 var(--font-text);
  border: 1px solid transparent; border-radius: var(--radius-btn);
  transition: background-color 300ms ease, color 300ms ease, transform 160ms var(--ease-out);
}
.btn--primary { background: var(--ink); color: var(--bg); }
.btn svg { transition: transform 400ms var(--ease-out); }
.btn:active { transform: scale(.98); }
.btn:focus-visible { outline: 2px solid var(--ink); outline-offset: 3px; }
@media (hover: hover) and (pointer: fine) {
  .btn--primary:hover { background: var(--ink-2); }
  .btn:hover svg { transform: translateX(5px); }
}
```

## Forms
- Label above the field; the placeholder is an example value, not the label.
- Field height 48–52 px, `font-size: 16px` (iOS zoom), padding `14px 16px`, 1 px border at 25–30% text colour, radius per system.
- Focus: text or accent border + a 1 px ring; never the browser's blue glow.
- Errors: 13 px text below in `--danger`, `aria-invalid`, `aria-describedby`; validate on blur and submit, not per keystroke; say how to fix («Проверьте номер: не хватает цифр»).
- Submit: button disabled, «Отправляем…». Success: the form is replaced by a confirmation with a clear next step, focus moves to it, «Отправить ещё» next to it.
- 2–4 options → a segmented control on radios, not a dropdown. Minimum fields.

## Navigation
- Fixed header 72–84 px desktop, 60–64 px phone. Over the first screen: transparent, light text, a light top darkening. After 40–80 px of scroll: `--bg` at 0.92–0.94, `backdrop-filter: blur(14px)`, 1 px bottom line, height −8–12 px, dark logo.
- 4–6 items; current page underlined 1–1.5 px with `aria-current="page"`; hover underline grows from the left in 240 ms. The header's main action: a small filled button (44 px).
- Phone: 44 × 44 burger → full-screen or dropdown panel; 52 px rows with thin lines or 28–34 px type; button at the bottom; Esc closes, focus trapped, page scroll locked.
- Page transitions: fade 320–550 ms; with pinned blocks animate only `opacity`.

## Cards
- Only for real objects: product, review, case, person. "Benefits with icons" in cards — NEVER.
- Product card: photo 4:5 or 1:1 on `--bg-2`, category label, name 15 px/500, muted specs, price; no border or shadow; hover zooms the photo to 1.03–1.04 over 400–800 ms.
- Review: real photo if any, quote, name, what they bought.
- On phones card rows become horizontal scroll with `scroll-snap`, card width 80–85% so the next one peeks.

## Icons
Line icons on a 24 px grid, 1.5 px stroke, round caps (Lucide style), inline SVG with `currentColor`; fill only for the active state. Emoji instead of icons — NEVER.
