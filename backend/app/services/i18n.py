"""The few texts the server itself produces (CSV export, shortcut answer) in German or English.

Everything else is translated in the web app. Language: the account's setting, else the
request's Accept-Language, else English.
"""

from fastapi import Request

from app.models.user import LOCALES, User

DEFAULT_LOCALE = "en"

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "csv.date": "date",
        "csv.habit": "habit",
        "csv.cue": "cue",
        "csv.planned": "planned",
        "csv.state": "state",
        "csv.yes": "yes",
        "csv.no": "no",
        "state.open": "open",
        "state.done": "done",
        "state.extra_done": "done (extra)",
        "state.not_planned": "not planned",
        "shortcut.done": "Done today",
        "shortcut.already_done": "Already done",
    },
    "de": {
        "csv.date": "datum",
        "csv.habit": "gewohnheit",
        "csv.cue": "hinweis",
        "csv.planned": "geplant",
        "csv.state": "zustand",
        "csv.yes": "ja",
        "csv.no": "nein",
        "state.open": "offen",
        "state.done": "erledigt",
        "state.extra_done": "zusätzlich erledigt",
        "state.not_planned": "nicht geplant",
        "shortcut.done": "Heute erledigt",
        "shortcut.already_done": "Bereits erledigt",
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
