# Design language

pomale shares its design language with [fahrma](https://github.com/percuro/fahrma), a car-sharing ledger by the same author. Both are web apps that have to feel right in a browser tab and as an installed app on a phone's home screen. They share spacing, type, components and behaviour; colours, shapes and one signature element belong to each app alone.

The apps follow the ergonomic rules of iOS and Android (target sizes, navigation at the bottom, safe areas, the system font) but imitate neither system's look.

## Principles

1. **Entered in seconds.** The most frequent action is the largest area within reach of the thumb. One primary button per view.
2. **Calm and honest.** Colour stands for meaning (a state, the primary action). A state is always a word or a symbol; colour only supports it.
3. **Numbers are exact.** Digits of equal width, right-aligned in lists, and one large figure per view (`.figure`).
4. **Content before frame.** Flat surfaces with hairlines. A shadow is reserved for what lies on top of the page: dialog, toast.
5. **At home everywhere.** One layout for the tab, the home-screen app and a desktop window, driven by the window's width and the safe areas.
6. **One system, two characters.** The same anatomy, a different colour world, shape and signature.

## Foundation

| Topic | Rule |
|---|---|
| Spacing | 4 px steps, `--space-1` to `--space-7` (4 to 48 px) |
| Type | The system font, no web font. Sizes 12 / 14 / 16 / 18 / 24 px and a 32 px figure; nothing below 12 px. On iPhone and iPad the base size follows the system text size |
| Touch targets | At least 44 × 44 px (`--tap`), 8 px apart |
| Window classes | Compact below 600 px, medium up to 839 px, wide from 840 px. The navigation sits at the bottom up to 839 px and in the top bar from 840 px; content may use columns from 600 px |
| Content width | 46 rem, wide pages 64 rem |
| App frame | Top bar with the name and the account, opaque up to the edges (browsers take the colour of their own bars from it). Navigation with three to five places, each an icon and a short word, the active one with a pill. Safe areas on every side |
| Icons | One set (`components/Icons.tsx`): 24 px grid, 2 px stroke, round ends, colour from the text. No Unicode characters as icons |
| Contrast | Text 4.5 : 1, edges of controls and the focus ring 3 : 1, in the light and the dark scheme |
| Motion | 120 / 200 / 320 ms, one curve, feedback only, behind `prefers-reduced-motion` |

### Colour roles

Every colour in the interface is a role. Both apps define the same roles in their `styles/theme.css`, once for the light and once for the dark scheme:

- Surfaces: `--bg`, `--surface`, `--surface-2`, `--border` (hairline), `--border-strong` (edge of fields and buttons, at least 3 : 1)
- Text: `--text`, `--muted`
- Brand: `--accent` (links), `--accent-fill` / `--on-accent-fill` (primary button), `--accent-soft` / `--on-accent-soft`, `--highlight` / `--on-highlight` (the active place, "now")
- Frame: `--chrome`, `--on-chrome`, `--chrome-muted`, `--chrome-brand`, `--chrome-border`, `--chrome-focus`
- The featured card: `--feature-*` (at most one per view)
- Meaning: `--plus`, `--minus`, `--danger` / `--on-danger`, `--danger-text` / `--danger-bg`, `--warn-*`, `--info-*`, `--ok-*`
- Other: `--focus`, `--shadow`, the radii `--radius-s/m/l`, `--radius-button`, `--radius-field`, `--radius-pill`, and `--font-display`

`styles/tokens.test.ts` checks 40 pairs of these roles against the contrast minimum in both schemes, and that the theme defines exactly this set.

### Components

App frame (`.topbar`, `.brand`, `.appnav`, `.content`), button (`.button` with `.primary`, `.quiet`, `.danger`, `.small`, `.icon`), `.icon-button`, `.link-button`, field (`.field`, `.hint`, `.error`), `.chips` / `.chip`, `.stepper`, `.card` (and `.card.feature`), `.list` / `.row`, `.badge`, `.stats` / `.stat`, `.notice`, `.dialog` (a sheet from the bottom on a phone), `.toast`, `.banner`, tables.

## The character of pomale: morning paper

| | |
|---|---|
| Colour world | Moss green on a warm, slightly green paper |
| Frame | A light top bar in the colour of the paper, the name in moss green |
| Primary button | Moss green |
| Highlight | A soft green: the active place, today's column |
| Shape | Soft: radii 10 / 16 / 22 px, buttons are capsules |
| Headings | The rounded system face on Apple devices (`ui-rounded`), the system face elsewhere |
| Signature | The ring: empty when open, partly filled with the amount inside, filled with a check when done. The same on "Today", in the week and in the history (`components/days/StateIcon.tsx`, `.ring`) |
| App icon | Light, a ring that is nearly closed with a check |

The state of a day is always written or named as well: the ring is decoration for the eye, the word is the information. Habit colours are a small mark next to the name and never the only hint.

fahrma is the opposite on purpose: a dark top bar, ink blue and headlight amber, firmer corners and large figures as its signature. The two app icons differ in lightness, not only in hue, so they can be told apart without colour vision.

## Files

```
frontend/src/index.css               the five layers, in order
frontend/src/styles/tokens.css       spacing, type, sizes, motion     shared
frontend/src/styles/base.css         element defaults                 shared
frontend/src/styles/components.css   components                       shared
frontend/src/styles/utilities.css    helper classes, topmost layer    shared
frontend/src/styles/tokens.test.ts   contrast test of the theme       shared
frontend/src/components/Icons.tsx    the icon set                     shared
frontend/src/styles/theme.css        colour roles, radii of pomale
frontend/src/styles/app.css          what only pomale has: ring, today, week, history
frontend/src/app/icon.svg, badge.svg app icon and notification badge; `node scripts/icons.mjs` writes public/
```

The files marked *shared* are identical in pomale and fahrma. A change to one of them belongs in both projects; say so in the pull request and the maintainer carries it over.

Checks: `npm test` (contrast of the theme), and in `e2e/tests/design.spec.ts` an automatic WCAG 2.2 AA scan of the main pages in both colour schemes, no sideways scrolling at 320 px, the window title, the position of the navigation and the way from the account page to logging out.

## Sources

- Apple Human Interface Guidelines: [Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars), [Layout](https://developer.apple.com/design/human-interface-guidelines/layout), [Typography](https://developer.apple.com/design/human-interface-guidelines/typography), [Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility), [Color](https://developer.apple.com/design/human-interface-guidelines/color), [Buttons](https://developer.apple.com/design/human-interface-guidelines/buttons)
- Material 3 and Android: [Window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes), [Navigation bar](https://developer.android.com/develop/ui/compose/components/navigation-bar), [Touch target size](https://support.google.com/accessibility/android/answer/7101858)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- web.dev: [PWA app design](https://web.dev/learn/pwa/app-design)
- [GOV.UK Design System: Layout](https://design-system.service.gov.uk/styles/layout/), [Nielsen Norman Group: 10 usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
