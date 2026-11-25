# Using it on an iPhone

The interface is in English or German: it follows the language chosen on the account page, otherwise the phone's language. Labels below are given in English with the German wording in brackets.

## Home-screen web app

1. Open your instance (e.g. `https://habits.example.org`) in **Safari**.
2. Share → **Add to Home Screen**.
3. Open it **from the new icon** and log in there. The home-screen app has its own cookie storage, so a login in Safari does not carry over. Logins last 30 days without use, at most 90 days (configurable). With single sign-on, see the note in [Single sign-on](oidc.md#iphone-home-screen-app).
4. "Today" ("Heute"): tap a row to mark it done; "Undo" ("Rückgängig") next to it undoes. The row stays where it is.

### Offline

- After the first visit with a connection the app also opens offline and shows the last loaded week.
- Checking off works offline too. Such entries are marked "waiting to be sent" ("wartet auf Übertragung"), and a banner shows how many are pending.
- Changes are sent as soon as the **open** app has a connection again: on opening, when switching back to it, or via "Send now" ("Jetzt senden"). Nothing is sent in the background.
- An entry made offline stays on the day it was made, even if it is sent after midnight.
- If the same day was changed differently on another device in the meantime, the app shows **both states** and asks which one to keep ("Conflicting change" / "Abweichende Änderung"). Nothing is overwritten silently.
- Logging out with unsent changes asks for confirmation. The changes stay on the phone and are sent when the same account logs in again; another account using the same phone never sends or sees them.

## Shortcut widget for a favourite habit

Checks off one habit from the home screen without opening the app. The shortcut does not use the app's offline queue: without a connection it reports an error, never a success.

### 1. Create a key (web app)

"Habits" ("Gewohnheiten") → at the habit: **Shortcut** ("Kurzbefehl") → name the device → **Create key** ("Schlüssel anlegen"). URL, method and header are shown **only once**; copy them straight into the Shortcuts app and nowhere else. The key can only mark this one habit as done for today. Revoke it any time with "Revoke" ("Widerrufen") under the same button.

### 2. Build the shortcut (Shortcuts app)

1. **+** → name it, e.g. "Read ✓".
2. Action **Get Contents of URL**:
   - URL: the address shown, ending in `/days/today`
   - Method: **PUT**
   - Headers: `Authorization` = `Bearer ht_…` (the value shown)
   - Request Body: **JSON**, field `done`, type **Boolean**, value **true**
3. Action **Get Dictionary Value**: key `message` from "Contents of URL".
4. Action **Show Result** (or "Show Notification") with that value.

The server determines the date in the time zone of the habit's owner (account page); the shortcut does not send one. The message is in the owner's language, or the phone's if none is set. For automations, the field `result` is `done` or `already_done` in every language.

| Response (`message`) | Meaning |
|---|---|
| "…: Done today" ("Heute erledigt") | checked off |
| "…: Already done" ("Bereits erledigt") | was already done, no second entry |
| Error 401 | key wrong or revoked, or the account is deactivated |
| Error 403 | key belongs to a different habit |
| Error 409 | habit is archived |
| Error 429 | too many failed attempts, wait 15 minutes |
| Network error | nothing recorded; tap again or use the web app |

### 3. Widget

Long-press the home screen → **Edit** → **Add Widget** → **Shortcuts** → choose a size → select the shortcut in the widget.

On the first run iOS asks whether the shortcut may access the address ("Allow"). Depending on the iOS version the Shortcuts app opens briefly. Check on your device: two taps must give "Already done" ("Bereits erledigt"), and in flight mode there must be no success message.

## Checklist

- [ ] Ten check-ins from the today view: median at most three seconds from the visible list, one tap
- [ ] VoiceOver reads name, cue and state
- [ ] Larger Text (Settings → Display & Brightness → Text Size): checking off works without horizontal scrolling
- [ ] A correction on the laptop shows up the next time the iPhone app is opened
- [ ] Flight mode: check off → marked → flight mode off, open the app → sent
- [ ] Shortcut: two taps give one entry; after revoking, no success message
