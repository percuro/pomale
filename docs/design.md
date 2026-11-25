# Design notes

## Two jobs, two views

The interface is built around two moments: recording an action in seconds while out and about (iPhone, "today"), and reviewing and correcting a week on a large screen (laptop, "week"). The start page follows the screen size.

## Why a web app

An installed web app (home screen) opens independently of the browser, works offline with a service worker, and needs no app store. What it cannot do on iOS is provide its own home-screen widget – that requires an app extension of a native app. The iOS Shortcuts widget covers the most important case (check off a favourite habit with one tap) without a native app: a shortcut calls `PUT /api/v1/habits/{id}/days/today` with a key that can do exactly that and nothing else. A native widget only pays off if a visible status ("2 of 3 done") on the home screen becomes indispensable.

## Setting, not toggling

`PUT …/days/{date}` with `{"done": true}` (or `{"value": 5}` for a quantity goal) sets a state instead of toggling it. Amounts are always sent as absolute values, never as "+1", so quick taps on + simply replace each other in the offline queue. Only the shortcut adds on the server, in one atomic update. Repeating a request (double tap, retry after a timeout, offline queue) never creates a second entry or flips the state back. Each entry has a version; the offline queue sends the version it last saw, and the server answers 409 with its current state if someone changed the entry in between, so the app can ask instead of overwriting.

## Dates

The key of an entry is `(habit, local date)`. "Today" is computed in the configured time zone (by the server for the shortcut, by the browser with `Intl` for offline use), never from the server clock. An entry made offline before midnight and sent after midnight keeps its original date. Schedule changes carry an effective date, so last week's quota does not change when you change your plan today.

## Goal types and the quota

Every plan has an effective date and a goal type. Changing the type or the target works like changing the weekdays: earlier days keep their old plan.

| Goal type | Example | A day is done when | Quota |
|---|---|---|---|
| `days` | read on Mon–Fri | it is checked off | done of due planned days ("4 of 5") |
| `weekly_count` | run 3× a week | it is checked off; the first 3 check-ins of a week count, more are "extra" | check-ins of the weekly target, week by week |
| `quantity` | 8 glasses of water a day | the amount reaches the target; below it the day is "partly done" | done of due planned days |

Details that keep the numbers honest:

- **Today counts once it is done.** For days and quantity goals, planned days before today are due; today only joins the quota once it is done. For weekly goals a finished week is due in full, the running week only counts what is already done.
- **Weeks start on Monday.** A weekly goal uses the target of the plan in effect at the end of the week (in the running week: today). In a week with fewer active days – the first week, or one with pauses – the target shrinks: `round(target × active days / 7)`, at least 1 while a day is left. A 3× goal started on a Wednesday asks for 2 that week.
- **Pauses** (holiday, illness) take days out: they are not due, also when entered afterwards. Checking off a paused day is allowed and counts as extra.
- **Past days of a weekly goal are never "missed"**; only the week as a whole has a target.

The backend (`day_service.evaluate`) and the web app (`lib/evaluate.ts`, for offline changes) use the same rules and are tested against the same cases (`backend/tests/fixtures/quota_cases.json`).

## No drama

The week view and the history show "4 of 5" instead of a streak that resets to zero; the history page has quotas per period, a 12-week trend and a month calendar, and no streak at all. In Lally et al. (2010), *How are habits formed* (European Journal of Social Psychology), missing a single opportunity did not materially affect habit formation – an argument against dramatic failure messages, not proof that this app works. Future, unplanned and paused days never count against the quota, and an open "today" does not count until it is done. A note on a day is optional and never asked for while checking off.

## Accessibility

Large labelled touch targets (at least 44 × 44 CSS pixels), visible keyboard focus, state shown as text and symbol rather than colour alone (habit colours are only a stripe next to the name), a keyboard-operable week grid, sorting by drag with a keyboard alternative and screen-reader announcements, a history calendar that is a real table naming every day's state, and layouts that work with large text without horizontal scrolling. On iPhone and iPad the text follows the system text size, because an installed web app has no browser zoom. The rules behind this, and the look of the app, are described in the [design language](design-language.md); an automatic WCAG 2.2 AA scan of the main pages runs with the end-to-end tests.
