# Accessibility

pomale aims at [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA: usable with a keyboard alone, with a screen reader, with large text and at 320 px width, in the light and the dark scheme.

## What is built in

- **Keyboard:** every action works without a mouse, including the week grid and sorting habits. The focus ring is at least 3 px with a contrast of at least 3 : 1. A "Skip to content" link leads past the navigation.
- **Changing pages:** after a change of page the focus moves to the start of the content, as after a page load, and screen readers announce the new page's heading. The window title names the page ("Week · pomale").
- **States in words:** done, open, partly done and not planned are in the names of the buttons, not only in the ring or the colour. Checking off is a toggle button ("pressed"), amounts are announced as they change, and messages and errors are live regions.
- **Dialogs** are native modal dialogs: the focus stays inside and returns to the button that opened them.
- **Text size:** on iPhone and iPad the text follows the system size; elsewhere the browser's zoom and font size work without sideways scrolling down to 320 px.
- **Motion:** animations and transitions only run when the system does not ask for reduced motion.
- **Colour:** all colour pairs of the theme meet the WCAG contrast minimum in both schemes. Habit colours are an extra mark next to the name, never the only information.

## How it is checked

Automatically, for every change (see [Development](development.md)):

- `npm test` checks 40 colour pairs of the theme against the contrast minimum in both schemes.
- The end-to-end tests run [axe](https://github.com/dequelabs/axe-core) with the WCAG 2.2 AA rules in Chromium and in WebKit on an iPhone screen, in both schemes, on:
  - every page as it loads, signed in and signed out (login, first-run setup, invitation, registration), in German and in English;
  - what appears only after a click: the note, amount and confirmation dialogs, editing a habit, a new shortcut or API key, archived habits, an invitation link, a backup result, the import preview and the offline notice.
- The same tests check that no page scrolls sideways at 320 px and that the focus moves to the content after a change of page.

Automated tests find only part of all problems. Checks by hand with screen readers (VoiceOver on iPhone and macOS, NVDA on Windows) are planned before 1.0.

## Known limits

- The interface is in German and English only.
- Reminders come from the operating system; how they read out and which buttons they offer depends on it (see [Reminders](reminders.md)).

## Reporting a problem

If something does not work for you with a keyboard, a screen reader, a magnifier or another aid, please open an issue on GitHub and name the page, the device, the browser and the aid. Problems that block use are treated like bugs.
