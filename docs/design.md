# Design notes

## Two jobs, two views

The interface is built around two moments: recording an action in seconds while out and about (iPhone, "today"), and reviewing and correcting a week on a large screen (laptop, "week"). The start page follows the screen size.

## Why a web app

An installed web app (home screen) opens independently of the browser, works offline with a service worker, and needs no app store. What it cannot do on iOS is provide its own home-screen widget – that requires an app extension of a native app. The iOS Shortcuts widget covers the most important case (check off a favourite habit with one tap) without a native app: a shortcut calls `PUT /api/v1/habits/{id}/days/today` with a key that can do exactly that and nothing else. A native widget only pays off if a visible status ("2 of 3 done") on the home screen becomes indispensable.

## Setting, not toggling

`PUT …/days/{date}` with `{"done": true}` sets a state instead of toggling it. Repeating a request (double tap, retry after a timeout, offline queue) never creates a second entry or flips the state back. Each entry has a version; the offline queue sends the version it last saw, and the server answers 409 with its current state if someone changed the entry in between, so the app can ask instead of overwriting.

## Dates

The key of an entry is `(habit, local date)`. "Today" is computed in the configured time zone (by the server for the shortcut, by the browser with `Intl` for offline use), never from the server clock. An entry made offline before midnight and sent after midnight keeps its original date. Schedule changes carry an effective date, so last week's quota does not change when you change your plan today.

## No drama

The history shows "4 of 5" instead of a streak that resets to zero. In Lally et al. (2010), *How are habits formed* (European Journal of Social Psychology), missing a single opportunity did not materially affect habit formation – an argument against dramatic failure messages, not proof that this app works. Future and unplanned days never count against the quota, and an open "today" does not count until it is done.

## Accessibility

Large labelled touch targets (at least 44 × 44 CSS pixels), visible keyboard focus, state shown as text and symbol rather than colour alone, a keyboard-operable week grid, and layouts that work with large text without horizontal scrolling.
