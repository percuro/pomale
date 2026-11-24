"""A short, readable device name from a User-Agent, e.g. "iPhone · Safari".

Deliberately rough: it only helps people tell their own sessions apart.
"""

_PLATFORMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Macintosh", "Mac"),
    ("Linux", "Linux"),
)
# Order matters: Edge and Opera also say "Chrome", Chrome also says "Safari"
_BROWSERS = (
    ("Edg", "Edge"),
    ("OPR", "Opera"),
    ("SamsungBrowser", "Samsung Internet"),
    ("Firefox", "Firefox"),
    ("FxiOS", "Firefox"),
    ("CriOS", "Chrome"),
    ("Chrome", "Chrome"),
    ("Safari", "Safari"),
)


def describe_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    platform = next((name for token, name in _PLATFORMS if token in user_agent), None)
    browser = next((name for token, name in _BROWSERS if token in user_agent), None)
    if platform is None and browser is None:
        return None
    if platform in ("iPhone", "iPad") and browser is None:
        # Home-screen web apps on iOS do not mention Safari
        browser = "Safari"
    return " · ".join(part for part in (platform, browser) if part)
