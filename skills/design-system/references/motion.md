# Motion

## Character
A smooth start and a long soft deceleration. No springs or bounces. Motion reveals content, it does not decorate it.

```css
:root {
  --ease-out:    cubic-bezier(0.23, 1, 0.32, 1);   /* reveals, hover, press */
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);  /* curtains, line drawing */
  --dur-hover: 240ms;
  --dur-reveal: 900ms;
  --stagger: 80ms;
}
```

## Durations
| What | Duration | Curve |
|---|---|---|
| hover: colour, background, underline | 200–300 ms (button fill up to 380) | `ease` |
| press, `scale(.97–.98)` | 120–180 ms | `--ease-out` |
| button arrow shift 4–5 px | 350–480 ms | `--ease-out` |
| menu, popover: `opacity` + `translateY(-6…-10px)` | 200–260 ms | `--ease-out` |
| block reveal: `opacity` + `translateY(12–16px)` (+ `blur(4px)`) | 700–900 ms, step 60–110 ms | `--ease-out` |
| first-screen heading lines from under a mask | 900–1000 ms, step 80 ms | `--ease-out` |
| photo curtain (`clip-path`) | 1000–1300 ms; photo inside `scale(1.1→1)` 1600–1900 ms | `--ease-in-out` / `--ease-out` |
| page transition | 320–550 ms | `--ease-out` |
| slide elements | 320–520 ms, step 50–70 ms | `--ease-out` |

## Rules
- Animate only `transform`, `opacity`, `filter`, `clip-path`; `width`, `height`, `top`, `left`, `margin` — NEVER.
- A reveal plays once when the block enters the viewport (IntersectionObserver, threshold 0.15–0.25), not bound to scroll position.
- Text only fades in with a small rise, by line or block. Typewriter, word-by-word fill, scroll-bound text — NEVER.
- Lines from under a mask: only for the first-screen main heading, whole lines.
- A composite block (card chain, steps) is a timeline that plays once on entry.
- Scrub, pin, parallax: off by default; exceptions: one "domain" scene (an object flies in, sticky steps) or the user's request. Parallax shift ≤ 4–8% of the block height.
- Number counters once, on first view, 1–1.6 s; the final value is in the HTML.
- Hover effects only inside `@media (hover: hover) and (pointer: fine)`.
- Infinite loops only for quiet hints (a pulsing dot, period ≥ 2.5 s).
- While a preloader or curtain runs, animations are paused (`animation-play-state: paused`) and do not play invisibly.
- The hidden start state is enabled by a class set from JS; without JS the content is visible.

## Reduced motion
ALWAYS: movement becomes a 300–500 ms fade; parallax, scrub, curtains, smooth scroll, auto-carousels off (ribbons become manual `scroll-snap`); background video does not autoplay (poster + play button); content shown in its final state.

```css
.rv { opacity: 0; transform: translateY(16px); filter: blur(4px);
      transition: opacity var(--dur-reveal) var(--ease-out),
                  transform var(--dur-reveal) var(--ease-out),
                  filter var(--dur-reveal) var(--ease-out);
      transition-delay: calc(var(--i, 0) * var(--stagger)); }
.rv.is-in { opacity: 1; transform: none; filter: none; }

@media (prefers-reduced-motion: reduce) {
  .rv { transform: none; filter: none; transition: opacity 400ms ease; }
  .parallax, .curtain { transform: none !important; clip-path: none !important; }
  ::view-transition-old(root), ::view-transition-new(root) { animation: none; }
}
```
