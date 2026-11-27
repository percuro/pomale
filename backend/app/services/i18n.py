"""The few texts the server itself produces (CSV export, shortcut answer) in German or English.

Everything else is translated in the web app. Language: the account's setting, else the
request's Accept-Language, else English.
"""

from fastapi import Request

from app.models.user import LOCALES, User

DEFAULT_LOCALE = "en"

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "shortcut.done": "Done today",
        "shortcut.already_done": "Already done",
        "shortcut.counted": "{value} of {target}",
        "push.test_title": "Test notification",
        "push.test_body": "Reminders from {app} reach this device.",
        "reminder.open": "Still open",
        "reminder.quantity": "{value} of {target}",
        "reminder.quantity_unit": "{value} of {target} {unit}",
        "reminder.weekly": "{done} of {target} this week",
        "reminder.several": "{count} habits open",
        "reminder.done_action": "Done",
        "today.open": "Still open: {items}",
        "today.all_done": "All done for today.",
        "today.nothing_due": "Nothing planned for today.",
    },
    "de": {
        "shortcut.done": "Heute erledigt",
        "shortcut.already_done": "Bereits erledigt",
        "shortcut.counted": "{value} von {target}",
        "push.test_title": "Testbenachrichtigung",
        "push.test_body": "Erinnerungen von {app} kommen auf diesem Gerät an.",
        "reminder.open": "Noch offen",
        "reminder.quantity": "{value} von {target}",
        "reminder.quantity_unit": "{value} von {target} {unit}",
        "reminder.weekly": "{done} von {target} diese Woche",
        "reminder.several": "{count} Gewohnheiten offen",
        "reminder.done_action": "Erledigt",
        "today.open": "Noch offen: {items}",
        "today.all_done": "Heute ist alles erledigt.",
        "today.nothing_due": "Heute ist nichts geplant.",
    },
}


def accept_language(header: str | None) -> str | None:
    """First supported language in an Accept-Language header, honouring q-values."""
    if not header:
        return None
    candidates = []
    for index, part in enumerate(header.split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 0.0
        language = tag.strip().lower().split("-")[0]
        if language in LOCALES and quality > 0:
            candidates.append((-quality, index, language))
    return min(candidates)[2] if candidates else None


def resolve_locale(user: User | None, request: Request | None) -> str:
    if user is not None and user.locale in LOCALES:
        return user.locale
    if request is not None:
        return accept_language(request.headers.get("Accept-Language")) or DEFAULT_LOCALE
    return DEFAULT_LOCALE


def text(locale: str, key: str) -> str:
    return TEXTS.get(locale, TEXTS[DEFAULT_LOCALE])[key]


def progress_text(
    locale: str,
    goal_type: str,
    value: int | None,
    target: int | None,
    unit: str | None,
    week: tuple[int, int] | None = None,
) -> str | None:
    """ "3 of 8 glasses" for amounts, "1 of 3 this week" for weekly goals, else None."""
    if goal_type == "quantity":
        values = {"value": value or 0, "target": target, "unit": unit}
        return text(locale, "reminder.quantity_unit" if unit else "reminder.quantity").format(**values)
    if goal_type == "weekly_count" and week is not None:
        return text(locale, "reminder.weekly").format(done=week[0], target=week[1])
    return None
