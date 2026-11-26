# Reminders

pomale can remind you of a habit that is still open: a notification at a time you choose, on the devices where you turned reminders on. It uses Web Push, the standard way installed web apps send notifications, so no app store and no extra service is needed.

## How it works

- Each habit can have up to **three reminder times** ("Habits" → Edit → "Add a time"). They are times in your account's time zone.
- At that time pomale checks whether the habit is **still open today**. If it is done, paused, not planned today, or its weekly goal is already reached, nothing is sent. A quantity goal below its target counts as open ("3 of 8 glasses").
- Habits due in the **same minute** come as one notification ("3 habits open: Read, Water, Stretch").
- A notification for one habit has a **Done** button on Android and desktop browsers. It checks the habit off for that day without opening the app; if the phone is offline, the check-off waits in the app's queue and is sent when you next open pomale. iPhone and iPad do not show buttons: a tap opens the app.
- Each reminder fires **at most once a day**. Editing a habit does not send it again.
- If your day ends after midnight (account page → "My day ends at"), a reminder time **before the day end belongs to the day that is ending**: with a day end of 02:00, a reminder at 00:30 asks about the day before, and its Done button checks off that day. The habit form marks such times with "counts for the day before". Changing the day end in the middle of the night can skip or repeat one reminder that night.
- If the server was down at the reminder time (e.g. during an update), it catches up for **15 minutes**, also across the end of the day (a reminder at 23:55 is still sent at 00:05, for the day it was meant for); older reminders are dropped instead of arriving all at once.
- On days when clocks change, a time that does not exist (e.g. 02:30 when clocks jump to 03:00) is sent one hour later; a time that happens twice is sent once.

## Turning it on

"Account" ("Konto") → **Reminders** ("Erinnerungen") → **Turn on for this device**. The browser asks for permission; pomale only asks after you tap that button. **Send a test** checks the whole chain. The list below shows every device that gets reminders; remove any of them there.

Reminders are per device. Logging out on a device, or ending its session under "Devices", turns its reminders off; deleting the account removes all of them. A login that simply expires keeps the device's reminders.

### Browsers

| Device | Works |
|---|---|
| Android: Chrome, Edge, Firefox, Samsung Internet | yes, also without installing the app; the Done button works |
| Windows, macOS, Linux: Chrome, Edge, Firefox, Safari 16+ | yes, while the browser runs |
| **iPhone and iPad (iOS/iPadOS 16.4 or later)** | **only in the web app on the home screen**, not in Safari itself |
| iOS before 16.4 | no |

### iPhone and iPad

1. Add pomale to the home screen (Safari → Share → **Add to Home Screen**) and open it **from the icon**; see [iphone.md](iphone.md).
2. Log in there, open "Account" → Reminders → **Turn on for this device**, and allow notifications.
3. Notifications then appear like those of any app: on the lock screen, in the Notification Centre, with the app's name. A **Focus** mode can hold them back; add pomale to the allowed apps if you want them during a Focus.

## Troubleshooting

- **"Notifications are blocked":** permission was refused once. Allow it in the browser's site settings (iPhone: Settings → Notifications → pomale), then reload the account page.
- **Test works, reminders do not arrive:** check the time zone and the day end on the account page and that the habit is really open at that time. Reminders come only for habits that are planned and not yet done.
- **Nothing at all on Android:** battery optimisation can delay notifications of the browser; allow it to run in the background.
- **"The push service did not accept the notification":** the server could not reach the push service. The server needs outgoing HTTPS (port 443) to the push services listed under `PUSH_ALLOWED_HOSTS` in the [configuration](configuration.md).

## Privacy

A notification travels through the push service of the browser's maker: Google (Chrome, Android), Apple (Safari, iPhone), Mozilla (Firefox) or Microsoft (Edge on Windows). The message is **end-to-end encrypted** (RFC 8291): the push service sees that a message is sent to a device, but not the habit names in it. pomale stores per device only the push address and its public keys, plus the device type for the list.

## For operators

- Reminders are on by default. `PUSH_ENABLED=false` turns them off completely (no scheduler, no device list).
- On the first start pomale creates a key pair (VAPID) and stores it **in the database**. Backups therefore include it. If you restore a backup from another instance or start with a fresh database, existing devices stop receiving reminders until they are turned on again.
- The scheduler runs inside the app process and checks once a minute. Run exactly one instance (see [Limits](configuration.md#limits)).
- `PUSH_CONTACT` is sent to the push services so they can contact you about problems (default: `PUBLIC_URL`). Apple requires a `mailto:` or `https://` address.
