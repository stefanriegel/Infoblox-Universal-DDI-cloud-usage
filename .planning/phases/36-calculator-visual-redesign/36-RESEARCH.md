# Phase 36: Calculator Visual Redesign - Research

**Researched:** 2026-03-08
**Domain:** Plain CSS custom properties, Jinja2 template structure, FastAPI route context injection
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Accent color scope**
- Accent appears on: wizard step number circles (active/complete state) and primary CTA buttons per calculator
- Accent does NOT appear on: tab bar active underline, breadcrumb, results/complete screen headings, section dividers, or data tables
- For Cloud Calculator: accent applies only on wizard screens (Setup/Providers/Accounts/Review). Progress, Results, and Summary tabs use standard `--ib-blue` — tab bar does not change per calculator
- Results/complete screens are data-heavy and audit-focused — kept visually neutral, no accent bleed into read-only content

**Accent injection mechanism**
- CSS class on `<body>`: `calc-cloud`, `calc-nios`, `calc-ad`
- Backend passes `calc_theme` variable in each `/cloud`, `/nios`, `/ad` route handler directly (not via `_get_tab_context()` helper — keep that helper generic, consistent with Phase 35 decision)
- Home screen (`/`) uses empty/no class — `--calc-accent` falls back to `--ib-blue` via cascade; wizard steps don't appear on home so no visible effect
- CSS in `app.css`:
  ```css
  .calc-cloud { --calc-accent: #0066CC; }
  .calc-nios  { --calc-accent: #00C389; }
  .calc-ad    { --calc-accent: #8B5CF6; }
  ```
- All accent-using selectors reference `var(--calc-accent)` rather than `--ib-blue`

**Wizard step complete state (DESIGN-04)**
- Completed step circle: filled accent background + Unicode ✓ character (not step number) — `content: '\2713'` via CSS
- Active step circle: filled accent background + step number (unchanged behavior)
- Upcoming step circle: unfilled, gray text — no change from current style
- Mechanism: `.wizard-steps li.completed .step-number` content switched to checkmark via CSS pseudo-element

**Results screen card layout (DESIGN-05)**
- **NIOS complete screen**: Wrap the entire completion flow in a single card (`<article>` with border/shadow). Internal layout: header section (Analysis Complete + filename), divider, Token Estimates section (existing scenario-grid of 3 scenario-cards), divider, Download XLS section. Single card, not separate cards per section.
- **Cloud Summary tab**: Add labeled section headers (`<h3>Token Summary`, `<h3>Per-Provider Breakdown`, `<h3>Account Attribution`) with horizontal dividers between sections. No new card wrappers — visual hierarchy via headings and spacing only.
- AD complete screen: apply same single-card wrapper pattern as NIOS (consistent treatment)

### Claude's Discretion
- Exact CSS for section headers on Cloud Summary tab (font size, weight, color, divider style)
- Whether `--calc-accent` is defined in `design-system.css` `:root` as a fallback or left undefined (letting browsers show unset)
- `base.html` `<body>` class attribute handling (single class vs. combining with other body classes)
- AD complete screen — if it doesn't have a completion state yet, implement the card wrapper as a placeholder

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DESIGN-03 | Each calculator has a distinct visual accent color (Cloud: blue `#0066CC`, NIOS: green `#00C389`, AD: purple `#8B5CF6`) within the shared design system | CSS custom property `--calc-accent` on body class; wizard step selectors already reference `--ib-blue` — swap to `var(--calc-accent)` |
| DESIGN-04 | Wizard steps display numbered step indicators with clear visual progression (step counter, active/complete state) | `.wizard-steps li.active .step-number` and `.wizard-steps li.completed .step-number` exist in app.css lines 380–390; completed state needs CSS `content: '\2713'` pseudo-element and accent color swap |
| DESIGN-05 | Results/complete screens use a card-based layout with visual separation of key metrics (token totals, formula derivations, attribution tables) | NIOS/AD complete partials: wrap outer `<article class="completion-banner">` or add enclosing `<article>` wrapper; Cloud summary.html: add `<h3>` section headers with `<hr>` dividers |
</phase_requirements>

---

## Summary

Phase 36 is a pure CSS + minimal HTML restructuring phase. The design system (`design-system.css` with `--ib-*` tokens) and the component library (`app.css` with `.wizard-steps`, `.scenario-card`, `.summary-cards`) are already in place from Phases 33–35. This phase layers per-calculator identity on top of that foundation without adding new components, new routes, or any JavaScript.

The work divides cleanly into three parallel streams: (1) CSS-only accent propagation via a body class and `--calc-accent` custom property, (2) CSS pseudo-element for the completed wizard step checkmark, and (3) light HTML restructuring of the NIOS/AD complete partials and the Cloud summary template.

The codebase is a FastAPI + Jinja2 + plain CSS stack with no build pipeline. All changes are achievable by editing three files (`routes/pages.py`, `base.html`, `app.css`) plus two or three template partials (`partials/nios/complete.html`, `partials/ad/complete.html`, `pages/summary.html`). No new libraries, no preprocessors, no JavaScript additions are needed.

**Primary recommendation:** Inject `calc_theme` after `_get_tab_context()` in each route handler (mirroring the `calculator_name` pattern from Phase 35), render it as a body class in `base.html`, and let CSS cascade do all visual switching.

---

## Standard Stack

### Core (already present — no new installs)
| Library/Tool | Version | Purpose | Status |
|---|---|---|---|
| FastAPI | in venv | Route handlers, template context injection | Existing |
| Jinja2 | in venv | Template rendering, `{{ calc_theme \| default('') }}` | Existing |
| Plain CSS | N/A | Custom properties cascade, pseudo-elements | Existing |
| pytest + starlette TestClient | in venv | Test scaffold for acceptance criteria | Existing |

**Installation:** No new packages required.

---

## Architecture Patterns

### Existing CSS File Split
```
src/cloud_usage/dashboard/static/
├── design-system.css   # :root token definitions (--ib-* variables)
└── app.css             # Component styles (wizard-steps, scenario-card, etc.)
```

`design-system.css` defines the global token foundation. `app.css` houses all component-level selectors. Phase 36 CSS additions belong in `app.css` (per-calculator body classes and accent overrides are component-level concerns, not design tokens).

### Pattern 1: CSS Custom Property Scoping via Body Class

**What:** A CSS class on `<body>` redefines a custom property (`--calc-accent`) that downstream selectors consume. The cascade automatically propagates the value to all descendants without any JS or per-element changes.

**When to use:** When a single semantic value (accent color) must differ per page context but apply to many unrelated selectors across the DOM.

**How it works in this codebase:**
```css
/* In app.css — three new rule blocks */
.calc-cloud { --calc-accent: #0066CC; }
.calc-nios  { --calc-accent: #00C389; }
.calc-ad    { --calc-accent: #8B5CF6; }

/* Existing wizard selectors — change --ib-blue references to var(--calc-accent) */
.wizard-steps li.active {
    color: var(--calc-accent);           /* was: var(--ib-blue) */
}
.wizard-steps li.active .step-number {
    background: var(--calc-accent);      /* was: var(--ib-blue) */
    border-color: var(--calc-accent);    /* was: var(--ib-blue) */
}
.wizard-steps li.completed {
    color: var(--calc-accent);           /* was: var(--ib-blue) */
}
.wizard-steps li.completed .step-number {
    background: var(--calc-accent);      /* was: var(--ib-blue) */
    border-color: var(--calc-accent);    /* was: var(--ib-blue) */
}
```

**Fallback consideration (Claude's Discretion):** If `--calc-accent` has no fallback in `:root`, browsers resolve `var(--calc-accent)` as the initial value (empty, which collapses to transparent for color properties). Since wizard steps only appear on `/cloud`, `/nios`, and `/ad` — all of which receive a body class — this is safe. Defining a fallback in `:root { --calc-accent: var(--ib-blue); }` is defensive and costs nothing.

**Confidence:** HIGH — Standard CSS custom property scoping, no browser compatibility concerns (all modern browsers, no IE in scope for enterprise desktop tool).

### Pattern 2: CSS Pseudo-Element for Completed Step Checkmark

**What:** Replace `.wizard-steps li.completed .step-number` text content with a CSS-generated checkmark using a `::before` or `::after` pseudo-element, hiding the original step number.

**Current state (app.css lines 386–390):**
```css
.wizard-steps li.completed .step-number {
    background: var(--ib-blue);
    color: #fff;
    border-color: var(--ib-blue);
}
```
The step number HTML text (e.g. "1", "2") is rendered by the Jinja2 template via `{{ s.number }}`. To show a checkmark instead, CSS must hide or override that text.

**Mechanism — CSS `font-size: 0` + pseudo-element:**
```css
.wizard-steps li.completed .step-number {
    background: var(--calc-accent);
    color: transparent;       /* hide the number text */
    border-color: var(--calc-accent);
    font-size: 0;             /* prevent layout shift from hidden text */
    position: relative;
}

.wizard-steps li.completed .step-number::after {
    content: '\2713';         /* Unicode checkmark ✓ */
    color: #fff;
    font-size: 0.85rem;       /* restore readable size for pseudo-element only */
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}
```

**Why `::after` not `content:` on the element itself:** The `.step-number` span contains text nodes (the step number). CSS `content` on the element itself doesn't replace text nodes — it only applies to replaced elements. Pseudo-elements render independently, allowing the number text to be visually suppressed while the checkmark appears cleanly.

**Alternative — simpler approach without `position: absolute`:** Set `color: transparent` on the element and use `::after` with `display: block; margin-top: -1.1em` to visually overlay. The centered positioning approach above is cleaner and more reliable across browsers.

**No HTML changes required.** The template (`step*.html` files) loop `{% for s in steps %}` and render `{{ s.number }}`. No template edits needed for DESIGN-04.

**Confidence:** HIGH — CSS pseudo-element with Unicode content is a widely-used pattern with no compatibility concerns in modern browsers.

### Pattern 3: Route Context Injection for `calc_theme`

**What:** Each page-level route handler (`/cloud`, `/nios`, `/ad`) adds `calc_theme` to the template context after calling `_get_tab_context()`, mirroring the Phase 35 `calculator_name` pattern.

**Current code structure (routes/pages.py lines 301–325):**
```python
@router.get("/cloud", response_class=HTMLResponse)
async def cloud_calculator(request: Request) -> HTMLResponse:
    templates = request.app.state.templates
    context = _get_tab_context(request, "progress")
    context["calculator_name"] = "Cloud Calculator"   # Phase 35 pattern
    return templates.TemplateResponse(request, "base.html", context)
```

**Phase 36 addition:**
```python
context["calc_theme"] = "calc-cloud"   # add after calculator_name line
```

Same pattern for `/nios` → `"calc-nios"` and `/ad` → `"calc-ad"`.

The `_get_tab_context()` helper is NOT modified (locked decision from CONTEXT.md, consistent with Phase 35 decision recorded in STATE.md).

**Confidence:** HIGH — Direct port of the established Phase 35 pattern, confirmed in both `routes/pages.py` and `STATE.md` decisions.

### Pattern 4: Body Class Rendering in base.html

**Current `<body>` tag (base.html line 10):**
```html
<body>
```

**Phase 36 change:**
```html
<body class="{{ calc_theme | default('') }}">
```

**Body class handling (Claude's Discretion):** Using `| default('')` produces `class=""` when `calc_theme` is not in context (home screen uses `home.html` which doesn't extend `base.html`, so no issue there). An empty `class=""` attribute is valid HTML. Alternatively, a conditional `{% if calc_theme %}class="{{ calc_theme }}"{% endif %}` avoids the empty attribute but adds template verbosity. Either works; `| default('')` is simpler.

**Confidence:** HIGH — Jinja2 `| default` filter is standard; confirmed Jinja2 is the template engine throughout this codebase.

### Pattern 5: NIOS/AD Complete Screen — Single Card Wrapper

**Current structure (partials/nios/complete.html, partials/ad/complete.html):**
Both files have an outer `<article class="completion-banner">` that already provides the white background, border-left, and box-shadow. The CONTEXT.md decision says to wrap the entire completion flow in a single card with section dividers.

**Design-system.css `article` base style (lines 404–411):**
```css
article {
    background: #fff;
    border: 1px solid var(--ib-gray-200);
    border-radius: 6px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}
```

The existing `completion-banner` class adds `border-left: 4px solid var(--ib-green)` and `box-shadow`. For DESIGN-05, the wrapper should use a neutral border (no colored left accent on the wrapper itself — that would conflict with the per-calculator theme). The inner sections should be separated by `<hr>` dividers.

**Proposed structure (NIOS complete partial):**
```html
<article class="completion-card">  {# new class — full border, no colored left accent #}
  <header>
    <strong>NIOS Analysis Complete</strong>
    ...filename...
  </header>
  <hr>
  <section>   {# Token Estimates — existing scenario-grid stays inside #}
    ...scenario-grid...
  </section>
  <hr>
  <section>   {# Download CTA #}
    ...download-cta...
  </section>
</article>
```

**New CSS class in app.css:**
```css
.completion-card {
    background: #fff;
    border: 1px solid var(--ib-gray-200);
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08);
    margin-bottom: 1rem;
}

.completion-card hr {
    border: none;
    border-top: 1px solid var(--ib-gray-200);
    margin: 1.25rem 0;
}
```

The existing `.completion-banner` class can be retired from these two partials (or kept if used elsewhere — search confirms it's only in these two files and the CSS definition; safe to remove from the partials).

**AD complete partial:** Same wrapper pattern. The file already uses `<article class="completion-banner">` so the change is parallel to NIOS.

**Confidence:** HIGH — Both files confirmed in codebase. Pattern is straightforward HTML restructuring.

### Pattern 6: Cloud Summary Tab — Section Headers with Dividers

**Current structure (pages/summary.html):**
The file already has `<h3>Per-Provider Breakdown</h3>` (line 13) and `<h3>Per-Account Breakdown</h3>` (line 43) and `<h3>Download Reports</h3>` (line 196). It includes `{% include "partials/summary_cards.html" %}` at the top (line 10) without a section header.

**CONTEXT.md decision:** Add `<h3>Token Summary</h3>` before the summary_cards include, `<h3>Per-Provider Breakdown</h3>` before the provider table (already exists — keep/style), `<h3>Account Attribution</h3>` before the per-account table, with `<hr>` horizontal dividers between sections. No new card wrappers — headings and spacing only.

**CSS for section headers (Claude's Discretion):**
```css
.section-header {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--ib-gray-600);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.75rem;
}

.section-divider {
    border: none;
    border-top: 1px solid var(--ib-gray-200);
    margin: 1.5rem 0;
}
```

Or simply apply inline-style to `<h3>` and `<hr>` to keep the change contained. Given the no-build-pipeline constraint and "functional tool" aesthetic, a small CSS class is preferable to inline styles.

**Confidence:** HIGH — Template structure fully confirmed from source read.

### Anti-Patterns to Avoid
- **Modifying `_get_tab_context()`:** Locked decision — this helper stays generic. `calc_theme` is injected after the call, not inside it.
- **Using accent color on tab bar:** Tab bar active underline stays `--ib-blue` always. CONTEXT.md explicitly excludes tab bar from accent scope.
- **JS-based content replacement for checkmarks:** No JavaScript needed. CSS pseudo-element handles the checkmark purely in CSS, consistent with the no-JS-in-static-assets constraint.
- **Separate cards per section on NIOS complete:** Single wrapper card, not per-section cards. The inner `scenario-grid` of `.scenario-card` elements already provides visual separation at the data level.
- **Accent on results/complete screen headings or data tables:** Explicitly excluded in CONTEXT.md. Data-heavy audit screens remain visually neutral.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Checkmark icon | SVG icon import, icon font, inline `<span>✓</span>` | CSS `content: '\2713'` | No external dependency; no HTML changes; consistent with no-build-pipeline constraint |
| Per-calculator theme switching | JavaScript class toggler, cookie/session state, JS on load | CSS body class + `var(--calc-accent)` cascade | Zero runtime overhead; CSS cascade is the right tool for inherited values |
| Section dividers | Custom `<div>` elements with border | `<hr>` styled via CSS | Semantic HTML; already handled by browser defaults, easy to override |

---

## Common Pitfalls

### Pitfall 1: CSS Custom Property Cascade Does Not Inherit Across Shadow DOM Boundaries
**What goes wrong:** `--calc-accent` defined on `<body>` does not propagate into shadow DOM (web components). Not relevant here — this codebase uses no web components, all Jinja2 server-rendered HTML.
**How to avoid:** N/A for this project.
**Confidence:** LOW risk (flagged only for completeness).

### Pitfall 2: `content: '\2713'` Not Rendering on Inline Elements Without `display` Adjustment
**What goes wrong:** Pseudo-elements (`::before`, `::after`) on `display: inline` elements can behave unexpectedly. The `.step-number` span has `display: inline-flex` (app.css line 370), which supports pseudo-elements correctly.
**How to avoid:** Confirmed — `inline-flex` elements fully support `::after` pseudo-elements. No change needed to the span's display property.
**Warning signs:** Checkmark appears but is misaligned — fix with `position: absolute` centering as described in Pattern 2.

### Pitfall 3: Empty Class Attribute on `<body>` When `calc_theme` Is Absent
**What goes wrong:** Home screen (`/`) uses `home.html` which does NOT extend `base.html`. It is a fully self-contained template with its own `<body>` tag. No `calc_theme` injection is needed on the home screen and no `<body class="">` will appear there.
**How to avoid:** Confirm `home.html` is standalone (confirmed — it does not `{% extends "base.html" %}`). The `| default('')` in `base.html` is a safety net for any future route that uses `base.html` without providing `calc_theme`.

### Pitfall 4: `completion-banner` Styles Conflicting with New `completion-card` Wrapper
**What goes wrong:** If the existing `<article class="completion-banner">` element is kept AND wrapped in another `<article class="completion-card">`, the `border-left: 4px solid var(--ib-green)` from `.completion-banner` creates an unwanted colored left stripe inside the neutral card wrapper.
**How to avoid:** Replace the `completion-banner` class with `completion-card` on the outer article element — don't nest. The `.completion-banner` CSS rule can remain in app.css (no orphan harm) but should be removed from the two partials.
**Warning signs:** Left colored border appears inside the card, creating visual noise.

### Pitfall 5: `hero-tokens` Color Is Hardcoded to `--ib-blue`
**What goes wrong:** The `.hero-tokens` span in the NIOS/AD scenario cards (app.css line 262) uses `color: var(--ib-blue)`. CONTEXT.md explicitly excludes results/complete screen headings from accent scope. However, `.hero-tokens` on the non-primary scenario cards (not the `.primary` card) would inherit the NIOS green accent if `.hero-tokens` is changed to `var(--calc-accent)`.
**How to avoid:** Do NOT change `.hero-tokens` to use `--calc-accent`. The locked decision keeps results/complete screens accent-neutral. Only wizard step indicators and primary CTA buttons get the accent. `hero-tokens` stays `--ib-blue`.

### Pitfall 6: `calc-nios` Green (`#00C389`) vs `--ib-accent-green` (`#00C389`)
**What goes wrong:** The NIOS accent color `#00C389` is the same value as the existing `--ib-accent-green` token defined in `design-system.css`. Using `--ib-accent-green` directly instead of `--calc-accent` for NIOS would work numerically but would break the intent: `--calc-accent` is the abstraction that enables the cascade. Using the token directly bypasses the pattern.
**How to avoid:** Always use `var(--calc-accent)` in component selectors. The `.calc-nios` body class definition maps `--calc-accent` to the correct value.

---

## Code Examples

Verified patterns from existing codebase source:

### Current wizard-steps active/completed selectors (app.css lines 360–390)
```css
/* These three blocks need --ib-blue replaced with var(--calc-accent) */
.wizard-steps li.active {
    color: var(--ib-blue);          /* → var(--calc-accent) */
    font-weight: 600;
}
.wizard-steps li.active .step-number {
    background: var(--ib-blue);     /* → var(--calc-accent) */
    color: #fff;
    border-color: var(--ib-blue);   /* → var(--calc-accent) */
}
.wizard-steps li.completed {
    color: var(--ib-blue);          /* → var(--calc-accent) */
}
.wizard-steps li.completed .step-number {
    background: var(--ib-blue);     /* → var(--calc-accent) */
    color: #fff;
    border-color: var(--ib-blue);   /* → var(--calc-accent) */
}
```

### Route handler injection (routes/pages.py — current Phase 35 pattern)
```python
@router.get("/cloud", response_class=HTMLResponse)
async def cloud_calculator(request: Request) -> HTMLResponse:
    templates = request.app.state.templates
    context = _get_tab_context(request, "progress")
    context["calculator_name"] = "Cloud Calculator"
    # Phase 36 adds:
    context["calc_theme"] = "calc-cloud"
    return templates.TemplateResponse(request, "base.html", context)
```

### base.html body tag (current — line 10)
```html
<body>
```
Phase 36 change:
```html
<body class="{{ calc_theme | default('') }}">
```

### download-cta button in nios/complete.html — CTA button accent scope
The `.download-cta .btn` class (app.css lines 308–322) uses `background: var(--ib-blue)`. CONTEXT.md says primary CTA buttons per-calculator get the accent. This `.btn` in the download CTA is the primary action button on the complete screen. Decision: the download CTA button is on the complete/results screen which is explicitly kept neutral. Only wizard CTA buttons get accent.

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 36 |
|---|---|---|
| PicoCSS variables (`--pico-*`) | Custom `--ib-*` tokens in `design-system.css` | `--calc-accent` fits naturally into existing token system |
| Single global button color | Per-calculator `--calc-accent` cascade | Requires adding body class to `base.html` |
| Hardcoded `--ib-blue` in wizard selectors | `var(--calc-accent)` in wizard selectors | Simple find/replace in app.css wizard section |

---

## Open Questions

1. **`--calc-accent` fallback in `:root`**
   - What we know: No body class on home screen (home.html is standalone); wizard steps don't appear on home screen.
   - What's unclear: Whether to define `:root { --calc-accent: var(--ib-blue); }` in design-system.css as defensive fallback.
   - Recommendation: Define the fallback. Zero downside; prevents invisible text if the pattern is ever used on a new page without a body class.

2. **Positioning of `::after` pseudo-element on `.step-number`**
   - What we know: `.step-number` is `display: inline-flex`, width/height 1.75rem, border-radius 50%.
   - What's unclear: Whether `position: relative` is already implied or needs adding to `.step-number`.
   - Recommendation: Add `position: relative` to `.step-number` in the Phase 36 CSS additions to ensure the `::after` absolute positioning anchors correctly.

3. **`hero-tokens` on `.scenario-card.primary` (white override)**
   - What we know: `<span class="hero-tokens" style="color:#fff;">` uses inline style on the primary card, overriding the `.hero-tokens` CSS color. This will continue to work correctly regardless of any changes to `.hero-tokens`.
   - No concern — inline styles have highest specificity for that property.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (confirmed in venv) |
| Config file | none — pytest discovers by convention |
| Quick run command | `pytest tests/test_dashboard_visual_redesign.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DESIGN-03 | GET /cloud body contains `calc-cloud` class | unit | `pytest tests/test_dashboard_visual_redesign.py::test_cloud_body_has_calc_cloud_class -x` | ❌ Wave 0 |
| DESIGN-03 | GET /nios body contains `calc-nios` class | unit | `pytest tests/test_dashboard_visual_redesign.py::test_nios_body_has_calc_nios_class -x` | ❌ Wave 0 |
| DESIGN-03 | GET /ad body contains `calc-ad` class | unit | `pytest tests/test_dashboard_visual_redesign.py::test_ad_body_has_calc_ad_class -x` | ❌ Wave 0 |
| DESIGN-03 | app.css contains `.calc-cloud` rule with `#0066CC` | unit | `pytest tests/test_dashboard_visual_redesign.py::test_app_css_has_calc_cloud_accent -x` | ❌ Wave 0 |
| DESIGN-03 | app.css contains `.calc-nios` rule with `#00C389` | unit | `pytest tests/test_dashboard_visual_redesign.py::test_app_css_has_calc_nios_accent -x` | ❌ Wave 0 |
| DESIGN-03 | app.css contains `.calc-ad` rule with `#8B5CF6` | unit | `pytest tests/test_dashboard_visual_redesign.py::test_app_css_has_calc_ad_accent -x` | ❌ Wave 0 |
| DESIGN-04 | app.css wizard completed step uses `var(--calc-accent)` | unit | `pytest tests/test_dashboard_visual_redesign.py::test_app_css_wizard_completed_uses_calc_accent -x` | ❌ Wave 0 |
| DESIGN-04 | app.css wizard completed step has checkmark pseudo-element content | unit | `pytest tests/test_dashboard_visual_redesign.py::test_app_css_wizard_completed_has_checkmark -x` | ❌ Wave 0 |
| DESIGN-05 | GET /tab/nios response (complete state) contains `completion-card` class | unit | `pytest tests/test_dashboard_visual_redesign.py::test_nios_complete_has_completion_card -x` | ❌ Wave 0 |
| DESIGN-05 | GET /tab/ad response (complete state) contains `completion-card` class | unit | `pytest tests/test_dashboard_visual_redesign.py::test_ad_complete_has_completion_card -x` | ❌ Wave 0 |
| DESIGN-05 | Cloud summary template contains `Token Summary` section header | unit | `pytest tests/test_dashboard_visual_redesign.py::test_summary_has_token_summary_header -x` | ❌ Wave 0 |

**Note:** Most CSS assertions are checked by fetching the static file and asserting string presence (same pattern as `test_dashboard_design.py`). For complete-state tests (NIOS/AD), the test must either mock the manager state to `complete` or assert on the template text directly — see `conftest.py` for existing manager mock fixtures.

### Sampling Rate
- **Per task commit:** `pytest tests/test_dashboard_visual_redesign.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dashboard_visual_redesign.py` — 11 tests covering DESIGN-03, DESIGN-04, DESIGN-05
- [ ] No new fixtures needed — existing `create_app()` + `TestClient` pattern is sufficient; CSS assertions use static file fetch; complete-state tests may need manager state manipulation

---

## Sources

### Primary (HIGH confidence)
- Direct source read: `src/cloud_usage/dashboard/static/app.css` — wizard-steps selectors lines 344–390, scenario-card lines 276–302, completion-banner lines 165–178
- Direct source read: `src/cloud_usage/dashboard/static/design-system.css` — `:root` token block lines 21–45, `article` base style lines 404–411
- Direct source read: `src/cloud_usage/dashboard/routes/pages.py` — route handlers lines 301–325, `_get_tab_context()` function lines 97–141
- Direct source read: `src/cloud_usage/dashboard/templates/base.html` — body tag, calculator_name conditional
- Direct source read: `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — full template structure
- Direct source read: `src/cloud_usage/dashboard/templates/partials/ad/complete.html` — full template structure
- Direct source read: `src/cloud_usage/dashboard/templates/pages/summary.html` — full template structure including existing h3 headers
- Direct source read: `.planning/STATE.md` — Phase 35 decisions on `calculator_name` injection pattern
- Direct source read: `tests/test_dashboard_design.py` — CSS assertion pattern using static file fetch

### Secondary (MEDIUM confidence)
- CSS custom property cascade and pseudo-element behavior: standard CSS specification behavior, no library-specific docs required

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing, no new dependencies
- Architecture: HIGH — all patterns confirmed from live source reads
- Pitfalls: HIGH — derived from actual CSS values and template structures read directly, not hypothetical

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable CSS/FastAPI/Jinja2 stack; no moving targets)
