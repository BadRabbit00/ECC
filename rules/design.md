---
paths:
  - "**/*.css"
  - "**/*.scss"
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.html"
  - "**/*.vue"
  - "**/*.dart"
---

# Visual design and UI code

## Scope

Anything that renders: sites, app screens, HTML documents, slides. The full guide (composition, photos, motion, documents, presentations) is the `design-system` skill. `ui-verifier` checks the result with screenshots.

## Rules

- R-UI-TOKENS: colors, fonts, spacing, radii, and easing come only from tokens (CSS custom properties / theme). Brand colors come from the brand book or logo, with the source noted. Never invent them. No pure `#000` for text.
- R-UI-TYPE: a round geometric sans (Montserrat by default; Manrope/Onest as alternatives; Inter/Golos for documents), weights ≥ 400, at most two families. Left-aligned text, 45–75 characters per line, `tabular-nums` for numbers.
- R-UI-ONE-RADIUS-SYSTEM: one radius system per project (square + pill buttons, or 4–8 px everywhere). Shadows only on floating layers.
- R-UI-CTA: an action is a filled button ≥ 48 px high with a verb + object label («Оставить заявку»), one primary button per screen. Never a small «Подробнее» link.
- R-UI-MOTION: animate only `transform`, `opacity`, `filter`, `clip-path`; use the project's easing tokens; reveal once on entering the viewport; honour `prefers-reduced-motion`. Hover effects go only inside `@media (hover: hover) and (pointer: fine)`.
- R-UI-A11Y: text contrast ≥ 4.5:1 (large text ≥ 3:1), visible `:focus-visible`, touch targets ≥ 44 px, inputs 16 px font.
- R-UI-NO-FETCH-IN-COMPONENTS: components never call `fetch`/`axios`. The chain is component → hook → API module → `http.ts`. Env vars are read only in `shared/config/env.ts`.
- R-UI-WIDTHS: every visual change is checked at 375 / 768 / 1024 / 1440 with no horizontal scroll. Documents are checked in both themes.
- R-UI-SCOPE: change only what was named. "Change the font" changes the typeface, not sizes or spacing.

## Examples

### R-UI-MOTION — compositor-only properties

Bad:
```css
.card { transition: all .3s; }
.card:hover { top: -4px; box-shadow: 0 8px 24px #0004; width: 102%; }
```
Why: layout thrash on every hover; the hover sticks on touch screens; `all` animates things nobody chose.

Good:
```css
.card { transition: transform var(--dur-hover) var(--ease-out); }
@media (hover: hover) and (pointer: fine) {
  .card:hover { transform: translateY(-4px); }
}
@media (prefers-reduced-motion: reduce) { .card { transition: none; } }
```

### R-UI-NO-FETCH-IN-COMPONENTS — data through hooks

Bad:
```tsx
export function OrderTable() {
  const [rows, setRows] = useState<Order[]>([]);
  useEffect(() => { fetch("/api/v1/orders").then(r => r.json()).then(setRows); }, []);
  return <Table rows={rows} />;
}
```
Why: no error or 401 handling, the URL is duplicated, and there is no cache or loading state.

Good:
```tsx
export function OrderTable() {
  const { data, isPending, error } = useOrders();        // TanStack Query hook → orderApi → http.ts
  if (error) return <ErrorState error={error} />;
  return <Table rows={data ?? []} loading={isPending} />;
}
```
