---
name: search-agent-signal
description: >-
  Frontend-design workflow locked to a red / white / yellow “signal flag”
  visual system for Search Agent HTML mockups and UI restyles. Use when the
  user wants Search Agent look redesign, HTML demos, red-white-yellow palette,
  signal aesthetic, or to replace the old dark gold dossier theme. Follows
  frontend-design two-pass planning; do not invent a new palette unless asked.
---

# Search Agent · Signal Flag (红 / 白 / 黄)

This skill = **frontend-design process** + a **fixed** red–white–yellow identity for Search Agent.

Subject: verifiable deep research (claims you can check). Audience: one operator doing serious briefs. Page job: make the question and the evidence feel sharp—like a signal flag, not a dark “AI research” dashboard.

**Do not** revive the old charcoal + gold “evidence dossier” look. That direction is retired.

For open-ended invention outside this product, use the general `frontend-design` skill. For hi-fi prototype craft / variants, optionally pair with `huashu-design`—but **keep this palette**.

---

## Process (from frontend-design — mandatory)

1. **Ground the subject** — state subject, audience, single job (use the paragraph above unless the user overrides).
2. **Two-pass plan** before code:
   - Pass A: compact token system — Color (4–6 named hex) · Type (display + body [+ utility]) · Layout (one sentence + ASCII) · **Signature** (one memorable element).
   - Pass B: critique — if any part reads like a generic AI default for “research SaaS,” revise and say what changed.
3. **Build from the plan only** — every color/type decision derives from the tokens below (or an explicit user override).
4. **Restraint** — spend boldness on the signature; cut one accessory before finishing.
5. **Quality floor** — mobile ok, focus visible, `prefers-reduced-motion`.

### Defaults to avoid (frontend-design calibration)

Even with red/white/yellow locked, still avoid: purple gradients · Inter/Roboto as display · cream+#terracotta “AI default” · black+acid neon · dense zero-radius broadsheet · emoji icon rows · hero card grids / stat strips.

---

## Locked palette (Signal Flag)

| Name | Hex | Role |
|------|-----|------|
| `paper` | `#FFFEFA` | Page ground (warm white, not pure #fff glare) |
| `ink` | `#1A1210` | Primary text |
| `mute` | `#6B6560` | Secondary / chrome |
| `signal-red` | `#E23B2F` | Brand mark, citation stamps, critical emphasis |
| `flag-yellow` | `#F5C518` | CTA, active step, attention stripe |
| `rule` | `#E8E2D8` | Dividers / input borders |
| `panel` | `#FFF8F0` | Soft panels (optional, sparse) |

Semantic mapping:

- **Red** = “this is claimable / stamped / the brand pulse” — brand wordmark accent, `[¹]` citation marks, errors that need action.
- **Yellow** = “act here” — primary CTA fill (with `ink` text), active wizard step, focus ring.
- **White** = calm field; most UI is quiet paper so signal colors stay loud.

Links to sources: underline + `signal-red` (or ink + red underline)—**not** soft sky-blue.

---

## Typography (intentional pair)

| Role | Face | Why |
|------|------|-----|
| Display | **Fraunces** (soft optical serif) | Editorial “stampable” headlines; not Instrument Serif, not Inter |
| Body / UI | **Schibsted Grotesk** (or **DM Sans** if Schibsted unavailable) | Clean operational UI |
| Utility / data | Same grotesk, tabular nums | Meta strips, fact counts |

Google Fonts starter:

```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Schibsted+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
```

```css
--font-display: "Fraunces", Georgia, serif;
--font-body: "Schibsted Grotesk", "DM Sans", system-ui, sans-serif;
```

Eyebrow: small caps / wide tracking in `mute`. Brand H1: Fraunces, tight tracking, with **signature** (below).

---

## Signature (the one memorable thing)

**Left signal bar + red brand underline.**

- A fixed 6–8px vertical strip on the viewport left: alternating or solid `flag-yellow` with a short `signal-red` segment at the top (like a flag hoist).
- Brand word “Search Agent” in Fraunces with a thick `signal-red` underline (3px), not a yellow glow.

Everything else stays quieter than this. Do not add a second signature (no giant watermark, no diagonal full-bleed yellow).

---

## Layout / chrome (product IA — keep)

Still match Wave 12f IA (visual skin changes; structure stays):

| Zone | Behavior |
|------|----------|
| Top utility | Right: Library + gear — `mute`, hover `ink`. No blue nav links |
| Home | One composition: eyebrow → brand → one line → input → modes → yellow CTA |
| Settings | Right sheet on `paper`, red close/label accents only where needed |
| Offline | Thin yellow/red banner — never a permanent “API online” line |
| Library | Tabs Saved / Watching; yellow underline on active tab |
| Report | Citation marks in `signal-red`; body on `paper` |

Content width ~ `max-w-3xl`. Modest radius (`8–10px`) on inputs—**not** pill clusters, **not** zero-radius newspaper.

---

## Motion

One orchestrated entrance: brand underline draws left→right (~400ms), then CTA yellow fills. Respect `prefers-reduced-motion` (skip draw). Hover = color shift only; no glow stacks.

---

## Copy voice

Same product voice: plain, operational. *You define the question. We search, extract, and cite every claim.* Errors: what to run (`start-personal.ps1`), no apology fluff.

---

## Workflow checklist

1. State subject / audience / job.
2. Confirm Signal Flag tokens (or user override).
3. ASCII one-composition layout; name the signature once.
4. Critique vs AI defaults; then code.
5. Standalone HTML: start from [html-starter.html](html-starter.html).
6. Self-check: paper field? red only for brand/citations/errors? yellow only for CTA/active? left signal bar present? no charcoal-gold relapse?
