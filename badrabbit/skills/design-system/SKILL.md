---
name: design-system
description: Use when work touches how something looks - site blocks, app screens, styles, HTML documents and guides, slides - for Alexey's design principles, the one-block-at-a-time process, colour and type rules, layout, components, motion, media, copy, documents, presentations, and the screenshot check.
---

# Design system

Alexey's visual design rules (source: `05-design`). **ALWAYS / NEVER** are hard rules; "by default" may change only by a named exception or the user's request. Writer rules for code: `design.md` (R-UI-*). Visual checks: `ui-verifier`. Slides: the `presenter` agent and `~/.claude/br/templates/slides.html`.

## Principles

1. **An idea from the client's world.** Every concept rests on a metaphor from the client's real material: product, process, place, texture, document. Test: «the block is built on …, because the client has …». If you cannot say it, it is a template, not an idea.
2. **Composition, not arrangement.** Layers: overlaps, depth, contrast of scale, rhythm of light and dark sections. A grid of equal rectangles is not design.
3. **Colour comes from the client.** Brand colours are never invented (`references/color-type.md`).
4. **A round, dense, readable typeface.** Wide geometric sans, weights from 400.
5. **The action is visible at once.** A CTA is a filled button, never a link.
6. **Copy informs, visuals create the mood.** Plain, direct headings.
7. **Restraint.** One accent, thin lines, almost no shadows, no decorative gadgets.
8. **System.** Colours, fonts, spacing, radii, easing only through tokens.
9. **Checked with eyes.** Nothing is shown before screenshots at 375 / 768 / 1024 / 1440.

## Process

**Before starting**: collect brand book, logo (vector), presentations, social media, the client's photos and videos, texts, references; list what is missing. References give theme and mood; their layout is never copied. Client documents are a draft of content, not finished copy.

**One block at a time**, strictly in order:
1. Understand the block: what is wrong and its goal (explain, convince, sell, move on). Unclear → 1–3 concrete questions in one round (interactive tool if available, recommended option first «(рекомендую)»; otherwise numbered options). Decide the rest and list the decisions when showing.
2. The idea with a reason: 2–4 sentences — what, from which client material, what risk.
3. A mock-up of this block only: HTML in a browser, real fonts, real or clearly marked draft photos.
4. Screenshot check (`references/media-copy-check.md`).
5. Show and agree.
6. Only then the next block.

NEVER rework several blocks at once; NEVER touch agreed blocks unless asked. One thoughtful block beats five shallow ones.

**Variants**: one solution by default; variants only when asked, at most two, differing in **idea** (metaphor, composition, use of photos), not background colour or font. For each: name, idea in one sentence, strength, risk. A visual fork is always shown as a mock-up. The chosen variant is edited in place; rejected ones are removed. Full-page mock-ups label blocks («3 · Каталог») and, with animation, a «Повторить анимацию» button; labels and draft marks never reach the product.

**Spot edits**: change only what was named, in the file and block the user looks at; no copies of files, no "improving" neighbours (name a problem nearby, do not touch it). «Смени шрифт» changes only the typeface. «Сделай заметнее» does not mean "make everything bigger". Agreed copy moved to another page is copied word for word.

## References

| File | Covers |
|---|---|
| `references/color-type.md` | colour sources, palette roles and proportions, contrast and text on photos, tone; typefaces, weights, the type scale, typographic details |
| `references/layout-components.md` | grid, spacing, radii, shadows, lines; block composition and layering moves, numbers, the first screen, numbering; buttons, forms, navigation, cards, icons |
| `references/motion.md` | easing tokens, durations, motion rules, reduced motion |
| `references/media-copy-check.md` | responsive rules and the screenshot check; photos and video; copywriting |
| `references/documents-slides.md` | HTML documents, guides (mini-guides), presentations |

## Anti-patterns

First screen "heading + two buttons + four number cards" · three "concepts" differing by background colour · flat 50/50 text/photo with three facts in a row · invented brand colours · sharp high-contrast serif in caps, weights 300 · "changed the font" and enlarged everything · «Подробнее →» as a small link · slogans playing on the brand name · type-on letters, scroll-bound headings, counters on every view · decorative gadgets (HUD captions, fake order widgets, gauges over video) · reworking all blocks at once; four new variants for a spot edit · an all-dark site without reason · the same background video on every page; edits with transitions and zooms · hover without `(hover: hover)` · a shadow on every card and five radii · a reference document in brand dark colours with caps · layout copied from a reference.

## Checklist before showing

- [ ] The block solves one task, nameable in one sentence; the idea grew from the client's material, reason written.
- [ ] Every colour has a source; derived ones marked; without a brand book the palette is a proposal.
- [ ] Round sans, weights ≥ 400, headings 500, ≤ 2 families (+ one handwritten accent if needed); caps only for small labels; «ёлочки», dashes, ё, non-breaking spaces.
- [ ] The main action is a filled button ≥ 48 px, one per screen.
- [ ] Numbers woven into the story, real, with sources; no row of number cards.
- [ ] Everything through tokens; one radius system; shadows only on floating layers.
- [ ] Motion on `transform`/`opacity`/`filter`/`clip-path`, custom easing, text only fades in, everything plays once; reduced motion checked.
- [ ] Hover inside `(hover: hover) and (pointer: fine)`; `:focus-visible` visible; contrast ≥ 4.5:1 (large ≥ 3:1).
- [ ] Photos real or one generated series, no artefacts; WebP/AVIF, `srcset`, lazy, sizes set.
- [ ] Copy plain and direct; agreed copy untouched.
- [ ] Screenshots at 375 / 768 / 1024 / 1440: no overflow, overlaps, orphans, horizontal scroll, console errors.
- [ ] Documents: both themes, print, offline if needed. Guides: TOC, real tables/SVG, analogies, common mistakes, self-check in `<details>`, cheat sheet, glossary. Slides: every slide at 1600×900 and narrow, PDF builds, no external URLs.
- [ ] Mock-up labels, draft marks, rejected variants removed; only what was asked changed.
