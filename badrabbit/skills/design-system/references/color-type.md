# Colour and type

## Where colours come from
Order: brand book → logo → client materials (presentations, packaging, signs, own photos — eyedropper).
- A palette proposal ALWAYS comes as a table: token, HEX, role, **source** (document and page, logo, photo).
- Derived colours (darker for text, hover, a dark section) are marked "derived from …".
- No brand book → say so and present the palette as a **proposal to approve**, built from the logo and photos.
- Brand book and logo disagree (e.g. a sub-brand colour against the main brand) → ask which wins.

## Palette roles
| Role | Rule |
|---|---|
| background | white or warm near-white (lightness 95–98%). Cold grey as the main background — NEVER |
| secondary background | 2–4% darker: alternating sections, under photos |
| text | near-black with the palette's undertone. Pure `#000` — NEVER |
| muted text | two levels, each ≥ 4.5:1 on the background |
| lines | text colour at 10–35% opacity |
| accent | one colour, ≤ 5% of the area: lines, numbers, active states, the main button |
| accent for text | a darker accent if the accent itself is under 4.5:1 |
| dark section | the deepest palette colour, not black |
| error | its own colour, only for form messages |
| semantic pairs | only where meaningful (plus/minus, A vs B); fixed to that meaning across the product |

Screen proportions: background ~60%, text and dark planes ~20%, washes and lines ~10%, muted ~5%, accent ≤ 5%.

## Contrast and text on photos
Normal text ≥ 4.5:1; large (from 24 px, or 19 px bold) ≥ 3:1. An accent that fails is decoration only. Text on photos: directional darkening from the text side (deep palette colour, opacity 0.4–0.85, fading out by 50–60% of the width); the product side stays clean; on phones the darkening comes from the bottom.

## Tone
Light base by default. A fully dark "night" site only if the brand book says so or the user asks. Dark sections for rhythm: 1–2 per page plus the final call or footer. No neon, random gradients, or glass cards; `backdrop-filter` only for the header and popovers over photos.

```css
:root {
  /* Placeholders. Replace with brand-book colours and name the source of each. */
  --bg:      #F7F6F3;  /* background: source — … */
  --bg-2:    #EFEDE8;  /* derived from --bg */
  --ink:     #1D1C1A;  /* text: source — … */
  --ink-2:   #4A4743;  /* derived from --ink */
  --muted:   #6E6A64;  /* derived from --ink, ≥ 4.5:1 on --bg */
  --line:    rgb(29 28 26 / .14);
  --accent:  #4A4A4A;  /* FROM THE BRAND BOOK */
  --accent-text: #333333; /* derived: accent for small text */
  --danger:  #A8432C;  /* form errors only */
}
```

## Typeface
- Default **Montserrat** (wide round geometric sans with Cyrillic); same class replacements: Manrope, Onest. Long reading and service documents: Inter, Golos Text, or the system stack.
- ALWAYS test glyphs: ё, «», —, №, the currency sign, every language of the site.
- NEVER: sharp high-contrast serifs for headings, weights 100–300, thin spaced caps, condensed display faces as the main font.
- At most two families. An allowed third: one handwritten face for an accent of 1–3 words (a signature, a step number, a "marker" note), at most once per block, never for must-read information. Monospace only for service labels and code in a technical style.
- Fonts self-hosted, `font-display: swap`, only the needed weights and subsets.

## Weights
Text 400 · UI, captions, buttons 500 · headings 500 · emphasis 600. Exception: short slide headings and big numbers in a presentation 600–800, if agreed with the user.

## Site type scale
| Role | Desktop | Phone | line-height | letter-spacing |
|---|---|---|---|---|
| first-screen heading | `clamp(40px, 5vw, 80px)` | 34–44 px | 1.0–1.1 | −0.02…−0.035em |
| H2 | `clamp(30px, 3.6vw, 56px)` | 28 px | 1.1–1.2 | −0.01…−0.03em |
| H3 | `clamp(21px, 1.8vw, 30px)` | 20–22 px | 1.2–1.3 | −0.01em |
| lead | `clamp(17px, 1.4vw, 21px)` | 16–17 px | 1.5–1.55 | 0 |
| body | 16–17 px | 16 px | 1.6–1.7 | 0 |
| caption | 13–14 px | 13 px | 1.4–1.5 | 0 |
| service label (caps) | 11–12 px, 500 | 11 px | 1 | 0.14–0.18em |
| button | 15–16 px, 500 | — or 12–13 px caps | 1 | 0 / 0.12–0.16em |

- Body line length 45–75 characters (`max-width: 36em`); headings `max-width: 15–20ch` and `text-wrap: balance`.
- Left-aligned; centred only for short cover phrases; justified — NEVER.
- Caps only for small service labels; headings in sentence case.
- `font-variant-numeric: tabular-nums` for counters, prices, tables, step numbers.
- Russian typography: «ёлочки» with „лапки“ inside; em dash with spaces; ё; non-breaking spaces after short prepositions and conjunctions, between a number and its unit, between digit groups (`12 500`).
- `text-transform: uppercase` can change some glyphs (Greek letters etc.): wrap such fragments in a `span` with `text-transform: none`.
